"use client";

/**
 * SwarmStateProvider — the Console's single source of state.
 *
 * Every value here is server-issued. SwarmOS decides; Console renders.
 * Boots from REST snapshots, then merges live WS frames keyed by `kind`.
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
  type DispositionDecision,
  type DockState,
  type ExecutionGroup,
  type MissionRuntimeEvent,
  type MissionView,
  type OperatingMode,
  type OperatorCommand,
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

export type LinkState = "connected" | "connecting" | "lost";
export type Intent = "verify" | "hold_patrol" | "dismiss" | "return";

export type IntentResult = {
  ok: boolean;
  status: number;
  body: CommandResponse;
};

export type Dispatch = (intent: Intent, target: string) => Promise<IntentResult>;

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
  /** Latest SwarmOS-owned station geometry per objective mission. */
  dispositions: DispositionDecision[];
  missionRuntime: MissionRuntimeEvent[];
  /** Append-only runtime frames observed this session; still server truth. */
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  streams: Record<string, StreamDescriptor>;
  awareness: AwarenessBreakdown;
  link: LinkState;
  clock: { time: string; date: string };
  operatorId: string;
  role: Role | null;
  mode: OperatingMode;
  verifier: UnitState | null;
  primaryDock: DockState | null;
  autonomyEnabled: boolean;
  dispatch: Dispatch;
};

const SwarmContext = createContext<SwarmState | null>(null);

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

export function SwarmStateProvider({ children }: { children: ReactNode }) {
  const { state: authState } = useAuth();
  const isAuthed = authState.status === "authenticated";
  const operatorId = isAuthed ? authState.session.operatorId : "";
  const role: Role | null = isAuthed ? authState.session.role : null;

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
  const [dispositions, setDispositions] = useState<DispositionDecision[]>([]);
  const [missionRuntime, setMissionRuntime] = useState<MissionRuntimeEvent[]>([]);
  const [missionRuntimeLog, setMissionRuntimeLog] = useState<MissionRuntimeEvent[]>([]);
  const [payloadEvents, setPayloadEvents] = useState<PayloadEvent[]>([]);
  const [streams, setStreams] = useState<Record<string, StreamDescriptor>>({});
  const [awareness, setAwareness] = useState<AwarenessBreakdown>(() =>
    fallbackAwareness(new Date())
  );
  const [link, setLink] = useState<LinkState>("connecting");
  const [clock, setClock] = useState(() => formatClock(new Date()));

  useEffect(() => {
    if (!isAuthed) return;
    let cancelled = false;
    (async () => {
      try {
        const [s, aw, dk, sc, un, ms, an, ev, cm, al, eg, dp, mr, pe] =
          await Promise.all([
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
            api.dispositions(),
            api.missionRuntime(),
            api.payloadEvents(200),
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
        setDispositions(dp.dispositions);
        setMissionRuntime(mr.mission_runtime);
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
    setDispositions([]);
    setMissionRuntime([]);
    setMissionRuntimeLog([]);
    setPayloadEvents([]);
    setStreams({});
    setAwareness(fallbackAwareness(new Date()));
  }, [isAuthed]);

  useEffect(() => {
    if (!isAuthed) {
      setLink("lost");
      return;
    }
    const sock = new SwarmSocket(() => {
      if (authState.status !== "authenticated") return null;
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
        case "disposition":
          setDispositions((prev) =>
            upsertById(prev, msg.data, "objective_mission_id")
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

  useEffect(() => {
    const tick = () => setClock(formatClock(new Date()));
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const dispatch: Dispatch = useCallback(async (intent, target) => {
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
  }, []);

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
      dispositions,
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
      dispositions,
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
    ]
  );

  return <SwarmContext.Provider value={value}>{children}</SwarmContext.Provider>;
}

export function useSwarm(): SwarmState {
  const ctx = useContext(SwarmContext);
  if (!ctx) throw new Error("useSwarm must be used inside <SwarmStateProvider>");
  return ctx;
}

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
