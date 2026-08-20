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

/** Compass bearing from one point to another. 0 is north. */
function bearingDeg(from: Geo, to: Geo): number {
  const dLat = to.lat - from.lat;
  const dLon = (to.lon - from.lon) * Math.cos((from.lat * Math.PI) / 180);
  return ((Math.atan2(dLon, dLat) * 180) / Math.PI + 360) % 360;
}

function samePoint(a: Geo, b: Geo): boolean {
  return a.lat === b.lat && a.lon === b.lon;
}

/** Rotate `from` a fraction `k` of the way to `to`, the short way round. */
function turnToward(from: number, to: number, k: number): number {
  const delta = ((to - from + 540) % 360) - 180;
  return (from + delta * k + 360) % 360;
}

/** Seconds an aircraft takes to come round onto a new leg. */
const TURN_S = 2.5;

function positionAt(
  legs: Leg[],
  home: Geo,
  atS: number
): { geo: Geo; state: UnitState["fsm_state"]; headingDeg: number } {
  let geo = home;
  let state: UnitState["fsm_state"] = "DOCKED";
  // Heading follows the leg being flown, so an aircraft on RTL points at the
  // home it is returning to rather than at the objective it has left. Before
  // launch it already faces its first leg, which is what a dart on a pad
  // should do. Turns are taken over TURN_S rather than snapped: a 180 that
  // happens between two 1 Hz samples reads as a glitch, not a turn.
  let headingDeg = legs.length > 0 ? bearingDeg(legs[0].a, legs[0].b) : 0;
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
    // A leg that holds station has no direction of travel, so it leaves the
    // heading where the last flown leg put it.
    if (!samePoint(leg.a, leg.b)) {
      const turn = Math.min(1, Math.max(0, (atS - leg.from) / TURN_S));
      headingDeg = turnToward(headingDeg, bearingDeg(leg.a, leg.b), turn);
    }
  }
  return { geo, state, headingDeg };
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
  const { geo, state, headingDeg } = positionAt(legs, home, atS);
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
    heading_deg: headingDeg,
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
//   RECONSTRUCTED — the positions. The bench recorded scores, not coordinates.
//   Each agent's distance from the objective is inverted out of its recorded
//   score under the real allocator formula (`score_bid`, priority
//   `80 + int(confidence * 20)` = 99 at confidence 0.99, battery 100), giving
//   34.83 m, 36.37 m, 38.08 m and 39.93 m, scaled by a common factor for
//   legibility (see PRESENTATION_SCALE) and then averaged into one shared dock
//   distance, because the real deployment launches every aircraft from one
//   physical pad — see DOCK_B. The four individual distances therefore do not
//   survive into the geometry; what does is their ranking, which is carried by
//   the roles SwarmOS actually assigned, not by where a dart sits on the map.
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

/**
 * Presentation scale for take B's geometry.
 *
 * The recorded scores imply ground distances of 34.8 m to 39.9 m — four SITL
 * endpoints effectively sharing one field. Rendered honestly that is a scene
 * about 40 m across, in which nothing travels anywhere: the camera has nothing
 * to open onto and nothing to close in on, and the transit is over before it
 * reads as a transit.
 *
 * So the distances are multiplied by a common factor. What that preserves is
 * the thing the allocator decision actually turned on — the *ranking* and the
 * exact ratios between the four bids, so `mav-004` is still nearest and won
 * `PRIMARY_OBSERVER`, and `mav-001` is still furthest and was left spare. What
 * it gives up is the absolute distance, which becomes a stated presentation
 * choice rather than a derivation.
 *
 * Nothing operational moves with it. Who held which role, who was excluded, who
 * replaced whom, and what evidence closed each child mission are all recorded
 * facts and are untouched.
 */
const PRESENTATION_SCALE = 6;

