/**
 * Recorded-take frame script — development and verification only.
 *
 * This is NOT a runtime capability and never reaches the live surface. It
 * exists so the operational console can be built, reviewed and regression
 * tested without a two-instance PX4 SITL bench, and so the comprehension
 * acceptance test in `docs/design/operational-console-ia.md` §8 can run in CI.
 *
 * Provenance, stated exactly:
 *
 *   RECORDED — anomaly ids, mission ids, owners, the winner scores, the BUSY
 *   exclusion with mission 1's active mission id, the evidence kinds and the
 *   take duration all come from take 1 of
 *   `docs/bench/artifacts/final-demo-rehearsal-2026-08-15.json`.
 *
 *   RECONSTRUCTED — the per-term score breakdowns and the agent positions.
 *   The artifact recorded only the score totals, so the terms are recomputed
 *   with the real allocator formula (`core/swarm_core/allocator.py::score_bid`,
 *   priority `80 + int(confidence * 20)`) and the positions are solved so that
 *   every distance reproduces the recorded total exactly. Both agents land
 *   within ~3 m of the PX4 SITL default home, which is what the bench ran.
 *
 *   SCRIPTED — the intra-take timing of each frame. The artifact recorded the
 *   ordering and the 62.7 s total, not per-frame timestamps.
 *
 * Anything rendered from this script is stamped `REPLAY · RECORDED FRAMES ·
 * NOT LIVE` by the command bar.
 */

