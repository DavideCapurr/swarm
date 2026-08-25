"use client";

/**
 * SwarmStateProvider — the Console's single source of state.
 *
 * Phase 3 truth-layer: every value here is server-issued. The `derived` flags
 * from Phase 2 are gone — `mode`, `verifier`, and `primaryDock` are read
 * directly off the WS/REST frames. SwarmOS decides; Console renders.
 *
 * Boots from REST snapshots, then merges live WS frames keyed by `kind`.
 * Surfaces never fetch on their own — they read from `useSwarm()`.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  api,
  type AllocationDecision,
  type AnomalyView,
  type AwarenessBreakdown,
  type CommandResponse,
  type DockState,
  type ExecutionGroup,
  type MissionDecision,
  type MissionDecisionReview,
  type MissionRuntimeEvent,
  type MissionView,
  type OperatingMode,
  type OperatorCommand,
  type ObjectiveStateFrame,
  type PayloadEvent,
  type Sector,
  type Session,
  type StreamDescriptor,
  type TimelineEvent,
  type UnitState,
} from "./api";
import { useAuth, type Role } from "./auth";
import { fallbackAwareness, formatClock } from "./derive";
import { SwarmSocket, type WSMessage } from "./ws";

// ── Link health ────────────────────────────────────────────────────────────────

export type LinkState = "connected" | "connecting" | "lost";

// ── Dispatch ───────────────────────────────────────────────────────────────────

export type Intent = "verify" | "hold_patrol" | "dismiss" | "return";

export type IntentResult = {
  ok: boolean;
  status: number;
  body: CommandResponse;
};

export type Dispatch = (intent: Intent, target: string) => Promise<IntentResult>;
export type DecisionReview = (
  decisionId: string,
  action: "approve" | "reject"
) => Promise<{ ok: boolean; status: number }>;

// ── Context shape ──────────────────────────────────────────────────────────────

export type SwarmState = {
  session: Session | null;
  units: UnitState[];
  docks: DockState[];
  sectors: Sector[];
  missions: MissionView[];
  anomalies: AnomalyView[];
  events: TimelineEvent[];
  commands: OperatorCommand[];
  allocations: AllocationDecision[];
  executionGroups: ExecutionGroup[];
  missionDecisions: MissionDecision[];
  missionDecisionReviews: MissionDecisionReview[];
  objectiveStates: ObjectiveStateFrame[];
  missionRuntime: MissionRuntimeEvent[];
  /**
   * Append-only record of the runtime frames this session observed.
   *
   * `missionRuntime` — like the backend's own projection — keeps only the
   * latest frame per mission, so the discrete execution ladder (ALLOCATED →
   * … → DONE) would be unreadable from it alone. This buffers the frames as
   * they arrive, de-duplicated by their server-issued id. It stores server
   * truth; it derives nothing.
   */
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  // Phase 5: stream descriptors per agent_id. `null` ≡ no descriptor yet
  // received; in that case the Console falls back to the placard.
  streams: Record<string, StreamDescriptor>;
  awareness: AwarenessBreakdown;
  link: LinkState;
  clock: { time: string; date: string };
  operatorId: string;
  role: Role | null;
  // Truth values projected by SwarmOS — no derive layer.
  mode: OperatingMode;
  verifier: UnitState | null;
  primaryDock: DockState | null;
  // Phase 7.C — mirrors session.autonomy_enabled. Read by HeadBar to
  // render the inline `autonomy baseline` chip.
  autonomyEnabled: boolean;
  dispatch: Dispatch;
  reviewDecision: DecisionReview;
};

const SwarmContext = createContext<SwarmState | null>(null);

// ── Helpers ────────────────────────────────────────────────────────────────────

function upsertById<T extends { [k: string]: unknown }>(
  list: T[],
  next: T,
  key: keyof T
): T[] {
  const idx = list.findIndex((x) => x[key] === next[key]);
  if (idx === -1) return [...list, next];
  const copy = list.slice();
  copy[idx] = next;
  return copy;
}

// ── Provider ───────────────────────────────────────────────────────────────────