/** Ground distance a recorded score implies, inverting the allocator's own terms. */
function distanceFromScore(score: number, batteryPct: number, priority: number): number {
  const distanceScore = score - 0.8 * (batteryPct / 100) - 0.5 * (priority / 100);
  return (1 / distanceScore - 1) * 1000 * PRESENTATION_SCALE;
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
 * The dock.
 *
 * The real deployment this take stands in for launches every aircraft from one
 * physical pad — every scenario YAML gives `n_drones` a single shared
 * `dock_offset_m`, and the earlier draft of this take, which put each aircraft
 * on its own bearing at its own distance, drew four independent sites instead
 * of one fleet. That was a demo fiction the architecture does not have.
 *
 * `DOCK_B` sits south of the objective at the *average* of the four ground
 * distances the recorded scores imply — an honest single number derived from
 * real data, not picked for effect. Each aircraft's exact pad is a small,
 * fixed offset from that one point (see `DOCK_SLOT_M`), the way four aircraft
 * actually sit on adjacent charging slots of one dock.
 */
const RECORDED_DISTANCES_M = [
  distanceFromScore(TAKE_B.primary.score, 100, PRIORITY_B),
  distanceFromScore(TAKE_B.secondary.score, 100, PRIORITY_B),
  distanceFromScore(TAKE_B.overwatch.score, 100, PRIORITY_B),
  distanceFromScore(TAKE_B.replacement.score, 100, PRIORITY_B),
];
const DOCK_DISTANCE_M =
  RECORDED_DISTANCES_M.reduce((a, b) => a + b, 0) / RECORDED_DISTANCES_M.length;
const DOCK_B = offsetGeo(OBJECTIVE_B, DOCK_DISTANCE_M, 180);

/** Metres east of `DOCK_B`, one slot per aircraft, 3 m apart on the pad. */
const DOCK_SLOT_M: Record<string, number> = {
  "mav-004": -4.5,
  "mav-003": -1.5,
  "mav-002": 1.5,
  "mav-001": 4.5,
};

function dockSlot(eastM: number): Geo {
  return offsetGeo(DOCK_B, Math.abs(eastM), eastM >= 0 ? 90 : 270);
}

const HOME_B: Record<string, Geo> = {
  "mav-004": dockSlot(DOCK_SLOT_M["mav-004"]),
  "mav-003": dockSlot(DOCK_SLOT_M["mav-003"]),
  "mav-002": dockSlot(DOCK_SLOT_M["mav-002"]),
  "mav-001": dockSlot(DOCK_SLOT_M["mav-001"]),
};

/**
 * The altitude ladder SwarmOS actually builds.
 *
 * `_cooperative_verify_plans` decomposes one objective into child VERIFY
 * missions against the *same* geo at `base_altitude_m + altitude_step_m * idx`
 * — 40 m, 55 m, 70 m by default. Separation between the roles is vertical, not
 * lateral, which is why the map lifts each executor off its ground mark and why
 * the height is stated next to the role rather than filed under telemetry.
 *
 * A replacement inherits the altitude of the role it takes over, not of the
 * machine it replaces.
 */
const ROLE_ALT_M: Record<string, number> = {
  "mav-004": 40, // PRIMARY_OBSERVER
  "mav-003": 55, // SECONDARY_OBSERVER
  "mav-001": 55, // SECONDARY_OBSERVER, after replacement
  "mav-002": 70, // OVERWATCH
};

const legsFor = (agentId: string, start: number, arrive: number, rtl: number): Leg[] => {
  const alt = ROLE_ALT_M[agentId] ?? CRUISE_ALT_M;
  return [
    { from: start, to: arrive, a: HOME_B[agentId], b: OBJECTIVE_B, state: "EN_ROUTE", alt },
    { from: arrive, to: rtl, a: OBJECTIVE_B, b: OBJECTIVE_B, state: "ON_STATION", alt },
    { from: rtl, to: rtl + 12, a: OBJECTIVE_B, b: HOME_B[agentId], state: "RTL", alt },
  ];
};

const LEGS_B: Record<string, Leg[]> = {
  "mav-004": legsFor("mav-004", 8, 30, 44),
  "mav-003": legsFor("mav-003", 8, 31, 44),
  "mav-002": legsFor("mav-002", 8, 32, 46),
  // The replacement launches only when SwarmOS selects it.
  "mav-001": legsFor("mav-001", 24, 42, 48),
};

/** `mav-003` is killed at T+20; its last reported position is held from there. */
const KILL_AT_S = 20;

/**
 * The hero beat — composition, a live member failure, the central replacement
 * of the vacated role, the bounded response, and completion.
 *
 * Extracted rather than copied so take C can show the same beat instead of a
 * second script of it. Every identity, score and intra-take timing below is
 * take B's and is unchanged: the failure at T+21 and the replacement at T+23
 * are the frames this surface has been verified against most carefully, and
 * two copies of them would eventually disagree.
 *
 * `t0` is the take's own wall clock. It is the only thing that varies between
 * the takes sharing this beat — the frames, their offsets and their content are
 * identical. Frames are appended to `frames`; the caller sorts.
 */
function pushHeroGroupFrames(frames: DemoFrame[], t0: number): void {
  const isoB = (at: number) => new Date(t0 + at).toISOString();

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
    fixedState?: UnitState["fsm_state"]
  ): UnitState {
    const { geo, state, headingDeg } = positionAt(legs, HOME_B[agentId], atS);
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

  /** `payload()` above stamps `ts` off `TAKE_A.t0`; this take runs on `TAKE_B.t0`. */
  function payloadB(
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
      ts: isoB(atS * 1000),
    };
  }

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
          dead ? "OFFLINE" : undefined
        ),
      });
    }
  }

  // The detection that starts everything. Shaped exactly as the runtime ships
  // it — `AnomalyView.evidence` with source, sensor, label, score and the
  // server's confidence-bound headline — and flagged `simulated`, because on
  // this take the triggering signal is injected on the bus rather than read off
  // a sensor. The Console reads that flag; it does not decide it.
  frames.push({
    at: 6_000,
    kind: "anomaly",
    data: {
      ...anomaly(TAKE_B.anomaly, "INTRUSION", OBJECTIVE_B, 0.99, 6, "mav-004"),
      ts: isoB(6_000),
      detected_at: isoB(6_000),
      evidence: {
        source: "drone_cv",
        sensor: "RGB",
        label: "person",
        metric: "score",
        value: 0.99,
        baseline: null,
        unit: null,
        headline:
          "Elevated anomaly — onboard CV classified a person at 0.99 confidence. Sector requires verification.",
        simulated: true,
      },
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
    data: payloadB(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "light_on", "mavlink_output_confirmed", 33),
  });
  frames.push({
    at: 34_000,
    kind: "payload",
    data: payloadB(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "play_message", "simulated", 34),
  });
  frames.push({
    at: 44_000,
    kind: "payload",
    data: payloadB(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "stop_message", "simulated", 44),
  });
  frames.push({
    at: 44_500,
    kind: "payload",
    data: payloadB(TAKE_B.primary.mission, TAKE_B.anomaly, TAKE_B.primary.agent, "light_off", "mavlink_output_confirmed", 44.5),
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
}

export function takeBFrames(): DemoFrame[] {
  const frames: DemoFrame[] = [];
  pushHeroGroupFrames(frames, TAKE_B.t0);
  return frames.sort((a, b) => a.at - b.at);
}

/** Fold take B up to `atMs`, exactly as `SwarmStateProvider` would. */
export function foldTakeB(atMs: number, frames: DemoFrame[] = takeBFrames()): TakeSlice {
  const slice = foldFrames(atMs, frames);
  return { ...slice, now: TAKE_B.t0 + atMs };
}

// ── Take C — reinforcement, at fleet scale ────────────────────────────────────
//
// Development and verification only, on exactly the terms of takes A and B:
// this never reaches the live surface, `/demo/intrusion` never sees it, and
// anything rendered from it is stamped `REPLAY · RECORDED FRAMES · NOT LIVE`.
//
// Take C exists because no other take shows every layer of the architecture at
// once. A proves SwarmOS holds more than one objective at a time. B proves it
// composes a group, loses a member and replaces it centrally. Phase 1
// (`core/swarm_orchestrator/execution_groups.py`) and phase 2 (`lib/authority.ts`
// `groupSwarms`) added a third layer neither take exercises: an objective SwarmOS
// can only partly serve at first, and a second `ExecutionGroup` — a second swarm,
// never extra members on the first — reinforcing it once capacity returns. Take C
// is the cut that proves that layer, inside a fleet large enough for "central
// authority" to be a claim worth making, alongside a second objective SwarmOS
// holds concurrently.
//
// Provenance, stated exactly:
//
//   RECORDED — the failover inside the reinforcement beat. `mav-003` fails at
//   T+21 while `SECONDARY_OBSERVER`, and SwarmOS replaces it with `mav-001` at
//   T+23: the agents, the roles, the child mission ids, the scores and the
//   failure/recovery evidence strings are all read from `TAKE_B`'s own constants
//   below, which are themselves
//   `docs/bench/phase12-execution-group-live-failover.md`, unchanged and not
//   retimed. What is NOT recorded is which group each agent sits in or when
//   each group was dispatched — see SCRIPTED.
//
//   SCRIPTED — the composition this take wires that recorded beat into, and it
//   is worth being blunt about the scope of that word here. The bench ran one
//   group of three, composed at once. This take never happened on a bench:
//   SwarmOS composes a group of two (`PRIMARY_OBSERVER` + `OVERWATCH`) under the
//   three roles the objective asked for, holds it under strength and tight over
//   the objective, then — once capacity frees up — dispatches a *second* group
//   carrying `reinforces_group_id` for the missing `SECONDARY_OBSERVER` role.
//   `mav-003` is that reinforcement's first member, and its recorded failure and
//   `mav-001`'s recorded replacement both happen inside the second group, not
//   the first. Every station point, the widening leg each already-stationed
//   subunit flies when the reinforcement is dispatched, the dispatch timing, and
//   the stated cruise speed are presentation values chosen to fit the fixed
//   T+21/T+23 beat into a legible take — not decoded from any planner field.
//   `shortfall_reinforcement_policy` is real, orchestrator-test-validated code
//   that would make a matching call given matching input (`docs/STATUS.md`), but
//   no run — bench or orchestrator test — produced *this* timing; it is scripted
//   to show the policy's outcome, not a replay of it. The anomaly, the
//   objective/group ids and the second objective's identifiers are likewise made
//   up rather than borrowed from a recorded run, for the same reason the thirty
//   reserve executors below are: reusing a recorded id for a scripted event would
//   misattribute real data. The thirty reserve executors themselves — their ids,
//   headings and batteries — are `dockedFleet`'s presentation values; no bench
//   ever ran thirty-four aircraft. They sit DOCKED on the one shared pad for the
//   whole take — the same pad every hero subunit launches from — which is the
//   one state that needs no flight data to be true of them.
//
//   COMPUTED — the second objective's allocation. The bids are not typed in:
//   `scoreBid` is the real allocator formula (`core/swarm_core/allocator.py`
//   `::score_bid`, priority `80 + int(confidence * 20)`), applied to the real
//   distances between the scripted positions, and the winner is the argmax over
//   it. The numbers are therefore illustrative in their inputs and honest in
//   their arithmetic.

/**
 * The reserve fleet.
 *
 * Every executor launches from the one physical pad — that is what the real
 * deployment does, it is why `DOCK_B` exists, and a demo that scattered thirty
 * aircraft across the site to look impressive would be drawing an architecture
 * SwarmOS does not have. So the reserve sits *on* `DOCK_B`, at the pad itself,
 * and the map states it as a dock holding capacity rather than as thirty darts
 * piled on one point.
 *
 * Ids continue the hero fleet's numbering (`mav-005` up), so nothing collides
 * with the four recorded aircraft. No RNG anywhere: a recorded take has to
 * render the same way twice.
 */
const RESERVE_FLEET_SIZE = 30;

export type DockedAgent = {
  agentId: string;
  home: Geo;
  headingDeg: number;
  batteryPct: number;
};

export function dockedFleet(dock: Geo, count = RESERVE_FLEET_SIZE): DockedAgent[] {
  const out: DockedAgent[] = [];
  for (let i = 1; i <= count; i += 1) {
    out.push({
      agentId: `mav-${String(i + 4).padStart(3, "0")}`,
      home: dock,
      // Aircraft on a pad do not all face one way. Co-prime step, so the spread
      // is deterministic and every agent gets a distinct heading.
      headingDeg: (137 * i) % 360,
      // 13 and 30 are co-prime, so every agent gets a distinct charge level and
      // the allocator's argmax over equal distances has a single answer rather
      // than a tie broken by array order.
      batteryPct: 88 + ((i * 13) % 30) * 0.3,
    });
  }
  return out;
}

const RESERVE_C = dockedFleet(DOCK_B);

// ── The reinforced objective ──────────────────────────────────────────────────
//
// Swarm 01 composes under strength, holds tight, and is reinforced by swarm 02
// once capacity frees up. The formation widens to make room, the recorded T+21
// failure and T+23 replacement land inside that wide disposition, and both
// swarms recover before the objective closes. See the take C header above for
// exactly what is RECORDED, SCRIPTED and COMPUTED here.

/** Made up, deterministically, never lifted from a bench run — see the header. */
const REINFORCE_ANOMALY = "f4a1c9d370eb4a2c8f0e5b6d3a19c7e2";
const REINFORCE_OBJECTIVE_MISSION = "9c2e6a8b1d4f4e7fa0c3b5d8e1f2a4c6";
const REINFORCE_SWARM_A_GROUP = "1e7b3c9a5f2d4e6b8a0c1d3e5f7a9b2c";
const REINFORCE_SWARM_B_GROUP = "5d8f2a4c6e0b3d7f9a1c4e6b8d0f2a5c";

/**
 * Cruise, in metres per second. SCRIPTED, on the same terms as `SWEEP_CRUISE_MS`
 * below: it sets how long composition, reinforcement and the widening leg take,
 * and it is chosen so the whole beat fits before the fixed T+21 failure. Nothing
 * operational depends on it.
 */
const REINFORCE_CRUISE_MPS = 40;

/** Flat-earth planar distance, metres — the same approximation `offsetGeo` uses. */
function metresBetween(a: Geo, b: Geo): number {
  const dLat = (b.lat - a.lat) * 111_320;
  const dLon = (b.lon - a.lon) * 111_320 * Math.cos((a.lat * Math.PI) / 180);
  return Math.hypot(dLat, dLon);
}

/** Seconds to fly `from` → `to` at `REINFORCE_CRUISE_MPS`, plus spool-up. */
function reinforceTransitS(from: Geo, to: Geo, overheadS = 2): number {
  return overheadS + metresBetween(from, to) / REINFORCE_CRUISE_MPS;
}

/**
 * Station points. SCRIPTED presentation geometry — see the header. Tight holds
 * `PRIMARY_OBSERVER` and `OVERWATCH` close over the objective while swarm 01
 * serves alone; wide is the disposition the combined force re-stations into,
 * clearly wider than tight's ~36 m span so the expansion reads as a real change
 * rather than a rounding error.
 */
const REINFORCE_TIGHT_PRIMARY = offsetEN(OBJECTIVE_B, -18, 8);
const REINFORCE_TIGHT_OVERWATCH = offsetEN(OBJECTIVE_B, 18, 8);
const REINFORCE_WIDE_PRIMARY = offsetEN(OBJECTIVE_B, -40, 15);
const REINFORCE_WIDE_OVERWATCH = offsetEN(OBJECTIVE_B, 40, 15);
const REINFORCE_WIDE_SECONDARY = offsetEN(OBJECTIVE_B, 0, -25);

// Beat timing, in take-seconds. Composition and dispatch are scripted; T+21 and
// T+23 are the two that are not — see `REINFORCE_FAIL_AT_S`/`REINFORCE_REPLACED_AT_S`.
//
// The hero objective must compose *after* the sweep (`SWEEP` below composes at
// t=2.5s): focus follows the newest active objective, and if the hero composed
// first the sweep would outrank it and hold the camera through the failover.
const REINFORCE_DETECT_S = 2.5;
const REINFORCE_FORM_S = 3;
const REINFORCE_ACTIVE_S = 3.5;
const REINFORCE_LAUNCH_PRIMARY_S = 4;
const REINFORCE_LAUNCH_OVERWATCH_S = 4.5;
const REINFORCE_ARRIVE_TIGHT_PRIMARY_S =
  REINFORCE_LAUNCH_PRIMARY_S + reinforceTransitS(HOME_B["mav-004"], REINFORCE_TIGHT_PRIMARY);
const REINFORCE_ARRIVE_TIGHT_OVERWATCH_S =
  REINFORCE_LAUNCH_OVERWATCH_S + reinforceTransitS(HOME_B["mav-002"], REINFORCE_TIGHT_OVERWATCH);

/** Capacity frees up; SwarmOS dispatches swarm 02. */
const REINFORCE_DISPATCH_S = 14.5;
const REINFORCE_SWARM_B_ACTIVE_S = 15.5;
const REINFORCE_LAUNCH_SECONDARY_S = 16;
/** The already-stationed subunits begin their second ON_STATION leg, tight → wide. */
const REINFORCE_REPOSITION_PRIMARY_S = 16;
const REINFORCE_REPOSITION_OVERWATCH_S = 16.3;
const REINFORCE_WIDE_PRIMARY_SETTLE_S =
  REINFORCE_REPOSITION_PRIMARY_S + reinforceTransitS(REINFORCE_TIGHT_PRIMARY, REINFORCE_WIDE_PRIMARY, 1);
const REINFORCE_WIDE_OVERWATCH_SETTLE_S =
  REINFORCE_REPOSITION_OVERWATCH_S +
  reinforceTransitS(REINFORCE_TIGHT_OVERWATCH, REINFORCE_WIDE_OVERWATCH, 1);

/**
 * T+21 / T+23. RECORDED, not retimed: `docs/bench/phase12-execution-group-live-
 * failover.md`. `mav-003` fails while EN_ROUTE to the wide `SECONDARY_OBSERVER`
 * station — it is dispatched well before T+21 so it is genuinely mid-transit,
 * not arriving, when the recorded failure lands.
 */
const REINFORCE_FAIL_AT_S = 21;
const REINFORCE_REPLACED_AT_S = 23;

const REINFORCE_LAUNCH_REPLACEMENT_S = 24;
const REINFORCE_ARRIVE_REPLACEMENT_S =
  REINFORCE_LAUNCH_REPLACEMENT_S + reinforceTransitS(HOME_B["mav-001"], REINFORCE_WIDE_SECONDARY);

const REINFORCE_LIGHT_ON_S = 34;
const REINFORCE_PLAY_MSG_S = 34.5;
const REINFORCE_STOP_MSG_S = 44;
const REINFORCE_LIGHT_OFF_S = 44.5;

const REINFORCE_RTL_PRIMARY_S = 46;
const REINFORCE_RTL_OVERWATCH_S = 47;
const REINFORCE_RTL_REPLACEMENT_S = 49;
const REINFORCE_DONE_PRIMARY_S = 48;
const REINFORCE_DONE_OVERWATCH_S = 49;
const REINFORCE_DONE_REPLACEMENT_S = 51;
/** Each group completes once its own members have all reported DONE. */
const REINFORCE_GROUP_A_COMPLETE_S = 50;
const REINFORCE_GROUP_B_COMPLETE_S = 52;

const REINFORCE_LAND_PRIMARY_S =
  REINFORCE_RTL_PRIMARY_S + reinforceTransitS(REINFORCE_WIDE_PRIMARY, HOME_B["mav-004"], 0);
const REINFORCE_LAND_OVERWATCH_S =
  REINFORCE_RTL_OVERWATCH_S + reinforceTransitS(REINFORCE_WIDE_OVERWATCH, HOME_B["mav-002"], 0);
const REINFORCE_LAND_REPLACEMENT_S =
  REINFORCE_RTL_REPLACEMENT_S + reinforceTransitS(REINFORCE_WIDE_SECONDARY, HOME_B["mav-001"], 0);

/** Take-seconds by which every hero subunit is back on the pad. */
const REINFORCE_COMPLETED_S = Math.ceil(
  Math.max(REINFORCE_LAND_PRIMARY_S, REINFORCE_LAND_OVERWATCH_S, REINFORCE_LAND_REPLACEMENT_S)
);

const REINFORCE_LEGS_PRIMARY: Leg[] = [
  {
    from: REINFORCE_LAUNCH_PRIMARY_S,
    to: REINFORCE_ARRIVE_TIGHT_PRIMARY_S,
    a: HOME_B["mav-004"],
    b: REINFORCE_TIGHT_PRIMARY,
    state: "EN_ROUTE",
    alt: ROLE_ALT_M["mav-004"],
  },
  {
    from: REINFORCE_ARRIVE_TIGHT_PRIMARY_S,
    to: REINFORCE_REPOSITION_PRIMARY_S,
    a: REINFORCE_TIGHT_PRIMARY,
    b: REINFORCE_TIGHT_PRIMARY,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-004"],
  },
  {
    from: REINFORCE_REPOSITION_PRIMARY_S,
    to: REINFORCE_WIDE_PRIMARY_SETTLE_S,
    a: REINFORCE_TIGHT_PRIMARY,
    b: REINFORCE_WIDE_PRIMARY,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-004"],
  },
  {
    from: REINFORCE_WIDE_PRIMARY_SETTLE_S,
    to: REINFORCE_RTL_PRIMARY_S,
    a: REINFORCE_WIDE_PRIMARY,
    b: REINFORCE_WIDE_PRIMARY,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-004"],
  },
  {
    from: REINFORCE_RTL_PRIMARY_S,
    to: REINFORCE_LAND_PRIMARY_S,
    a: REINFORCE_WIDE_PRIMARY,
    b: HOME_B["mav-004"],
    state: "RTL",
    alt: ROLE_ALT_M["mav-004"],
  },
  {
    from: REINFORCE_LAND_PRIMARY_S,
    to: REINFORCE_COMPLETED_S + 2,
    a: HOME_B["mav-004"],
    b: HOME_B["mav-004"],
    state: "DOCKED",
    alt: 0,
  },
];

const REINFORCE_LEGS_OVERWATCH: Leg[] = [
  {
    from: REINFORCE_LAUNCH_OVERWATCH_S,
    to: REINFORCE_ARRIVE_TIGHT_OVERWATCH_S,
    a: HOME_B["mav-002"],
    b: REINFORCE_TIGHT_OVERWATCH,
    state: "EN_ROUTE",
    alt: ROLE_ALT_M["mav-002"],
  },
  {
    from: REINFORCE_ARRIVE_TIGHT_OVERWATCH_S,
    to: REINFORCE_REPOSITION_OVERWATCH_S,
    a: REINFORCE_TIGHT_OVERWATCH,
    b: REINFORCE_TIGHT_OVERWATCH,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-002"],
  },
  {
    from: REINFORCE_REPOSITION_OVERWATCH_S,
    to: REINFORCE_WIDE_OVERWATCH_SETTLE_S,
    a: REINFORCE_TIGHT_OVERWATCH,
    b: REINFORCE_WIDE_OVERWATCH,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-002"],
  },
  {
    from: REINFORCE_WIDE_OVERWATCH_SETTLE_S,
    to: REINFORCE_RTL_OVERWATCH_S,
    a: REINFORCE_WIDE_OVERWATCH,
    b: REINFORCE_WIDE_OVERWATCH,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-002"],
  },
  {
    from: REINFORCE_RTL_OVERWATCH_S,
    to: REINFORCE_LAND_OVERWATCH_S,
    a: REINFORCE_WIDE_OVERWATCH,
    b: HOME_B["mav-002"],
    state: "RTL",
    alt: ROLE_ALT_M["mav-002"],
  },
  {
    from: REINFORCE_LAND_OVERWATCH_S,
    to: REINFORCE_COMPLETED_S + 2,
    a: HOME_B["mav-002"],
    b: HOME_B["mav-002"],
    state: "DOCKED",
    alt: 0,
  },
];

/** `mav-003` never arrives: it is killed mid-transit at `REINFORCE_FAIL_AT_S`. */
const REINFORCE_LEGS_SECONDARY: Leg[] = [
  {
    from: REINFORCE_LAUNCH_SECONDARY_S,
    to: REINFORCE_LAUNCH_SECONDARY_S + reinforceTransitS(HOME_B["mav-003"], REINFORCE_WIDE_SECONDARY),
    a: HOME_B["mav-003"],
    b: REINFORCE_WIDE_SECONDARY,
    state: "EN_ROUTE",
    alt: ROLE_ALT_M["mav-003"],
  },
];

const REINFORCE_LEGS_REPLACEMENT: Leg[] = [
  {
    from: REINFORCE_LAUNCH_REPLACEMENT_S,
    to: REINFORCE_ARRIVE_REPLACEMENT_S,
    a: HOME_B["mav-001"],
    b: REINFORCE_WIDE_SECONDARY,
    state: "EN_ROUTE",
    alt: ROLE_ALT_M["mav-001"],
  },
  {
    from: REINFORCE_ARRIVE_REPLACEMENT_S,
    to: REINFORCE_RTL_REPLACEMENT_S,
    a: REINFORCE_WIDE_SECONDARY,
    b: REINFORCE_WIDE_SECONDARY,
    state: "ON_STATION",
    alt: ROLE_ALT_M["mav-001"],
  },
  {
    from: REINFORCE_RTL_REPLACEMENT_S,
    to: REINFORCE_LAND_REPLACEMENT_S,
    a: REINFORCE_WIDE_SECONDARY,
    b: HOME_B["mav-001"],
    state: "RTL",
    alt: ROLE_ALT_M["mav-001"],
  },
  {
    from: REINFORCE_LAND_REPLACEMENT_S,
    to: REINFORCE_COMPLETED_S + 2,
    a: HOME_B["mav-001"],
    b: HOME_B["mav-001"],
    state: "DOCKED",
    alt: 0,
  },
];

/**
 * The reinforcement beat — composition under strength, reinforcement, the
 * widening leg, the recorded failover inside it, and recovery.
 *
 * Members are stamped once, when SwarmOS puts them in, and later frames carry
 * them forward changing only `state` — the same discipline `pushHeroGroupFrames`
 * observes, for the same reason: re-stamping would move the group's composition
 * time and could reorder the objectives or hand focus to the wrong one. One
 * exception is deliberate: unlike `pushHeroGroupFrames`, the failed member's own
 * `ts` is left untouched on the FAILED transition rather than moved to the
 * failure time. Swarm 02 composes with a single member, so that member is also
 * its earliest — moving its `ts` forward would move `composedAt` for the whole
 * group from the dispatch time to the failure time, which is exactly the
 * re-dating this discipline exists to prevent.
 */
function pushReinforcementFrames(frames: DemoFrame[]): void {
  function groupMemberR(
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
      ts: isoC(atS * 1000),
    };
  }

  function groupFrameR(
    groupId: string,
    reinforcesGroupId: string | null,
    requestedMembers: number,
    state: ExecutionGroup["state"],
    members: ExecutionGroupMember[],
    atS: number
  ): ExecutionGroup {
    return {
      id: groupId,
      objective_mission_id: REINFORCE_OBJECTIVE_MISSION,
      objective_kind: "COOPERATIVE_VERIFY",
      anomaly_id: REINFORCE_ANOMALY,
      reinforces_group_id: reinforcesGroupId,
      requested_members: requestedMembers,
      members,
      state,
      failure_reason: null,
      ts: isoC(atS * 1000),
    };
  }

  function unitR(
    agentId: string,
    atS: number,
    missionId: string | null,
    legs: Leg[],
    batteryPct: number,
    fixedState?: UnitState["fsm_state"]
  ): UnitState {
    const { geo, state, headingDeg } = positionAt(legs, HOME_B[agentId], atS);
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
      ts: isoC(atS * 1000),
    };
  }

  function runtimeR(
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
      ts: isoC(atS * 1000),
    };
  }

  function missionR(missionId: string, agentId: string, legs: Leg[], atS: number): MissionView {
    const track: Geo[] = [];
    for (let t = 0; t <= atS; t += 1.5) track.push(positionAt(legs, HOME_B[agentId], t).geo);
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
      ts: isoC(atS * 1000),
    };
  }

  /** `payload()` above stamps `ts` off `TAKE_A.t0`; this take runs on `TAKE_C.t0`. */
  function payloadR(
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
      ts: isoC(atS * 1000),
    };
  }

  const roster = [
    {
      agent: "mav-004",
      mission: TAKE_B.primary.mission,
      legs: REINFORCE_LEGS_PRIMARY,
      from: REINFORCE_LAUNCH_PRIMARY_S,
    },
    {
      agent: "mav-002",
      mission: TAKE_B.overwatch.mission,
      legs: REINFORCE_LEGS_OVERWATCH,
      from: REINFORCE_LAUNCH_OVERWATCH_S,
    },
    {
      agent: "mav-003",
      mission: TAKE_B.secondary.mission,
      legs: REINFORCE_LEGS_SECONDARY,
      from: REINFORCE_LAUNCH_SECONDARY_S,
    },
    {
      agent: "mav-001",
      mission: TAKE_B.replacement.mission,
      legs: REINFORCE_LEGS_REPLACEMENT,
      from: REINFORCE_LAUNCH_REPLACEMENT_S,
    },
  ];

  // Telemetry, at 1 Hz. `mav-003`'s last reported position holds from the
  // recorded failure onward, exactly as `pushHeroGroupFrames` does for the same
  // agent in take B.
  for (let t = 0; t <= REINFORCE_COMPLETED_S + 5; t += 1) {
    for (const entry of roster) {
      const dead = entry.agent === "mav-003" && t > REINFORCE_FAIL_AT_S;
      const sample = dead ? REINFORCE_FAIL_AT_S : t;
      frames.push({
        at: t * 1000,
        kind: "unit",
        data: unitR(
          entry.agent,
          sample,
          t >= entry.from ? entry.mission : null,
          entry.legs,
          Math.max(60, 100 - t * 0.3),
          dead ? "OFFLINE" : undefined
        ),
      });
    }
  }

  // The detection that starts everything, shaped exactly as take B's.
  frames.push({
    at: REINFORCE_DETECT_S * 1000,
    kind: "anomaly",
    data: {
      ...anomaly(REINFORCE_ANOMALY, "INTRUSION", OBJECTIVE_B, 0.98, REINFORCE_DETECT_S, "mav-004"),
      ts: isoC(REINFORCE_DETECT_S * 1000),
      detected_at: isoC(REINFORCE_DETECT_S * 1000),
      evidence: {
        source: "drone_cv",
        sensor: "RGB",
        label: "person",
        metric: "score",
        value: 0.98,
        baseline: null,
        unit: null,
        headline:
          "Elevated anomaly — onboard CV classified a person at 0.98 confidence. Sector requires verification.",
        simulated: true,
      },
    },
  });

  // Swarm 01 composes under strength: two of the three roles the objective
  // asked for. ADR-0012 — a partial composition is ACTIVE, not DEGRADED, and
  // carries no failure_reason.
  const swarmAInitial = [
    groupMemberR("mav-004", "PRIMARY_OBSERVER", TAKE_B.primary.mission, "ASSIGNED", TAKE_B.primary.score, REINFORCE_FORM_S),
    groupMemberR("mav-002", "OVERWATCH", TAKE_B.overwatch.mission, "ASSIGNED", TAKE_B.overwatch.score, REINFORCE_FORM_S),
  ];
  frames.push({
    at: REINFORCE_FORM_S * 1000,
    kind: "group",
    data: groupFrameR(REINFORCE_SWARM_A_GROUP, null, 3, "FORMING", swarmAInitial, REINFORCE_FORM_S),
  });
  const swarmAActive = swarmAInitial.map((m) => ({ ...m, state: "ACTIVE" as const }));
  frames.push({
    at: REINFORCE_ACTIVE_S * 1000,
    kind: "group",
    data: groupFrameR(REINFORCE_SWARM_A_GROUP, null, 3, "ACTIVE", swarmAActive, REINFORCE_ACTIVE_S),
  });

  frames.push({
    at: REINFORCE_LAUNCH_PRIMARY_S * 1000,
    kind: "runtime",
    data: runtimeR(TAKE_B.primary.mission, "mav-004", "EN_ROUTE", REINFORCE_LAUNCH_PRIMARY_S),
  });
  frames.push({
    at: REINFORCE_LAUNCH_OVERWATCH_S * 1000,
    kind: "runtime",
    data: runtimeR(TAKE_B.overwatch.mission, "mav-002", "EN_ROUTE", REINFORCE_LAUNCH_OVERWATCH_S),
  });
  frames.push({
    at: REINFORCE_ARRIVE_TIGHT_PRIMARY_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.primary.mission,
      "mav-004",
      "ON_STATION",
      REINFORCE_ARRIVE_TIGHT_PRIMARY_S,
      "mavlink_mission_item_reached"
    ),
  });
  frames.push({
    at: REINFORCE_ARRIVE_TIGHT_OVERWATCH_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.overwatch.mission,
      "mav-002",
      "ON_STATION",
      REINFORCE_ARRIVE_TIGHT_OVERWATCH_S,
      "mavlink_mission_item_reached"
    ),
  });

  // Capacity frees up. SwarmOS dispatches swarm 02 — a second ExecutionGroup,
  // never extra members on the first — for the missing SECONDARY_OBSERVER role.
  const swarmBInitial = [
    groupMemberR(
      "mav-003",
      "SECONDARY_OBSERVER",
      TAKE_B.secondary.mission,
      "ASSIGNED",
      TAKE_B.secondary.score,
      REINFORCE_DISPATCH_S
    ),
  ];
  frames.push({
    at: REINFORCE_DISPATCH_S * 1000,
    kind: "group",
    data: groupFrameR(REINFORCE_SWARM_B_GROUP, REINFORCE_SWARM_A_GROUP, 1, "FORMING", swarmBInitial, REINFORCE_DISPATCH_S),
  });
  const swarmBActive = swarmBInitial.map((m) => ({ ...m, state: "ACTIVE" as const }));
  frames.push({
    at: REINFORCE_SWARM_B_ACTIVE_S * 1000,
    kind: "group",
    data: groupFrameR(
      REINFORCE_SWARM_B_GROUP,
      REINFORCE_SWARM_A_GROUP,
      1,
      "ACTIVE",
      swarmBActive,
      REINFORCE_SWARM_B_ACTIVE_S
    ),
  });
  frames.push({
    at: REINFORCE_LAUNCH_SECONDARY_S * 1000,
    kind: "runtime",
    data: runtimeR(TAKE_B.secondary.mission, "mav-003", "EN_ROUTE", REINFORCE_LAUNCH_SECONDARY_S),
  });

  // The failure: a real process-level loss while the member was EN_ROUTE,
  // recorded at T+21. It lands inside the wide shot — both surviving swarm 01
  // subunits have already settled onto their wide station by this point.
  frames.push({
    at: REINFORCE_FAIL_AT_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.secondary.mission,
      "mav-003",
      "FAILED",
      REINFORCE_FAIL_AT_S,
      null,
      "MAVLinkCommandError: COMMAND_LONG 20 timed out waiting for COMMAND_ACK"
    ),
  });
  frames.push({
    at: (REINFORCE_FAIL_AT_S + 0.2) * 1000,
    kind: "group",
    data: groupFrameR(
      REINFORCE_SWARM_B_GROUP,
      REINFORCE_SWARM_A_GROUP,
      1,
      "DEGRADED",
      [{ ...swarmBActive[0], state: "FAILED" }],
      REINFORCE_FAIL_AT_S + 0.2
    ),
  });

  // SwarmOS selects the unused spare for the same logical role, at T+23. No
  // surviving agent elected it; the provenance is `replaces_agent_id`.
  const swarmBRestored = [
    { ...swarmBActive[0], state: "REPLACED" as const },
    groupMemberR(
      "mav-001",
      "SECONDARY_OBSERVER",
      TAKE_B.replacement.mission,
      "ACTIVE",
      TAKE_B.replacement.score,
      REINFORCE_REPLACED_AT_S,
      "mav-003"
    ),
  ];
  frames.push({
    at: REINFORCE_REPLACED_AT_S * 1000,
    kind: "group",
    data: groupFrameR(
      REINFORCE_SWARM_B_GROUP,
      REINFORCE_SWARM_A_GROUP,
      1,
      "ACTIVE",
      swarmBRestored,
      REINFORCE_REPLACED_AT_S
    ),
  });
  frames.push({
    at: REINFORCE_LAUNCH_REPLACEMENT_S * 1000,
    kind: "runtime",
    data: runtimeR(TAKE_B.replacement.mission, "mav-001", "EN_ROUTE", REINFORCE_LAUNCH_REPLACEMENT_S),
  });
  frames.push({
    at: REINFORCE_ARRIVE_REPLACEMENT_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.replacement.mission,
      "mav-001",
      "ON_STATION",
      REINFORCE_ARRIVE_REPLACEMENT_S,
      "mavlink_mission_item_reached"
    ),
  });

  // Bounded presence response, once the combined force is at full strength.
  frames.push({
    at: REINFORCE_LIGHT_ON_S * 1000,
    kind: "payload",
    data: payloadR(
      TAKE_B.primary.mission,
      REINFORCE_ANOMALY,
      "mav-004",
      "light_on",
      "mavlink_output_confirmed",
      REINFORCE_LIGHT_ON_S
    ),
  });
  frames.push({
    at: REINFORCE_PLAY_MSG_S * 1000,
    kind: "payload",
    data: payloadR(TAKE_B.primary.mission, REINFORCE_ANOMALY, "mav-004", "play_message", "simulated", REINFORCE_PLAY_MSG_S),
  });
  frames.push({
    at: REINFORCE_STOP_MSG_S * 1000,
    kind: "payload",
    data: payloadR(TAKE_B.primary.mission, REINFORCE_ANOMALY, "mav-004", "stop_message", "simulated", REINFORCE_STOP_MSG_S),
  });
  frames.push({
    at: REINFORCE_LIGHT_OFF_S * 1000,
    kind: "payload",
    data: payloadR(
      TAKE_B.primary.mission,
      REINFORCE_ANOMALY,
      "mav-004",
      "light_off",
      "mavlink_output_confirmed",
      REINFORCE_LIGHT_OFF_S
    ),
  });

  // Recovery, each on an acknowledged RTL, then both groups completed.
  frames.push({
    at: REINFORCE_DONE_PRIMARY_S * 1000,
    kind: "runtime",
    data: runtimeR(TAKE_B.primary.mission, "mav-004", "DONE", REINFORCE_DONE_PRIMARY_S, "mavlink_rtl_command_acknowledged"),
  });
  frames.push({
    at: REINFORCE_DONE_OVERWATCH_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.overwatch.mission,
      "mav-002",
      "DONE",
      REINFORCE_DONE_OVERWATCH_S,
      "mavlink_rtl_command_acknowledged"
    ),
  });
  frames.push({
    at: REINFORCE_DONE_REPLACEMENT_S * 1000,
    kind: "runtime",
    data: runtimeR(
      TAKE_B.replacement.mission,
      "mav-001",
      "DONE",
      REINFORCE_DONE_REPLACEMENT_S,
      "mavlink_rtl_command_acknowledged"
    ),
  });
  frames.push({
    at: REINFORCE_GROUP_A_COMPLETE_S * 1000,
    kind: "group",
    data: groupFrameR(
      REINFORCE_SWARM_A_GROUP,
      null,
      3,
      "COMPLETED",
      swarmAActive.map((m) => ({ ...m, state: "COMPLETED" as const })),
      REINFORCE_GROUP_A_COMPLETE_S
    ),
  });
  frames.push({
    at: REINFORCE_GROUP_B_COMPLETE_S * 1000,
    kind: "group",
    data: groupFrameR(
      REINFORCE_SWARM_B_GROUP,
      REINFORCE_SWARM_A_GROUP,
      1,
      "COMPLETED",
      swarmBRestored.map((m) => (m.state === "REPLACED" ? m : { ...m, state: "COMPLETED" as const })),
      REINFORCE_GROUP_B_COMPLETE_S
    ),
  });

  // Observed tracks, sampled so the map has a path to draw.
  for (let t = 4; t <= REINFORCE_COMPLETED_S; t += 2) {
    for (const entry of roster) {
      if (t < entry.from) continue;
      const sample = entry.agent === "mav-003" && t > REINFORCE_FAIL_AT_S ? REINFORCE_FAIL_AT_S : t;
      frames.push({
        at: t * 1000,
        kind: "mission",
        data: missionR(entry.mission, entry.agent, entry.legs, sample),
      });
    }
  }
}

