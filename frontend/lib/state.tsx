"use client";

/**
 * SwarmStateProvider — the Console's single source of state.
 *
 * Boots from REST snapshots, then merges live WS frames keyed by `kind`. Every
 * value the surfaces read goes through this provider; nothing fetches on its
 * own. `dispatch` exposes the four Phase 1 operator intents (verify /
 * hold-patrol / dismiss / return). `derived` exposes Phase 2 fallbacks for
 * fields not yet projected server-side, each carrying a `derived: true` flag.
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
  type TimelineEvent,
  type UnitState,
} from "./api";
import {
  deriveOperatingMode,
  deriveVerifier,
  fallbackAwareness,
  formatClock,
  type MaybeDerived,
} from "./derive";
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
  awareness: AwarenessBreakdown;
  link: LinkState;
  clock: { time: string; date: string };
  operatorId: string;
  // ── Phase 2 derived (flag carried) ──────────────────────────────────────────
  mode: { value: OperatingMode; derived: boolean; reason?: string };
  verifier: { value: UnitState | null; derived: boolean; reason?: string };
  primaryDock: { value: DockState | null; derived: boolean; reason?: string };
  // ── Actions ─────────────────────────────────────────────────────────────────
  dispatch: Dispatch;
};

const SwarmContext = createContext<SwarmState | null>(null);

const DEFAULT_OPERATOR_ID = "op-001";

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

function unwrap<T>(m: MaybeDerived<T>): { value: T; derived: boolean; reason?: string } {
  return m.derived ? { value: m.value, derived: true, reason: m.reason } : { value: m.value, derived: false };
}

// ── Provider ───────────────────────────────────────────────────────────────────

export function SwarmStateProvider({
  children,
  operatorId = DEFAULT_OPERATOR_ID,
}: {
  children: ReactNode;
  operatorId?: string;
}) {
  // Server-issued aggregates.
  const [session, setSession] = useState<Session | null>(null);
  const [units, setUnits] = useState<UnitState[]>([]);
  const [docks, setDocks] = useState<DockState[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [missions, setMissions] = useState<MissionView[]>([]);
  const [anomalies, setAnomalies] = useState<AnomalyView[]>([]);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [commands, setCommands] = useState<OperatorCommand[]>([]);
  const [awareness, setAwareness] = useState<AwarenessBreakdown>(() => fallbackAwareness(new Date()));
  // Link + clock.
  const [link, setLink] = useState<LinkState>("connecting");
  const [clock, setClock] = useState(() => formatClock(new Date()));

  // Boot REST snapshot.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, aw, dk, sc, un, ms, an, ev] = await Promise.all([
          api.session(),
          api.awareness(),
          api.docks(),
          api.sectors(),
          api.units(),
          api.missions(),
          api.anomalies(),
          api.events(50),
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
      } catch {
        /* backend not up yet — WS will fill in once it connects */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Boot WS subscription.
  useEffect(() => {
    const sock = new SwarmSocket();
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
      }
    });
    return () => {
      off();
      sock.close();
      clearInterval(heartbeat);
    };
  }, []);

  // Clock tick (UTC, 30s cadence is enough — operator surfaces show hh:mm).
  useEffect(() => {
    const tick = () => setClock(formatClock(new Date()));
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  // Dispatch.
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
      const { data, status } = await route(target, operatorId);
      return { ok: status >= 200 && status < 300, status, body: data };
    },
    [operatorId]
  );
  dispatchRef.current = dispatch;

  // Derived values.
  const focusAnomaly =
    anomalies.find((a) => a.state === "pending" || a.state === "verifying") ??
    anomalies.find((a) => a.state === "verified" || a.state === "escalated") ??
    null;
  const modeD = useMemo(() => deriveOperatingMode(units, anomalies), [units, anomalies]);
  const verifierD = useMemo(() => deriveVerifier(units, focusAnomaly), [units, focusAnomaly]);
  const primaryD = useMemo(() => {
    if (docks.length === 0) return { value: null, derived: false } as MaybeDerived<DockState | null>;
    if (docks.length === 1) return { value: docks[0], derived: false } as MaybeDerived<DockState | null>;
    const primary = docks.find((d) => d.status === "online") ?? docks[0];
    return { value: primary, derived: true, reason: "primary dock heuristic" } as MaybeDerived<DockState | null>;
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
      awareness,
      link,
      clock,
      operatorId,
      mode: unwrap(modeD),
      verifier: unwrap(verifierD),
      primaryDock: unwrap(primaryD),
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
      awareness,
      link,
      clock,
      operatorId,
      modeD,
      verifierD,
      primaryD,
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
