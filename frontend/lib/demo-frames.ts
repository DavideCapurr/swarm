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
  ExecutionGroup,
  ExecutionGroupMember,
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
  | { at: number; kind: "mission"; data: MissionView }
  | { at: number; kind: "group"; data: ExecutionGroup };

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
  executionGroups: ExecutionGroup[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  missions: MissionView[];
  now: number;
};

/** Fold any frame script up to `atMs` exactly as `SwarmStateProvider` would. */
function foldFrames(atMs: number, frames: DemoFrame[]): Omit<TakeSlice, "now"> {
  const units = new Map<string, UnitState>();
  const groups = new Map<string, ExecutionGroup>();
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
      case "group":
        groups.set(frame.data.id, frame.data);
        break;
    }
  }

  return {
    units: [...units.values()],
    anomalies: [...anomalies.values()],
    allocations: [...allocations.values()],
    executionGroups: [...groups.values()],
    missionRuntime: [...runtimeLatest.values()],
    missionRuntimeLog: runtimeLog,
    payloadEvents: payloads,
    missions: [...missions.values()],
  };
}

/** Fold take A up to `atMs`. */
export function foldTakeA(atMs: number, frames: DemoFrame[] = takeAFrames()): TakeSlice {
  return { ...foldFrames(atMs, frames), now: TAKE_A.t0 + atMs };
}

// ── Take B — SwarmOS-owned ExecutionGroup with a live member replacement ─────
//
// Development and verification only, on the same terms as take A above: this
// never reaches the live surface and anything rendered from it is stamped
// `REPLAY · RECORDED FRAMES · NOT LIVE`. It exists because the composition and
// recomposition beats are the centre of the surface and cannot otherwise be
// reviewed without a four-instance PX4 SITL bench.
//
// Provenance, stated exactly:
//
//   RECORDED — every identity and every decision below is read out of
//   `docs/bench/phase12-execution-group-live-failover.md`: the anomaly, the
//   execution group, the parent objective, the three roles, which agent held
//   each role, each child mission id, each recorded score, which agent was
//   killed and in which state, that `mav-001` was the spare SwarmOS selected,
//   the replacement child mission, the `replaces_agent_id` provenance, and the
//   evidence boundary each member completed against.
//
//   RECONSTRUCTED — the positions. The bench recorded scores, not coordinates,
//   so each agent is placed at the exact ground distance its recorded score
//   implies under the real allocator formula (`score_bid`, priority
//   `80 + int(confidence * 20)` = 99 at confidence 0.99, battery 100): 34.83 m,
//   36.37 m, 38.08 m and 39.93 m. Distance is therefore derived; the approach
//   bearing is not recorded anywhere and is chosen — see HOME_B.
//
//   SCRIPTED — the intra-take timing. The bench recorded a 7.08 s detection
//   latency and 47.51 s from kill to recovered completion; the ordering here is
//   the bench's, compressed into one 62 s take.

export const TAKE_B = {
  durationMs: 62_000,
  t0: Date.UTC(2026, 7, 15, 17, 28, 45),
  anomaly: "d3e97452bda44cbc99cd5e16d67aed2f",
  group: "4efceb04bdda4f3e88f9da18dbb158c6",
  objectiveMission: "8582edb3f2984289ab756602ac03aad5",
  requestedMembers: 3,
  primary: { role: "PRIMARY_OBSERVER", agent: "mav-004", mission: "0a224497d6384724aa3ee4043dcffc26", score: 2.2613507126 },
  secondary: { role: "SECONDARY_OBSERVER", agent: "mav-003", mission: "b9a64ed080bc47e498ea18e4d8655069", score: 2.2599093608 },
  overwatch: { role: "OVERWATCH", agent: "mav-002", mission: "3dbd3eeaee6f43d29f6498a8042990ab", score: 2.2583201001 },
  replacement: { role: "SECONDARY_OBSERVER", agent: "mav-001", mission: "a03fd8ddc5c140e89ec0eeb717296c42", score: 2.2566069734, replaces: "mav-003" },
} as const;

const OBJECTIVE_B: Geo = { lat: 47.39805, lon: 8.546, alt_m: 0 };

/** Ground distance a recorded score implies, inverting the allocator's own terms. */
function distanceFromScore(score: number, batteryPct: number, priority: number): number {
  const distanceScore = score - 0.8 * (batteryPct / 100) - 0.5 * (priority / 100);
  return (1 / distanceScore - 1) * 1000;
}