/**
 * The area sweep.
 *
 * The second objective SwarmOS holds through this take, and the one that makes
 * the fleet a fleet: thirty executors deployed at once, in a three-rank line
 * abreast, while three more are held back for whatever else arrives. It is not
 * a response to a detection — it carries no anomaly, because SwarmOS raising a
 * scheduled sweep over its own sector is an objective it selects, not one it
 * was handed.
 *
 * The geometry is chosen so the whole deployment stays legible on one screen at
 * the recording viewport. The camera scales to whatever it has to hold, so what
 * matters is not the absolute spacing but its ratio to the formation's own
 * extent: 50 m between neighbours in a rank and 50 m between ranks leaves about
 * 70 px — five glyph widths — between adjacent aircraft once the formation is
 * extended. Ranks are separated vertically as well, the same way SwarmOS
 * deconflicts a cooperative objective, so two ranks can never resolve onto one
 * line of pixels.
 *
 * The whole formation sits south of the dock. The hero group flies due north,
 * so the two never contend for the same ground.
 */
const SWEEP_RANKS = 3;
const SWEEP_PER_RANK = 10;
/** Metres between neighbours in a rank. */
const SWEEP_LATERAL_M = 50;
/** Metres north of the dock, one per rank. Negative: the sector is south. */
const SWEEP_RANK_N_M = [-100, -150, -200];
/**
 * Station altitude per rank. Vertical deconfliction, as in the role ladder.
 *
 * Descending with range, and that ordering is a drawing decision as much as a
 * deconfliction one: the map lifts a glyph off its ground mark in proportion to
 * reported altitude, so giving the *nearest* rank the *highest* station pushes
 * the ranks further apart on screen instead of collapsing them together. The
 * separation is real either way — 20 m between ranks — and no operational value
 * is computed from it.
 */
