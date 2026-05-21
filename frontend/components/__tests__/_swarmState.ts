/**
 * Phase 7.C — minimal stub of the SwarmState context for component tests.
 *
 * The real provider boots from REST + WS, which is heavier than these
 * focused render tests need. Each test passes the slice it cares about
 * and lets the helper fill in safe defaults for everything else.
 */

import type {
  AnomalyView,
  AwarenessBreakdown,
  DockState,
  MissionView,
  OperatorCommand,
  Sector,
  Session,
  StreamDescriptor,
  TimelineEvent,
  UnitState,
} from "@/lib/api";
import type { SwarmState } from "@/lib/state";

const NOW_ISO = new Date(0).toISOString();

const DEFAULT_AWARENESS: AwarenessBreakdown = {
  score: 0,
  factors: {},
  blind_spot_sectors: [],
  stale_sectors: [],
  risk_state: "rest",
  mode: "rest",
  verifying_agent: null,
  ts: NOW_ISO,
};

export function makeSwarmState(overrides: Partial<SwarmState> = {}): SwarmState {
  const session: Session = overrides.session ?? {
    id: "sess-1",
    label: "session 014",
    site_id: "vineyard-01",
    autonomy_enabled: false,
    started_at: NOW_ISO,
    ts: NOW_ISO,
  };
  return {
    session,
    units: overrides.units ?? ([] as UnitState[]),
    docks: overrides.docks ?? ([] as DockState[]),
    sectors: overrides.sectors ?? ([] as Sector[]),
    missions: overrides.missions ?? ([] as MissionView[]),
    anomalies: overrides.anomalies ?? ([] as AnomalyView[]),
    events: overrides.events ?? ([] as TimelineEvent[]),
    commands: overrides.commands ?? ([] as OperatorCommand[]),
    streams: overrides.streams ?? ({} as Record<string, StreamDescriptor>),
    awareness: overrides.awareness ?? DEFAULT_AWARENESS,
    link: overrides.link ?? "connected",
    clock: overrides.clock ?? { time: "00:00", date: "1970-01-01" },
    operatorId: overrides.operatorId ?? "op-test",
    role: overrides.role ?? "operator",
    mode: overrides.mode ?? "rest",
    verifier: overrides.verifier ?? null,
    primaryDock: overrides.primaryDock ?? null,
    autonomyEnabled: overrides.autonomyEnabled ?? session.autonomy_enabled,
    dispatch: overrides.dispatch ?? (async () => ({
      ok: true,
      status: 200,
      body: { command_id: "x", status: "accepted" },
    })),
  };
}

export function makeCommand(
  overrides: Partial<OperatorCommand> = {}
): OperatorCommand {
  return {
    id: overrides.id ?? "cmd-1",
    action: overrides.action ?? "verify",
    target: overrides.target ?? "anomaly:a-1",
    operator_id: overrides.operator_id ?? "op-test",
    source: overrides.source ?? "operator",
    rule: overrides.rule ?? null,
    submitted_at: overrides.submitted_at ?? NOW_ISO,
    accepted_at: overrides.accepted_at ?? null,
    in_flight_at: overrides.in_flight_at ?? null,
    status: overrides.status ?? "submitted",
    rejected_reason: overrides.rejected_reason ?? null,
    completed_at: overrides.completed_at ?? null,
    mission_id: overrides.mission_id ?? null,
    ts: overrides.ts ?? NOW_ISO,
  };
}

export function makeEvent(
  overrides: Partial<TimelineEvent> = {}
): TimelineEvent {
  return {
    id: overrides.id ?? "evt-1",
    kind: overrides.kind ?? "operator",
    ts: overrides.ts ?? NOW_ISO,
    sector_id: overrides.sector_id ?? null,
    agent_id: overrides.agent_id ?? null,
    mission_id: overrides.mission_id ?? null,
    anomaly_id: overrides.anomaly_id ?? null,
    dock_id: overrides.dock_id ?? null,
    confidence: overrides.confidence ?? null,
    body: overrides.body ?? "operator intent accepted · verify",
    action_label: overrides.action_label ?? null,
    source: overrides.source ?? "operator",
  };
}

export function makeAnomaly(
  overrides: Partial<AnomalyView> = {}
): AnomalyView {
  return {
    id: overrides.id ?? "a-1",
    kind: overrides.kind ?? "SMOKE",
    geo: overrides.geo ?? { lat: 44.7, lon: 8.03, alt_m: 0 },
    sector_id: overrides.sector_id ?? "center-a",
    confidence: overrides.confidence ?? 0.6,
    band: overrides.band ?? "elevated",
    state: overrides.state ?? "pending",
    detected_at: overrides.detected_at ?? NOW_ISO,
    detected_by: overrides.detected_by ?? null,
    verifying_agent: overrides.verifying_agent ?? null,
    ts: overrides.ts ?? NOW_ISO,
  };
}