/** Place a point `distanceM` from `from` along a compass bearing. */
function offsetGeo(from: Geo, distanceM: number, bearingDeg: number): Geo {
  const rad = (bearingDeg * Math.PI) / 180;
  const dLat = (distanceM * Math.cos(rad)) / 111_320;
  const dLon =
    (distanceM * Math.sin(rad)) / (111_320 * Math.cos((from.lat * Math.PI) / 180));
  return { lat: from.lat + dLat, lon: from.lon + dLon, alt_m: 0 };
}

const PRIORITY_B = 99; // 80 + int(0.99 * 20)

/**
 * Approach bearings.
 *
 * Free parameters: the bench recorded scores, not coordinates, so the distance
 * from the objective is pinned by `distanceFromScore` and the direction is not.
 *
 * The four launch points sit south of the objective across a 51° arc. Two
 * things follow, and both are the reason for the choice. The aircraft are far
 * enough apart at launch to read as four aircraft rather than one stack of
 * darts. And the transit runs along the frame's short axis, so the journey is
 * the long dimension of what the camera holds instead of a short hop into the
 * middle of a ring — the objective is somewhere the fleet goes, not somewhere
 * it is already standing.
 */
const HOME_B: Record<string, Geo> = {
  "mav-004": offsetGeo(OBJECTIVE_B, distanceFromScore(TAKE_B.primary.score, 100, PRIORITY_B), 155),
  "mav-003": offsetGeo(OBJECTIVE_B, distanceFromScore(TAKE_B.secondary.score, 100, PRIORITY_B), 172),
  "mav-002": offsetGeo(OBJECTIVE_B, distanceFromScore(TAKE_B.overwatch.score, 100, PRIORITY_B), 189),
  "mav-001": offsetGeo(OBJECTIVE_B, distanceFromScore(TAKE_B.replacement.score, 100, PRIORITY_B), 206),
};

const isoB = (at: number) => new Date(TAKE_B.t0 + at).toISOString();

function groupMember(
  agentId: string,
  role: string,
  missionId: string,
  state: ExecutionGroupMember["state"],
  score: number,
  atS: number,
  replaces: string | null = null
): ExecutionGroupMember {
  return {
    agent_id: agentId,
    role,
    mission_id: missionId,
    state,
    score,
    score_breakdown: {},
    replaces_agent_id: replaces,
    ts: isoB(atS * 1000),
  };
}

function groupFrame(
  state: ExecutionGroup["state"],
  members: ExecutionGroupMember[],
  atS: number
): ExecutionGroup {
  return {
    id: TAKE_B.group,
    objective_mission_id: TAKE_B.objectiveMission,
    objective_kind: "COOPERATIVE_VERIFY",
    anomaly_id: TAKE_B.anomaly,
    requested_members: TAKE_B.requestedMembers,
    members,
    state,
    failure_reason: null,
    ts: isoB(atS * 1000),
  };
}

function unitB(
  agentId: string,
  atS: number,
  missionId: string | null,
  legs: Leg[],
  batteryPct: number,
  headingDeg: number,
  fixedState?: UnitState["fsm_state"]
): UnitState {
  const { geo, state } = positionAt(legs, HOME_B[agentId], atS);
  return {
    agent_id: agentId,
    vendor: "mavlink",
    model: "px4-iris-sitl",
    fsm_state: fixedState ?? state,
    battery_pct: batteryPct,
    geo,
    current_mission_id: missionId,
    current_sector_id: null,
    link_quality: fixedState === "OFFLINE" ? 0 : 1,
    heading_deg: headingDeg,
    altitude_agl_m: geo.alt_m,
    dock_id: "dock-sitl-01",
    ts: isoB(atS * 1000),
  };
}

function runtimeB(
  missionId: string,
  agentId: string,
  phase: string,
  atS: number,
  evidence: MissionRuntimeEvent["evidence"] = null,
  error: string | null = null
): MissionRuntimeEvent {
  return {
    id: `${missionId}-${phase}-${atS}`,
    mission_id: missionId,
    agent_id: agentId,
    phase,
    progress_pct: phase === "DONE" ? 100 : phase === "ON_STATION" ? 90 : 5,
    evidence,
    error,
    ts: isoB(atS * 1000),
  };
}

function missionB(missionId: string, agentId: string, legs: Leg[], atS: number): MissionView {
  const track: Geo[] = [];
  for (let t = 0; t <= atS; t += 1.5) {
    track.push(positionAt(legs, HOME_B[agentId], t).geo);
  }
  return {
    id: missionId,
    kind: "VERIFY",
    assigned_agent: agentId,
    sector_id: null,
    phase: "en_route",
    progress_pct: 0,
    eta_s: null,
    waypoints: [OBJECTIVE_B],
    track,
    ts: isoB(atS * 1000),
  };
}