const SWEEP_RANK_ALT_M = [90, 70, 50];
/**
 * Cruise, in metres per second.
 *
 * SCRIPTED. It sets how long the deployment takes to form up, and it is chosen
 * so that it completes inside a seventy-second take. Nothing operational
 * depends on it — no bid, no role and no evidence boundary is computed from it.
 */
const SWEEP_CRUISE_MS = 30;

/** East/north offset in metres, on the same spherical model as `offsetGeo`. */
function offsetEN(from: Geo, eastM: number, northM: number): Geo {
  return {
    lat: from.lat + northM / 111_320,
    lon: from.lon + eastM / (111_320 * Math.cos((from.lat * Math.PI) / 180)),
    alt_m: 0,
  };
}

/**
 * Scripted identifiers for the sweep.
 *
 * Made up, deterministically, and never lifted from a bench run: putting a
 * recorded mission id on an event that was never recorded would misattribute
 * real data to a scripted one.
 */
const SWEEP_GROUP_ID = "6b1d78f04c2e4a95bd3067ff8a12c4e9";
const SWEEP_OBJECTIVE_MISSION = "c7d2e9114ab8452fa0367e5bd91c8e64";
const sweepMission = (i: number) =>
  (0x7c4f0000 + i).toString(16).padStart(8, "0") + "9b3418e8a5c2f60117be94a3";

