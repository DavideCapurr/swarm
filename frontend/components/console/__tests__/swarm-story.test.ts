import { describe, expect, it } from "vitest";

import { buildAuthorityView } from "@/lib/authority";
import {
  TAKE_C_PLAYBACK_SCALE,
  causalTakeCDurationMs,
  foldCausalTakeC,
  isCausalTakeCCapture,
  type CausalTakeCCapture,
} from "@/lib/causal-take-c";
import type {
  DispositionDecision,
  ExecutionGroup,
  ExecutionGroupMember,
  MissionRuntimeEvent,
  UnitState,
} from "@/lib/api";

const START = "2026-08-19T16:00:00.000Z";

function unit(agentId: string, lat: number, state: UnitState["fsm_state"] = "EN_ROUTE"): UnitState {
  return {
    agent_id: agentId,
    vendor: "simulated",
    model: "sim-x500",
    fsm_state: state,
    battery_pct: 99,
    geo: { lat, lon: 8.03, alt_m: 45 },
    current_mission_id: null,
    current_sector_id: null,
    link_quality: state === "OFFLINE" ? 0 : 1,
    heading_deg: 0,
    altitude_agl_m: 45,
    dock_id: null,
    ts: START,
  };
}

function member(agentId: string, role: string): ExecutionGroupMember {
  return {
    agent_id: agentId,
    role,
    mission_id: `mission-${agentId}`,
    state: "ACTIVE",
    score: 3,
    score_breakdown: {},
    replaces_agent_id: null,
    diverted_from_mission_id: null,
    diverted_from_objective_id: null,
    ts: START,
  };
}

function group(
  id: string,
  members: ExecutionGroupMember[],
  reinforcesGroupId: string | null = null
): ExecutionGroup {
  return {
    id,
    objective_mission_id: "objective-causal",
    objective_kind: "COOPERATIVE_VERIFY",
    anomaly_id: null,
    reinforces_group_id: reinforcesGroupId,
    requested_members: reinforcesGroupId ? 1 : 3,
    members,
    state: "ACTIVE",
    failure_reason: null,
    ts: START,
  };
}

function disposition(revision: number, radius: number, agents: string[]): DispositionDecision {
  return {
    objective_mission_id: "objective-causal",
    revision,
    reason: revision === 1 ? "COMPOSITION" : "REINFORCEMENT",
    center: { lat: 44.7, lon: 8.03, alt_m: 45 },
    active_members: agents.length,
    radius_m: radius,
    assignments: agents.map((agentId, index) => ({
      group_id: index < 2 ? "origin" : "reinforcement",
      agent_id: agentId,
      role: index === 0 ? "PRIMARY_OBSERVER" : `ROLE_${index}`,
      mission_id: `slot-${agentId}`,
      geo: { lat: 44.7 + index * 0.001, lon: 8.03, alt_m: 45 + index * 5 },
    })),
    ts: START,
  };
}

const runtime: MissionRuntimeEvent = {
  id: "runtime-1",
  mission_id: "mission-a",
  agent_id: "a",
  phase: "EN_ROUTE",
  progress_pct: 5,
  evidence: null,
  error: null,
  ts: START,
};

const CAPTURE: CausalTakeCCapture = {
  schema_version: 1,
  provenance: "causal-simulator-runtime",
  proof_scope: {
    swarmos_decisions: "runtime bus truth",
    physical_positions: "kinematic simulator telemetry/state",
    disposition_execution: "simulator only",
    px4_disposition_claim: false,
  },
  started_at: START,
  duration_ms: 200,
  world_facts: [
    "baseline continuous coverage objective exists",
    "intrusion appears",
    "capacity becomes available",
    "an active physical executor fails",
  ],
  milestones: {},
  frames: [
    { at: 0, kind: "unit", data: unit("a", 44.7) },
    { at: 0, kind: "unit", data: unit("b", 44.701) },
    { at: 20, kind: "group", data: group("origin", [member("a", "PRIMARY_OBSERVER"), member("b", "SECONDARY_OBSERVER")]) },
    { at: 30, kind: "disposition", data: disposition(1, 22, ["a", "b"]) },
    { at: 40, kind: "runtime", data: runtime },
    { at: 100, kind: "unit", data: unit("a", 44.702, "OFFLINE") },
    { at: 120, kind: "unit", data: unit("c", 44.703) },
    { at: 120, kind: "group", data: group("reinforcement", [member("c", "REINFORCEMENT_1")], "origin") },
    { at: 130, kind: "disposition", data: disposition(2, 30, ["a", "b", "c"]) },
  ],
};

describe("causal Take C replay", () => {
  it("accepts only simulator-scoped causal provenance", () => {
    expect(isCausalTakeCCapture(CAPTURE)).toBe(true);
    expect(
      isCausalTakeCCapture({
        ...CAPTURE,
        proof_scope: { ...CAPTURE.proof_scope, px4_disposition_claim: true },
      })
    ).toBe(false);
  });

  it("time-dilates presentation without inventing intermediate physical state", () => {
    const beforeFailure = foldCausalTakeC(99 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    expect(beforeFailure.units.find((entry) => entry.agent_id === "a")?.geo.lat).toBe(44.7);

    const afterFailure = foldCausalTakeC(100 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    const failed = afterFailure.units.find((entry) => entry.agent_id === "a");
    expect(failed?.fsm_state).toBe("OFFLINE");
    expect(failed?.geo.lat).toBe(44.702);
    expect(causalTakeCDurationMs(CAPTURE)).toBe(200 * TAKE_C_PLAYBACK_SCALE);
  });

  it("renders only the latest server-issued disposition for the objective", () => {
    const beforeReinforcement = foldCausalTakeC(100 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    expect(beforeReinforcement.dispositions).toMatchObject([{ revision: 1, radius_m: 22 }]);

    const afterReinforcement = foldCausalTakeC(150 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    expect(afterReinforcement.dispositions).toMatchObject([{ revision: 2, radius_m: 30 }]);
    expect(afterReinforcement.dispositions[0].assignments.map((slot) => slot.agent_id)).toEqual([
      "a",
      "b",
      "c",
    ]);
  });

  it("keeps objective demand on the origin group instead of summing reinforcement demand", () => {
    const slice = foldCausalTakeC(150 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    const view = buildAuthorityView(slice);
    const objective = view.objectives.find((entry) => entry.key === "objective-causal");

    expect(objective?.swarms).toHaveLength(2);
    expect(objective?.requestedMembers).toBe(3);
    expect(objective?.swarms[1].requestedMembers).toBe(1);
  });

  it("folds runtime latest and append-only log with live-provider semantics", () => {
    const slice = foldCausalTakeC(50 * TAKE_C_PLAYBACK_SCALE, CAPTURE);
    expect(slice.missionRuntime).toEqual([runtime]);
    expect(slice.missionRuntimeLog).toEqual([runtime]);
  });
});