/** Bearing from an agent's home toward the objective, so darts point where they fly. */
function headingToObjective(agentId: string): number {
  const home = HOME_B[agentId];
  const dLat = OBJECTIVE_B.lat - home.lat;
  const dLon =
    (OBJECTIVE_B.lon - home.lon) * Math.cos((home.lat * Math.PI) / 180);
  return (((Math.atan2(dLon, dLat) * 180) / Math.PI) + 360) % 360;
}

const legsFor = (agentId: string, start: number, arrive: number, rtl: number): Leg[] => [
  { from: start, to: arrive, a: HOME_B[agentId], b: OBJECTIVE_B, state: "EN_ROUTE", alt: CRUISE_ALT_M },
  { from: arrive, to: rtl, a: OBJECTIVE_B, b: OBJECTIVE_B, state: "ON_STATION", alt: CRUISE_ALT_M },
  { from: rtl, to: rtl + 12, a: OBJECTIVE_B, b: HOME_B[agentId], state: "RTL", alt: CRUISE_ALT_M },
];

const LEGS_B: Record<string, Leg[]> = {
  "mav-004": legsFor("mav-004", 8, 30, 44),
  "mav-003": legsFor("mav-003", 8, 31, 44),
  "mav-002": legsFor("mav-002", 8, 32, 46),
  // The replacement launches only when SwarmOS selects it.
  "mav-001": legsFor("mav-001", 24, 42, 48),
};

/** `mav-003` is killed at T+20; its last reported position is held from there. */
const KILL_AT_S = 20;