/** Priority the allocator derives for a scheduled sweep — no confidence term. */
const PRIORITY_SWEEP = 80;

/** The allocator's own bid, summed from the terms `breakdown` already models. */
function scoreBid(distance: number, batteryPct: number, priority: number): number {
  const terms = breakdown(distance, batteryPct, priority);
  return (
    terms.distance_score + terms.battery_score + terms.priority_score - terms.busy_penalty
  );
}

type SweepStation = {
  agent: DockedAgent;
  role: string;
  missionId: string;
  station: Geo;
  altM: number;
  distanceM: number;
  score: number;
  /** Take-seconds: launch, arrival on station, return, back on the pad. */
  launchS: number;
  arriveS: number;
  returnS: number;
  landS: number;
};

/**
 * Take-seconds the formation holds station before SwarmOS recalls it.
 *
 * Set so the sweep closes *before* the hero objective does. Focus follows the
 * newest objective still running, and a patrol that outlived the verification
 * would take the last frames of the take with it.
 */
const SWEEP_RETURN_S = 35;

const SWEEP: SweepStation[] = RESERVE_C.map((agent, i) => {
  const rank = Math.floor(i / SWEEP_PER_RANK);
  const k = i % SWEEP_PER_RANK;
  const eastM = (k - (SWEEP_PER_RANK - 1) / 2) * SWEEP_LATERAL_M;
  const northM = SWEEP_RANK_N_M[rank];
  const station = offsetEN(DOCK_B, eastM, northM);
  const distanceM = Math.hypot(eastM, northM);
  // Aircraft leave one pad in sequence, rank by rank, and the spacing is wide
  // enough that no more than two or three are ever within a second of the pad
  // at once. A fleet that launches on the same tick is thirty glyphs on one
  // pixel for the first five seconds of the take.
  //
  // Within a rank they go in alternate stations — every second slot, then the
  // ones in between. Two aircraft launched back to back then leave on bearings
  // 110 m apart at the far end rather than 55, which is what separates them on
  // screen while they are still close to the pad.
  const launchSlot = k % 2 === 0 ? k / 2 : (SWEEP_PER_RANK + k - 1) / 2;
  const launchS = 3 + rank * 1.6 + launchSlot * 0.5;
  const transitS = 2 + distanceM / SWEEP_CRUISE_MS;
  return {
    agent,
    role: `SWEEP_${String(i + 1).padStart(2, "0")}`,
    missionId: sweepMission(i),
    station,
    altM: SWEEP_RANK_ALT_M[rank],
    distanceM,
    // COMPUTED: the real allocator formula over the real station distance.
    score: scoreBid(distanceM, agent.batteryPct, PRIORITY_SWEEP),
    launchS,
    arriveS: launchS + transitS,
    returnS: SWEEP_RETURN_S,
    landS: SWEEP_RETURN_S + transitS,
  };
});