import type {
  AllocationDecision,
  AnomalyView,
  Geo,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "./api";

// ── Recorded identities (take 1) ──────────────────────────────────────────────

export const TAKE_A = {
  durationMs: 62_749,
  t0: Date.UTC(2026, 7, 15, 12, 0, 0),
  anomalyOne: "537ff9257f814c168252bc5a1a2dbf3d",
  missionOne: "4c97f2f2127b454eae5cf76be2d20a5e",
  ownerOne: "mav-002",
  scoreOneWinner: 2.2583144913504087,
  scoreOneOther: 2.2566123015039246,
  anomalyTwo: "5301ed74aefe43fe97101520db711e24",
  missionTwo: "e768f1423a654f2bbb208330b62e578a",
  ownerTwo: "mav-001",
  scoreTwoWinner: 2.292894501797253,
} as const;

const OBJECTIVE_ONE: Geo = { lat: 47.398, lon: 8.546, alt_m: 0 };
const OBJECTIVE_TWO: Geo = { lat: 47.39775, lon: 8.54559, alt_m: 0 };

const HOME_001: Geo = { lat: 47.3977687, lon: 8.5455943, alt_m: 0 };
const HOME_002: Geo = { lat: 47.3977794, lon: 8.545613, alt_m: 0 };

const CRUISE_ALT_M = 30;

// ── Score breakdowns, recomputed with the real allocator terms ───────────────

function breakdown(distanceM: number, batteryPct: number, priority: number) {
  return {
    distance_m: distanceM,
    distance_score: 1.0 / (1.0 + distanceM / 1000.0),
    battery_pct: batteryPct,
    battery_score: 0.8 * (batteryPct / 100),
    priority,
    priority_score: 0.5 * (priority / 100),
    busy_penalty: 0,
  };
}

// ── Frame script ──────────────────────────────────────────────────────────────

export type DemoFrame =
  | { at: number; kind: "unit"; data: UnitState }
  | { at: number; kind: "anomaly"; data: AnomalyView }
  | { at: number; kind: "allocation"; data: AllocationDecision }
  | { at: number; kind: "runtime"; data: MissionRuntimeEvent }
  | { at: number; kind: "payload"; data: PayloadEvent }
  | { at: number; kind: "mission"; data: MissionView };

const iso = (at: number) => new Date(TAKE_A.t0 + at).toISOString();

function lerpGeo(from: Geo, to: Geo, t: number, altM: number): Geo {
  const k = Math.max(0, Math.min(1, t));
  return {
    lat: from.lat + (to.lat - from.lat) * k,
    lon: from.lon + (to.lon - from.lon) * k,
    alt_m: altM,
  };
}

type Leg = { from: number; to: number; a: Geo; b: Geo; state: UnitState["fsm_state"]; alt: number };

function positionAt(legs: Leg[], home: Geo, atS: number): { geo: Geo; state: UnitState["fsm_state"] } {
  let geo = home;
  let state: UnitState["fsm_state"] = "DOCKED";
  for (const leg of legs) {
    if (atS < leg.from) break;
    const k = atS >= leg.to ? 1 : (atS - leg.from) / (leg.to - leg.from);
    const altitude =
      leg.state === "EN_ROUTE"
        ? leg.alt * Math.min(1, k * 3) // climb-out
        : leg.state === "RTL"
          ? leg.alt * (1 - k * 0.9) // descent
          : leg.alt; // holding station
    geo = lerpGeo(leg.a, leg.b, k, altitude);
    state = leg.state;
  }
  return { geo, state };
}

const LEGS_002: Leg[] = [
  { from: 3, to: 19, a: HOME_002, b: OBJECTIVE_ONE, state: "EN_ROUTE", alt: CRUISE_ALT_M },
  { from: 19, to: 42, a: OBJECTIVE_ONE, b: OBJECTIVE_ONE, state: "ON_STATION", alt: CRUISE_ALT_M },
  { from: 42, to: 56, a: OBJECTIVE_ONE, b: HOME_002, state: "RTL", alt: CRUISE_ALT_M },
  { from: 56, to: 62, a: HOME_002, b: HOME_002, state: "DOCKED", alt: 0 },
];

const LEGS_001: Leg[] = [
  { from: 26, to: 40, a: HOME_001, b: OBJECTIVE_TWO, state: "EN_ROUTE", alt: CRUISE_ALT_M },
  { from: 40, to: 60, a: OBJECTIVE_TWO, b: OBJECTIVE_TWO, state: "ON_STATION", alt: CRUISE_ALT_M },
  { from: 60, to: 62.7, a: OBJECTIVE_TWO, b: HOME_001, state: "RTL", alt: CRUISE_ALT_M },
];

function unitFrame(
  agentId: string,
  home: Geo,
  legs: Leg[],
  atS: number,
  missionId: string | null,
  batteryPct: number
): UnitState {
  const { geo, state } = positionAt(legs, home, atS);
  return {
    agent_id: agentId,
    vendor: "mavlink",
    model: "px4-iris-sitl",
    fsm_state: state,
    battery_pct: batteryPct,
    geo,
    current_mission_id: missionId,
    current_sector_id: null,
    link_quality: 1,
    heading_deg: agentId === "mav-002" ? 42 : 318,
    altitude_agl_m: geo.alt_m,
    dock_id: "dock-sitl-01",
    ts: iso(atS * 1000),
  };
}

function anomaly(
  id: string,
  kind: AnomalyView["kind"],
  geo: Geo,
  confidence: number,
  atS: number,
  detectedBy: string
): AnomalyView {
  return {
    id,
    kind,
    geo,
    sector_id: null,
    confidence,
    band: "verified",
    state: "verifying",
    detected_at: iso(atS * 1000),
    detected_by: detectedBy,
    verifying_agent: null,
    evidence: null,
    ts: iso(atS * 1000),
  };
}

function runtime(
  missionId: string,
  agentId: string,
  phase: string,
  atS: number,
  evidence: MissionRuntimeEvent["evidence"] = null
): MissionRuntimeEvent {
  return {
    id: `${missionId}-${phase}-${atS}`,
    mission_id: missionId,
    agent_id: agentId,
    phase,
    progress_pct: phase === "DONE" ? 100 : phase === "ON_STATION" ? 90 : 5,
    evidence,
    error: null,
    ts: iso(atS * 1000),
  };
}

function payload(
  missionId: string,
  anomalyId: string,
  agentId: string,
  kind: PayloadEvent["kind"],
  mode: PayloadEvent["execution_mode"],
  atS: number
): PayloadEvent {
  return {
    id: `${missionId}-${kind}`,
    mission_id: missionId,
    anomaly_id: anomalyId,
    action_id: `${missionId}-${kind}-action`,
    agent_id: agentId,
    kind,
    status: mode === "simulated" ? "simulated" : "confirmed",
    execution_mode: mode,
    light_on: kind === "light_on",
    speaker_active: kind === "play_message",
    message: kind === "play_message" || kind === "stop_message" ? "restricted_area" : null,
    error_code: null,
    ts: iso(atS * 1000),
  };
}

function trackTo(legs: Leg[], home: Geo, atS: number, fromS: number): Geo[] {
  const points: Geo[] = [];
  for (let t = fromS; t <= atS; t += 1) points.push(positionAt(legs, home, t).geo);
  return points;
}

/** The whole take as an ordered frame script. */
export function takeAFrames(): DemoFrame[] {
  const frames: DemoFrame[] = [];

  // Telemetry at 2 Hz, as the MAVLink adapter publishes it.
  for (let t = 0; t <= 62.5; t += 0.5) {
    const missionTwoOwned = t >= 25 ? TAKE_A.missionTwo : null;
    const missionOneOwned = t >= 2 && t < 42 ? TAKE_A.missionOne : null;
    frames.push({
      at: t * 1000,
      kind: "unit",
      data: unitFrame("mav-001", HOME_001, LEGS_001, t, missionTwoOwned, 100 - t * 0.05),
    });
    frames.push({
      at: t * 1000,
      kind: "unit",
      data: unitFrame("mav-002", HOME_002, LEGS_002, t, missionOneOwned, 100 - t * 0.12),
    });
  }

  // Mission tracks (server-side observed position history).
  for (let t = 4; t <= 62; t += 2) {
    frames.push({
      at: t * 1000,
      kind: "mission",
      data: {
        id: TAKE_A.missionOne,
        kind: "VERIFY",
        assigned_agent: TAKE_A.ownerOne,
        sector_id: null,
        phase: "en_route",
        progress_pct: 0,
        eta_s: null,
        waypoints: [OBJECTIVE_ONE],
        track: trackTo(LEGS_002, HOME_002, t, 3),
        ts: iso(t * 1000),
      },
    });
    if (t >= 27) {
      frames.push({
        at: t * 1000,
        kind: "mission",
        data: {
          id: TAKE_A.missionTwo,
          kind: "VERIFY",
          assigned_agent: TAKE_A.ownerTwo,
          sector_id: null,
          phase: "en_route",
          progress_pct: 0,
          eta_s: null,
          waypoints: [OBJECTIVE_TWO],
          track: trackTo(LEGS_001, HOME_001, t, 26),
          ts: iso(t * 1000),
        },
      });
    }
  }

  frames.push({
    at: 1_000,
    kind: "anomaly",
    data: anomaly(TAKE_A.anomalyOne, "INTRUSION", OBJECTIVE_ONE, 0.95, 1, "perimeter-cam-04"),
  });

  frames.push({
    at: 2_000,
    kind: "allocation",
    data: {
      mission_id: TAKE_A.missionOne,
      mission_kind: "VERIFY",
      anomaly_id: TAKE_A.anomalyOne,
      mode: "auction",
      eligible_units: [
        {
          agent_id: "mav-001",
          fsm_state: "DOCKED",
          battery_pct: 100,
          score: TAKE_A.scoreOneOther,
          score_breakdown: breakdown(39.9201, 100, 99),
        },
        {
          agent_id: "mav-002",
          fsm_state: "DOCKED",
          battery_pct: 100,
          score: TAKE_A.scoreOneWinner,
          score_breakdown: breakdown(38.0826, 100, 99),
        },
      ],
      excluded_units: [],
      winner_agent_id: TAKE_A.ownerOne,
      winner_score: TAKE_A.scoreOneWinner,
      ts: iso(2_000),
    },
  });

  frames.push({ at: 3_000, kind: "runtime", data: runtime(TAKE_A.missionOne, "mav-002", "EN_ROUTE", 3) });
  frames.push({
    at: 19_500,
    kind: "runtime",
    data: runtime(TAKE_A.missionOne, "mav-002", "ON_STATION", 19.5, "mavlink_mission_item_reached"),
  });

  frames.push({
    at: 20_500,
    kind: "payload",
    data: payload(TAKE_A.missionOne, TAKE_A.anomalyOne, "mav-002", "light_on", "mavlink_output_confirmed", 20.5),
  });
  frames.push({
    at: 20_800,
    kind: "payload",
    data: payload(TAKE_A.missionOne, TAKE_A.anomalyOne, "mav-002", "play_message", "simulated", 20.8),
  });

  frames.push({
    at: 24_000,
    kind: "anomaly",
    data: anomaly(TAKE_A.anomalyTwo, "HEAT_SPOT", OBJECTIVE_TWO, 0.99, 24, "thermal-array-02"),
  });

  frames.push({
    at: 25_000,
    kind: "allocation",
    data: {
      mission_id: TAKE_A.missionTwo,
      mission_kind: "VERIFY",
      anomaly_id: TAKE_A.anomalyTwo,
      mode: "auction",
      eligible_units: [
        {
          agent_id: "mav-001",
          fsm_state: "DOCKED",
          battery_pct: 100,
          score: TAKE_A.scoreTwoWinner,
          score_breakdown: breakdown(2.1099, 100, 99),
        },
      ],
      excluded_units: [
        {
          agent_id: "mav-002",
          fsm_state: "ON_STATION",
          battery_pct: 97,
          reason: "BUSY",
          active_mission_id: TAKE_A.missionOne,
        },
      ],
      winner_agent_id: TAKE_A.ownerTwo,
      winner_score: TAKE_A.scoreTwoWinner,
      ts: iso(25_000),
    },
  });

  frames.push({ at: 26_000, kind: "runtime", data: runtime(TAKE_A.missionTwo, "mav-001", "EN_ROUTE", 26) });

  frames.push({
    at: 41_000,
    kind: "payload",
    data: payload(TAKE_A.missionOne, TAKE_A.anomalyOne, "mav-002", "stop_message", "simulated", 41),
  });
  frames.push({
    at: 41_400,
    kind: "payload",
    data: payload(TAKE_A.missionOne, TAKE_A.anomalyOne, "mav-002", "light_off", "mavlink_output_confirmed", 41.4),
  });

  frames.push({
    at: 42_000,
    kind: "runtime",
    data: runtime(TAKE_A.missionOne, "mav-002", "DONE", 42, "mavlink_rtl_command_acknowledged"),
  });
  frames.push({
    at: 44_000,
    kind: "runtime",
    data: runtime(TAKE_A.missionTwo, "mav-001", "ON_STATION", 44, "mavlink_mission_item_reached"),
  });
  frames.push({
    at: 60_000,
    kind: "runtime",
    data: runtime(TAKE_A.missionTwo, "mav-001", "DONE", 60, "mavlink_rtl_command_acknowledged"),
  });

  return frames.sort((a, b) => a.at - b.at);
}

// ── Fold ──────────────────────────────────────────────────────────────────────

export type TakeSlice = {
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: AllocationDecision[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  missions: MissionView[];
  now: number;
};

/** Fold the script up to `atMs` exactly as `SwarmStateProvider` would. */
export function foldTakeA(atMs: number, frames: DemoFrame[] = takeAFrames()): TakeSlice {
  const units = new Map<string, UnitState>();
  const anomalies = new Map<string, AnomalyView>();
  const allocations = new Map<string, AllocationDecision>();
  const runtimeLatest = new Map<string, MissionRuntimeEvent>();
  const runtimeLog: MissionRuntimeEvent[] = [];
  const payloads: PayloadEvent[] = [];
  const missions = new Map<string, MissionView>();

  for (const frame of frames) {
    if (frame.at > atMs) break;
    switch (frame.kind) {
      case "unit":
        units.set(frame.data.agent_id, frame.data);
        break;
      case "anomaly":
        anomalies.set(frame.data.id, frame.data);
        break;
      case "allocation":
        allocations.set(frame.data.mission_id, frame.data);
        break;
      case "runtime":
        runtimeLatest.set(frame.data.mission_id, frame.data);
        if (!runtimeLog.some((e) => e.id === frame.data.id)) runtimeLog.push(frame.data);
        break;
      case "payload":
        if (!payloads.some((e) => e.id === frame.data.id)) payloads.push(frame.data);
        break;
      case "mission":
        missions.set(frame.data.id, frame.data);
        break;
    }
  }

  return {
    units: [...units.values()],
    anomalies: [...anomalies.values()],
    allocations: [...allocations.values()],
    missionRuntime: [...runtimeLatest.values()],
    missionRuntimeLog: runtimeLog,
    payloadEvents: payloads,
    missions: [...missions.values()],
    now: TAKE_A.t0 + atMs,
  };
}