export function SwarmStateProvider({
  children,
}: {
  children: ReactNode;
}) {
  const { state: authState } = useAuth();
  const isAuthed = authState.status === "authenticated";
  const operatorId = isAuthed ? authState.session.operatorId : "";
  const role: Role | null = isAuthed ? authState.session.role : null;
  // Server-issued aggregates.
  const [session, setSession] = useState<Session | null>(null);
  const [units, setUnits] = useState<UnitState[]>([]);
  const [docks, setDocks] = useState<DockState[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [missions, setMissions] = useState<MissionView[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyView[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [commands, setCommands] = useState<OperatorCommand[]>([]);
  const [allocations, setAllocations] = useState<AllocationDecision[]>([]);
  const [executionGroups, setExecutionGroups] = useState<ExecutionGroup[]>([]);
  const [missionDecisions, setMissionDecisions] = useState<MissionDecision[]>([]);
  const [missionDecisionReviews, setMissionDecisionReviews] = useState<
    MissionDecisionReview[]
  >([]);
  const [objectiveStates, setObjectiveStates] = useState<ObjectiveStateFrame[]>([]);
  const [missionRuntime, setMissionRuntime] = useState<MissionRuntimeEvent[]>([]);
  const [missionRuntimeLog, setMissionRuntimeLog] = useState<MissionRuntimeEvent[]>([]);
  const [payloadEvents, setPayloadEvents] = useState<PayloadEvent[]>([]);
  const [streams, setStreams] = useState<Record<string, StreamDescriptor>>({});
  const [awareness, setAwareness] = useState<AwarenessBreakdown>(() => fallbackAwareness(new Date()));
  // Link + clock.
  const [link, setLink] = useState<LinkState>("connecting");
  const [clock, setClock] = useState(() => formatClock(new Date()));

  // Boot REST snapshot. Re-run whenever auth flips so a fresh login
  // pulls fresh data; an anonymous user gets no snapshot calls (which
  // would 401 anyway).
  useEffect(() => {
    if (!isAuthed) return;
    let cancelled = false;
    (async () => {
      try {
        const [s, aw, dk, sc, un, ms, an, ev, cm, al, eg, mr, pe, md, mdr, os] = await Promise.all([
          api.session(),
          api.awareness(),
          api.docks(),
          api.sectors(),
          api.units(),
          api.missions(),
          api.anomalies(),
          api.events(50),
          api.commands(50),
          api.allocations(),
          api.executionGroups(),
          api.missionRuntime(),
          api.payloadEvents(200),
          api.missionDecisions(),
          api.missionDecisionReviews(),
          api.objectiveStates(),
        ]);
        if (cancelled) return;
        setSession(s.session);
        setAwareness(aw.awareness);
        setDocks(dk.docks);
        setSectors(sc.sectors);
        setUnits(un.units);
        setMissions(ms.missions);
        setAnomalies(an.anomalies);
        setEvents(ev.events);
        setCommands(cm.commands);
        setAllocations(al.allocations);
        setExecutionGroups(eg.execution_groups);
        setMissionDecisions(md.decisions);
        setMissionDecisionReviews(mdr.reviews);
        setObjectiveStates(os.objective_states);
        setMissionRuntime(mr.mission_runtime);
        // The REST snapshot is latest-per-mission, so it seeds the log with
        // whatever the backend currently holds; live frames extend it.
        setMissionRuntimeLog(mr.mission_runtime);
        setPayloadEvents(pe.payload_events);
      } catch {
        /* backend not up yet — WS will fill in once it connects */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  // Drop all server data on logout so a later login (possibly a different
  // operator) starts from a clean slate instead of the previous session's
  // frames.
  useEffect(() => {
    if (isAuthed) return;
    setSession(null);
    setUnits([]);
    setDocks([]);
    setSectors([]);
    setMissions([]);
    setAnomalies([]);
    setEvents([]);
    setCommands([]);
    setAllocations([]);
    setExecutionGroups([]);
    setMissionDecisions([]);
    setMissionDecisionReviews([]);
    setObjectiveStates([]);
    setMissionRuntime([]);
    setMissionRuntimeLog([]);
    setPayloadEvents([]);
    setStreams({});
    setAwareness(fallbackAwareness(new Date()));
  }, [isAuthed]);

  // Boot WS subscription only when authenticated; the backend refuses
  // upgrades without an access token.
  useEffect(() => {
    if (!isAuthed) {
      setLink("lost");
      return;
    }
    const sock = new SwarmSocket(() => {
      if (authState.status !== "authenticated") return null;
      // A token this close to expiry would die server-side right after
      // the upgrade; report none and let the socket's retry loop pick up
      // the refreshed token instead.
      if (authState.session.expiresAt - Date.now() < 30_000) return null;
      return authState.session.accessToken;
    });
    sock.connect();
    setLink("connecting");
    let lastFrame = 0;
    const heartbeat = setInterval(() => {
      setLink((curr) => {
        if (lastFrame === 0) return curr === "lost" ? "lost" : "connecting";
        if (Date.now() - lastFrame < 6_000) return "connected";
        return "lost";
      });
    }, 2_000);
    const off = sock.onMessage((msg: WSMessage) => {
      lastFrame = Date.now();
      setLink("connected");
      switch (msg.kind) {
        case "session":
          setSession(msg.data);
          return;
        case "unit":
          setUnits((prev) => upsertById(prev, msg.data, "agent_id"));
          return;
        case "dock":
          setDocks((prev) => upsertById(prev, msg.data, "dock_id"));
          return;
        case "sector":
          setSectors((prev) => upsertById(prev, msg.data, "id"));
          return;
        case "awareness":
          setAwareness(msg.data);
          return;
        case "mission":
          setMissions((prev) => upsertById(prev, msg.data, "id"));
          return;
        case "anomaly_view":
          setAnomalies((prev) => upsertById(prev, msg.data, "id"));
          return;
        case "event":
          setEvents((prev) => {
            if (prev.some((e) => e.id === msg.data.id)) return prev;
            return [...prev.slice(-499), msg.data];
          });
          return;
        case "operator":
          setCommands((prev) => upsertById(prev, msg.data, "id"));
          return;
        case "stream":
          setStreams((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
          return;
        case "allocation":
          setAllocations((prev) => upsertById(prev, msg.data, "mission_id"));
          return;
        case "execution_group":
          setExecutionGroups((prev) => upsertById(prev, msg.data, "id"));
          return;
        case "mission_decision":
          setMissionDecisions((prev) =>
            upsertById(prev, msg.data, "decision_id")
          );
          return;
        case "mission_decision_review":
          setMissionDecisionReviews((prev) =>
            upsertById(prev, msg.data, "review_id")
          );
          return;
        case "objective_state":
          setObjectiveStates((prev) =>
            upsertById(prev, msg.data, "objective_id")
          );
          return;
        case "mission_runtime":
          setMissionRuntime((prev) => upsertById(prev, msg.data, "mission_id"));
          setMissionRuntimeLog((prev) => {
            if (prev.some((e) => e.id === msg.data.id)) return prev;
            return [...prev.slice(-499), msg.data];
          });
          return;
        case "payload":
          setPayloadEvents((prev) => {
            if (prev.some((e) => e.id === msg.data.id)) return prev;
            return [...prev.slice(-499), msg.data];
          });
          return;
      }
    });
    return () => {
      off();
      sock.close();
      clearInterval(heartbeat);
    };
  }, [isAuthed, authState]);

  // Clock tick (UTC, 30s cadence is enough — operator surfaces show hh:mm).
  useEffect(() => {
    const tick = () => setClock(formatClock(new Date()));
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  // Dispatch — operator identity rides on the JWT, so the action signatures
  // don't need an operatorId argument anymore.
  const dispatch: Dispatch = useCallback(
    async (intent, target) => {
      const route =
        intent === "verify"
          ? api.verify
          : intent === "hold_patrol"
            ? api.holdPatrol
            : intent === "dismiss"
              ? api.dismiss
              : api.returnUnit;
      const { data, status } = await route(target);
      return { ok: status >= 200 && status < 300, status, body: data };
    },
    []
  );
  const reviewDecision: DecisionReview = useCallback(
    async (decisionId, action) => {
      const { status } = await api.reviewMissionDecision(decisionId, action);
      return { ok: status >= 200 && status < 300, status };
    },
    []
  );

  // Truth selectors — every one of these reads a field the server has
  // already populated. No client-side heuristics.
  const verifier = useMemo<UnitState | null>(() => {
    const id = awareness.verifying_agent;
    if (!id) return null;
    return units.find((u) => u.agent_id === id) ?? null;
  }, [units, awareness.verifying_agent]);
  const primaryDock = useMemo<DockState | null>(() => {
    if (docks.length === 0) return null;
    return docks.find((d) => d.primary) ?? docks[0];
  }, [docks]);

  const value = useMemo<SwarmState>(
    () => ({
      session,
      units,
      docks,
      sectors,
      missions,
      anomalies,
      events,
      commands,
      allocations,
      executionGroups,
      missionDecisions,
      missionDecisionReviews,
      objectiveStates,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
      streams,
      awareness,
      link,
      clock,
      operatorId,
      role,
      mode: awareness.mode,
      verifier,
      primaryDock,
      autonomyEnabled: session?.autonomy_enabled ?? false,
      dispatch,
      reviewDecision,
    }),
    [
      session,
      units,
      docks,
      sectors,
      missions,
      anomalies,
      events,
      commands,
      allocations,
      executionGroups,
      missionDecisions,
      missionDecisionReviews,
      objectiveStates,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
      streams,
      awareness,
      link,
      clock,
      operatorId,
      role,
      verifier,
      primaryDock,
      dispatch,
      reviewDecision,
    ]
  );

  return <SwarmContext.Provider value={value}>{children}</SwarmContext.Provider>;
}

export function useSwarm(): SwarmState {
  const ctx = useContext(SwarmContext);
  if (!ctx) throw new Error("useSwarm must be used inside <SwarmStateProvider>");
  return ctx;
}

// ── Convenience selectors ─────────────────────────────────────────────────────

export function useFocusAnomaly(): AnomalyView | null {
  const { anomalies } = useSwarm();
  return (
    anomalies.find((a) => a.state === "pending" || a.state === "verifying") ??
    anomalies.find((a) => a.state === "verified" || a.state === "escalated") ??
    null
  );
}

export function useUnit(agentId: string | null): UnitState | null {
  const { units } = useSwarm();
  if (!agentId) return null;
  return units.find((u) => u.agent_id === agentId) ?? null;
}