/** Take-seconds by which every sweep member is back on the pad. */
const SWEEP_COMPLETED_S = Math.ceil(Math.max(...SWEEP.map((s) => s.landS))) + 1;

export const TAKE_C = {
  /** Settles a few seconds after the later of the two objectives to complete. */
  durationMs: (Math.max(REINFORCE_COMPLETED_S, SWEEP_COMPLETED_S) + 6) * 1000,
  /** The failover beat is take B's, so take C states it on take B's session clock. */
  t0: TAKE_B.t0,
  reserveAgents: RESERVE_C.length,
  reinforcement: {
    anomaly: REINFORCE_ANOMALY,
    objectiveMission: REINFORCE_OBJECTIVE_MISSION,
    swarmA: REINFORCE_SWARM_A_GROUP,
    swarmB: REINFORCE_SWARM_B_GROUP,
    requestedMembers: 3,
    failAtS: REINFORCE_FAIL_AT_S,
    replacedAtS: REINFORCE_REPLACED_AT_S,
  },
  sweep: {
    group: SWEEP_GROUP_ID,
    objectiveMission: SWEEP_OBJECTIVE_MISSION,
    members: SWEEP.length,
    ranks: SWEEP_RANKS,
  },
} as const;

const isoC = (at: number) => new Date(TAKE_C.t0 + at).toISOString();