export function takeBFrames(): DemoFrame[] {
  const frames: DemoFrame[] = [];
  const roster = [
    { agent: TAKE_B.primary.agent, mission: TAKE_B.primary.mission, from: 8 },
    { agent: TAKE_B.secondary.agent, mission: TAKE_B.secondary.mission, from: 8 },
    { agent: TAKE_B.overwatch.agent, mission: TAKE_B.overwatch.mission, from: 8 },
    { agent: TAKE_B.replacement.agent, mission: TAKE_B.replacement.mission, from: 24 },
  ];

  // Telemetry, at 1 Hz — the shape the Console actually receives.
  for (let t = 0; t <= 62; t += 1) {
    for (const entry of roster) {
      const dead = entry.agent === "mav-003" && t > KILL_AT_S;
      const sample = dead ? KILL_AT_S : t;
      frames.push({
        at: t * 1000,
        kind: "unit",
        data: unitB(
          entry.agent,
          sample,
          t >= entry.from ? entry.mission : null,
          LEGS_B[entry.agent],
          Math.max(58, 100 - t * 0.35),
          headingToObjective(entry.agent),
          dead ? "OFFLINE" : undefined
        ),
      });
    }
  }

  frames.push({
    at: 6_000,
    kind: "anomaly",
    data: {
      ...anomaly(TAKE_B.anomaly, "INTRUSION", OBJECTIVE_B, 0.99, 6, "mav-004"),
      ts: isoB(6_000),
      detected_at: isoB(6_000),
    },
  });

  // SwarmOS composes the group: three required roles, three of four agents
  // selected, one left as spare. The parent objective takes no physical award.
  const initialMembers = [
    groupMember(TAKE_B.primary.agent, TAKE_B.primary.role, TAKE_B.primary.mission, "ASSIGNED", TAKE_B.primary.score, 7),
    groupMember(TAKE_B.secondary.agent, TAKE_B.secondary.role, TAKE_B.secondary.mission, "ASSIGNED", TAKE_B.secondary.score, 7),
    groupMember(TAKE_B.overwatch.agent, TAKE_B.overwatch.role, TAKE_B.overwatch.mission, "ASSIGNED", TAKE_B.overwatch.score, 7),
  ];
  frames.push({ at: 7_000, kind: "group", data: groupFrame("FORMING", initialMembers, 7) });

  const activeMembers = initialMembers.map((member) => ({ ...member, state: "ACTIVE" as const }));
  frames.push({ at: 8_500, kind: "group", data: groupFrame("ACTIVE", activeMembers, 8.5) });

  for (const entry of roster.slice(0, 3)) {
    frames.push({ at: 8_600, kind: "runtime", data: runtimeB(entry.mission, entry.agent, "EN_ROUTE", 8.6) });
  }

  // The failure: a real process-level loss while the member was EN_ROUTE.
  frames.push({
    at: 21_000,
    kind: "runtime",
    data: runtimeB(
      TAKE_B.secondary.mission,
      TAKE_B.secondary.agent,
      "FAILED",
      21,
      null,
      "MAVLinkCommandError: COMMAND_LONG 20 timed out waiting for COMMAND_ACK"
    ),
  });
  frames.push({
    at: 21_200,
    kind: "group",
    data: groupFrame(
      "DEGRADED",
      [
        activeMembers[0],
        { ...activeMembers[1], state: "FAILED", ts: isoB(21_200) },
        activeMembers[2],
      ],
      21.2
    ),
  });

  // SwarmOS selects the unused spare for the same logical role. No surviving
  // agent elected it; the provenance is `replaces_agent_id`.
  const restored = [
    activeMembers[0],
    { ...activeMembers[1], state: "REPLACED" as const, ts: isoB(23_000) },
    activeMembers[2],
    groupMember(
      TAKE_B.replacement.agent,
      TAKE_B.replacement.role,
      TAKE_B.replacement.mission,
      "ACTIVE",
      TAKE_B.replacement.score,
      23,
      TAKE_B.replacement.replaces
    ),
  ];
  frames.push({ at: 23_000, kind: "group", data: groupFrame("ACTIVE", restored, 23) });
  frames.push({
    at: 24_000,
    kind: "runtime",
    data: runtimeB(TAKE_B.replacement.mission, TAKE_B.replacement.agent, "EN_ROUTE", 24),
  });

  // Arrival is accepted only on final MISSION_ITEM_REACHED, for every member.
  frames.push({ at: 30_000, kind: "runtime", data: runtimeB(TAKE_B.primary.mission, TAKE_B.primary.agent, "ON_STATION", 30, "mavlink_mission_item_reached") });
  frames.push({ at: 32_000, kind: "runtime", data: runtimeB(TAKE_B.overwatch.mission, TAKE_B.overwatch.agent, "ON_STATION", 32, "mavlink_mission_item_reached") });
  frames.push({ at: 42_000, kind: "runtime", data: runtimeB(TAKE_B.replacement.mission, TAKE_B.replacement.agent, "ON_STATION", 42, "mavlink_mission_item_reached") });

  // Bounded presence response. The light is confirmed at the PX4 output; the
  // speaker stays explicitly simulated.
  frames.push({
    at: 33_000,
    kind: "payload",
    data: payload(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "light_on", "mavlink_output_confirmed", 33),
  });
  frames.push({
    at: 34_000,
    kind: "payload",
    data: payload(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "play_message", "simulated", 34),
  });
  frames.push({
    at: 44_000,
    kind: "payload",
    data: payload(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "stop_message", "simulated", 44),
  });
  frames.push({
    at: 44_500,
    kind: "payload",
    data: payload(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "light_off", "mavlink_output_confirmed", 44.5),
  });

  // Completion, each on an acknowledged RTL, then the aggregate group.
  frames.push({ at: 46_000, kind: "runtime", data: runtimeB(TAKE_B.primary.mission, TAKE_B.primary.agent, "DONE", 46, "mavlink_rtl_command_acknowledged") });
  frames.push({ at: 47_000, kind: "runtime", data: runtimeB(TAKE_B.overwatch.mission, TAKE_B.overwatch.agent, "DONE", 47, "mavlink_rtl_command_acknowledged") });
  frames.push({ at: 49_000, kind: "runtime", data: runtimeB(TAKE_B.replacement.mission, TAKE_B.replacement.agent, "DONE", 49, "mavlink_rtl_command_acknowledged") });
  frames.push({
    at: 50_000,
    kind: "group",
    data: groupFrame(
      "COMPLETED",
      restored.map((member) =>
        member.state === "REPLACED" ? member : { ...member, state: "COMPLETED" as const }
      ),
      50
    ),
  });

  // Observed tracks, sampled so the map has a path to draw.
  for (let t = 10; t <= 62; t += 2) {
    for (const entry of roster) {
      if (t < entry.from) continue;
      const sample = entry.agent === "mav-003" && t > KILL_AT_S ? KILL_AT_S : t;
      frames.push({
        at: t * 1000,
        kind: "mission",
        data: missionB(entry.mission, entry.agent, LEGS_B[entry.agent], sample),
      });
    }
  }

  return frames.sort((a, b) => a.at - b.at);
}

/** Fold take B up to `atMs`, exactly as `SwarmStateProvider` would. */
export function foldTakeB(atMs: number, frames: DemoFrame[] = takeBFrames()): TakeSlice {
  const slice = foldFrames(atMs, frames);
  return { ...slice, now: TAKE_B.t0 + atMs };
}
