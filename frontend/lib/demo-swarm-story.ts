import type { ExecutionGroupMember, Geo, MissionRuntimeEvent, MissionView, UnitState } from "./api";
import { TAKE_C, type TakeSlice } from "./demo-frames";

const SUPPORT_AGENT = "mav-035";
const SUPPORT_MISSION = "35c0a1e26b9d4f03a6f8c1b2d5e7a904";
const DISPATCH_MS = 14_500;
const LAUNCH_MS = 16_000;
const ARRIVE_MS = 19_000;
const RETURN_MS = 48_000;
const DONE_MS = 51_000;

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function lerpGeo(a: Geo, b: Geo, t: number, altitude: number): Geo {
  const k = clamp01(t);
  return {
    lat: a.lat + (b.lat - a.lat) * k,
    lon: a.lon + (b.lon - a.lon) * k,
    alt_m: altitude,
  };
}

function offsetEN(from: Geo, eastM: number, northM: number): Geo {
  return {
    lat: from.lat + northM / 111_320,
    lon: from.lon + eastM / (111_320 * Math.cos((from.lat * Math.PI) / 180)),
    alt_m: 0,
  };
}

function bearingDeg(from: Geo, to: Geo): number {
  const dLat = to.lat - from.lat;
  const dLon = (to.lon - from.lon) * Math.cos((from.lat * Math.PI) / 180);
  return ((Math.atan2(dLon, dLat) * 180) / Math.PI + 360) % 360;
}

function timestamp(atMs: number): string {
  return new Date(TAKE_C.t0 + atMs).toISOString();
}

function runtimeEvent(
  phase: string,
  atMs: number,
  evidence: MissionRuntimeEvent["evidence"] = null
): MissionRuntimeEvent {
  return {
    id: `${SUPPORT_MISSION}-${phase}-${atMs}`,
    mission_id: SUPPORT_MISSION,
    agent_id: SUPPORT_AGENT,
    phase,
    progress_pct:
      phase === "DONE" ? 100 : phase === "ON_STATION" ? 70 : phase === "RETURNING" ? 85 : 35,
    evidence,
    error: null,
    ts: timestamp(atMs),
  };
}

/**
 * Take C is presentation-only already. This adds one explicitly scripted support
 * subunit to the reinforcing swarm so the thing the viewer sees as "SWARM 02"
 * is actually a multi-subunit unit, not one aircraft wearing a group label.
 *
 * The recorded mav-003 -> mav-001 failover remains untouched. The added support
 * role has its own synthetic mission id and never borrows recorded evidence.
 */