function unitC(
  agent: DockedAgent,
  atS: number,
  legs: Leg[] | null,
  missionId: string | null,
  batteryPct: number
): UnitState {
  const flown = legs ? positionAt(legs, agent.home, atS) : null;
  return {
    agent_id: agent.agentId,
    vendor: "mavlink",
    model: "px4-iris-sitl",
    fsm_state: flown?.state ?? "DOCKED",
    battery_pct: batteryPct,
    geo: flown?.geo ?? agent.home,
    current_mission_id: missionId,
    current_sector_id: null,
    link_quality: 1,
    heading_deg: flown?.headingDeg ?? agent.headingDeg,
    altitude_agl_m: flown?.geo.alt_m ?? 0,
    // The one shared pad. Every executor in this take launches from it, which
    // is what lets the map draw a dock holding capacity instead of a heap of
    // overlapping darts.
    dock_id: "dock-sitl-01",
    ts: isoC(atS * 1000),
  };
}

function legsForSweep(s: SweepStation): Leg[] {
  return [
    { from: s.launchS, to: s.arriveS, a: s.agent.home, b: s.station, state: "EN_ROUTE", alt: s.altM },
    { from: s.arriveS, to: s.returnS, a: s.station, b: s.station, state: "ON_STATION", alt: s.altM },
    { from: s.returnS, to: s.landS, a: s.station, b: s.agent.home, state: "RTL", alt: s.altM },
    { from: s.landS, to: 68, a: s.agent.home, b: s.agent.home, state: "DOCKED", alt: 0 },
  ];
}

