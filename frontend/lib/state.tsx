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
  useRef,
  useState,
  type ReactNode,
} from "react";

import {
  api,
  type AnomalyView,
  type AwarenessBreakdown,
  type CommandResponse,
  type DockState,
  type MissionView,
  type OperatingMode,
  type OperatorCommand,
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
  dispatch: Dispatch;
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
        const [s, aw, dk, sc, un, ms, an, ev, cm] = await Promise.all([
          api.session(),
          api.awareness(),
          api.docks(),
          api.sectors(),
          api.units(),
          api.missions(),
          api.anomalies(),
          api.events(50),
          api.commands(50),
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
      } catch {
        /* backend not up yet — WS will fill in once it connects */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  // Boot WS subscription only when authenticated; the backend refuses
  // upgrades without an access token.
  useEffect(() => {
    if (!isAuthed) {
      setLink("lost");
      return;
    }
    const sock = new SwarmSocket(() =>
      authState.status === "authenticated" ? authState.session.accessToken : null
    );
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
  const dispatchRef = useRef<Dispatch | null>(null);
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
  dispatchRef.current = dispatch;

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
      streams,
      awareness,
      link,
      clock,
      operatorId,
      role,
      mode: awareness.mode,
      verifier,
      primaryDock,
      dispatch,
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
      streams,
      awareness,
      link,
      clock,
      operatorId,
      role,
      verifier,
      primaryDock,
      dispatch,
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