export function augmentTakeCForSwarmStory(slice: TakeSlice, atMs: number): TakeSlice {
  const template = slice.units.find((unit) => unit.agent_id === "mav-001") ?? slice.units[0];
  if (!template) return slice;

  const intrusion = slice.anomalies.find((anomaly) => anomaly.kind === "INTRUSION") ?? null;
  const dockTemplate =
    slice.units.find(
      (unit) => unit.fsm_state === "DOCKED" && unit.dock_id === template.dock_id
    ) ?? (atMs < 24_000 ? template : null);
  const dock = dockTemplate?.geo ?? template.geo;
  const target = intrusion ? offsetEN(intrusion.geo, 28, -18) : offsetEN(dock, 28, 70);

  let fsmState: UnitState["fsm_state"] = "DOCKED";
  let geo = { ...dock, alt_m: 0 };
  let altitude = 0;
  let heading = template.heading_deg;
  let currentMission: string | null = null;

  if (atMs >= LAUNCH_MS && atMs < ARRIVE_MS) {
    const k = (atMs - LAUNCH_MS) / (ARRIVE_MS - LAUNCH_MS);
    altitude = 55 * Math.min(1, k * 2.4);
    geo = lerpGeo(dock, target, k, altitude);
    heading = bearingDeg(dock, target);
    fsmState = "EN_ROUTE";
    currentMission = SUPPORT_MISSION;
  } else if (atMs >= ARRIVE_MS && atMs < RETURN_MS) {
    altitude = 55;
    geo = { ...target, alt_m: altitude };
    heading = bearingDeg(dock, target);
    fsmState = "ON_STATION";
    currentMission = SUPPORT_MISSION;
  } else if (atMs >= RETURN_MS && atMs < DONE_MS) {
    const k = (atMs - RETURN_MS) / (DONE_MS - RETURN_MS);
    altitude = 55 * (1 - k * 0.9);
    geo = lerpGeo(target, dock, k, altitude);
    heading = bearingDeg(target, dock);
    fsmState = "RTL";
    currentMission = SUPPORT_MISSION;
  } else if (atMs >= DONE_MS) {
    geo = { ...dock, alt_m: 0 };
    altitude = 0;
    fsmState = "DOCKED";
    currentMission = null;
  }

  const supportUnit: UnitState = {
    ...template,
    agent_id: SUPPORT_AGENT,
    fsm_state: fsmState,
    battery_pct: Math.max(72, 96 - atMs / 1000 * 0.22),
    geo,
    current_mission_id: currentMission,
    heading_deg: heading,
    altitude_agl_m: altitude,
    ts: timestamp(atMs),
  };

  const units = [...slice.units.filter((unit) => unit.agent_id !== SUPPORT_AGENT), supportUnit];

  const executionGroups = slice.executionGroups.map((group) => {
    if (!group.reinforces_group_id || atMs < DISPATCH_MS) return group;
    const seed = group.members.find((member) => member.agent_id === "mav-003") ?? group.members[0];
    if (!seed) return group;

    const supportState: ExecutionGroupMember["state"] =
      group.state === "COMPLETED" || atMs >= DONE_MS
        ? "COMPLETED"
        : group.state === "FORMING"
          ? "ASSIGNED"
          : "ACTIVE";

    const support: ExecutionGroupMember = {
      agent_id: SUPPORT_AGENT,
      role: "OVERWATCH",
      mission_id: SUPPORT_MISSION,
      state: supportState,
      score: Math.max(0, seed.score - 0.01),
      score_breakdown: { ...seed.score_breakdown },
      replaces_agent_id: null,
      ts: group.ts,
    };

    return {
      ...group,
      requested_members: 2,
      members: [...group.members.filter((member) => member.agent_id !== SUPPORT_AGENT), support],
    };
  });

  const history: MissionRuntimeEvent[] = [];
  if (atMs >= LAUNCH_MS) history.push(runtimeEvent("EN_ROUTE", LAUNCH_MS));
  if (atMs >= ARRIVE_MS) {
    history.push(runtimeEvent("ON_STATION", ARRIVE_MS, "mavlink_mission_item_reached"));
  }
  if (atMs >= RETURN_MS) history.push(runtimeEvent("RETURNING", RETURN_MS));
  if (atMs >= DONE_MS) {
    history.push(runtimeEvent("DONE", DONE_MS, "mavlink_rtl_command_acknowledged"));
  }

  const latest = history.at(-1) ?? null;
  const missionRuntime = [
    ...slice.missionRuntime.filter((event) => event.mission_id !== SUPPORT_MISSION),
    ...(latest ? [latest] : []),
  ];
  const missionRuntimeLog = [
    ...slice.missionRuntimeLog.filter((event) => event.mission_id !== SUPPORT_MISSION),
    ...history,
  ];

  const mission: MissionView = {
    id: SUPPORT_MISSION,
    kind: "VERIFY",
    assigned_agent: atMs >= DISPATCH_MS && atMs < DONE_MS ? SUPPORT_AGENT : null,
    sector_id: null,
    phase:
      atMs < LAUNCH_MS
        ? "accepted"
        : atMs < ARRIVE_MS
          ? "en_route"
          : atMs < RETURN_MS
            ? "on_station"
            : atMs < DONE_MS
              ? "returning"
              : "done",
    progress_pct:
      atMs < LAUNCH_MS ? 0 : atMs < ARRIVE_MS ? 40 : atMs < RETURN_MS ? 70 : atMs < DONE_MS ? 90 : 100,
    eta_s: null,
    waypoints: [target],
    track: atMs < LAUNCH_MS ? [] : [dock, geo],
    ts: timestamp(atMs),
  };

  const missions = [...slice.missions.filter((item) => item.id !== SUPPORT_MISSION), mission];

  return {
    ...slice,
    units,
    executionGroups,
    missionRuntime,
    missionRuntimeLog,
    missions,
  };
}