const SWEEP_LEGS = new Map(SWEEP.map((s) => [s.agent.agentId, legsForSweep(s)]));

function sweepMember(
  s: SweepStation,
  state: ExecutionGroupMember["state"],
  atS: number
): ExecutionGroupMember {
  return {
    agent_id: s.agent.agentId,
    role: s.role,
    mission_id: s.missionId,
    state,
    score: s.score,
    score_breakdown: {},
    replaces_agent_id: null,
    ts: isoC(atS * 1000),
  };
}

function sweepGroup(
  state: ExecutionGroup["state"],
  members: ExecutionGroupMember[],
  atS: number
): ExecutionGroup {
  return {
    id: SWEEP_GROUP_ID,
    objective_mission_id: SWEEP_OBJECTIVE_MISSION,
    objective_kind: "AREA_SWEEP",
    // No anomaly: a scheduled sweep is an objective SwarmOS selected, not a
    // response to something a sensor reported.
    anomaly_id: null,
    requested_members: SWEEP.length,
    members,
    state,
    failure_reason: null,
    ts: isoC(atS * 1000),
  };
}

function runtimeSweep(
  s: SweepStation,
  phase: string,
  atS: number,
  evidence: MissionRuntimeEvent["evidence"] = null
): MissionRuntimeEvent {
  return {
    id: `${s.missionId}-${phase}`,
    mission_id: s.missionId,
    agent_id: s.agent.agentId,
    phase,
    progress_pct: phase === "DONE" ? 100 : phase === "ON_STATION" ? 90 : 5,
    evidence,
    error: null,
    ts: isoC(atS * 1000),
  };
}

/**
 * The sweep, from composition to recovery.
 *
 * It opens before the hero detection rather than during it. The surface follows
 * the newest objective SwarmOS is working, so an objective raised mid-transit
 * would take the camera off the group for as long as it stayed newest; opening
 * first means SwarmOS is visibly already holding one objective when the second
 * arrives, and the camera never leaves the hero beat once it has it. It also
 * lands the formation at full extension across the failover, which is the one
 * moment worth showing the whole fleet and the recomposition together.
 *
 * It closes before the hero too, so the take's last frames settle on the
 * objective that was verified rather than on a patrol that outlived it.
 */
function pushSweepFrames(frames: DemoFrame[]): void {
  for (let t = 0; t <= 68; t += 1) {
    for (const s of SWEEP) {
      frames.push({
        at: t * 1000,
        kind: "unit",
        data: unitC(
          s.agent,
          t,
          SWEEP_LEGS.get(s.agent.agentId) as Leg[],
          t >= 2.5 && t < s.landS ? s.missionId : null,
          Math.max(55, s.agent.batteryPct - Math.max(0, t - s.launchS) * 0.22)
        ),
      });
    }
  }

  // Members are stamped once, when SwarmOS puts them in, and later frames only
  // carry them forward with a new state — the shape the hero beat already
  // publishes. Re-stamping every member on every frame would move the group's
  // composition time forward with it, which is a claim about when SwarmOS
  // decided, not about when it last spoke.
  const assigned = SWEEP.map((s) => sweepMember(s, "ASSIGNED", 2.5));
  const active = assigned.map((member) => ({ ...member, state: "ACTIVE" as const }));

  frames.push({ at: 2_500, kind: "group", data: sweepGroup("FORMING", assigned, 2.5) });
  frames.push({ at: 3_000, kind: "group", data: sweepGroup("ACTIVE", active, 3) });

  for (const s of SWEEP) {
    frames.push({ at: s.launchS * 1000, kind: "runtime", data: runtimeSweep(s, "EN_ROUTE", s.launchS) });
    frames.push({
      at: s.arriveS * 1000,
      kind: "runtime",
      data: runtimeSweep(s, "ON_STATION", s.arriveS, "mavlink_mission_item_reached"),
    });
    frames.push({
      at: s.landS * 1000,
      kind: "runtime",
      data: runtimeSweep(s, "DONE", s.landS, "mavlink_rtl_command_acknowledged"),
    });
  }

  frames.push({
    at: SWEEP_COMPLETED_S * 1000,
    kind: "group",
    data: sweepGroup(
      "COMPLETED",
      active.map((member) => ({ ...member, state: "COMPLETED" as const })),
      SWEEP_COMPLETED_S
    ),
  });
}
export function takeCFrames(): DemoFrame[] {
  const frames: DemoFrame[] = [];
  pushReinforcementFrames(frames);
  pushSweepFrames(frames);
  return frames.sort((a, b) => a.at - b.at);
}

/** Fold take C up to `atMs`, exactly as `SwarmStateProvider` would. */
export function foldTakeC(atMs: number, frames: DemoFrame[] = takeCFrames()): TakeSlice {
  return { ...foldFrames(atMs, frames), now: TAKE_C.t0 + atMs };
}
