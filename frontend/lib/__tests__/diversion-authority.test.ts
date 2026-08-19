import { describe, expect, it } from "vitest";

import type { ExecutionGroup, UnitState } from "../api";
import { buildAuthorityView, type AuthorityInput } from "../authority";

function unit(agentId: string, missionId: string): UnitState {
  return {
    agent_id: agentId,
    vendor: "simulator",
    model: "thin-executor",
    fsm_state: "EN_ROUTE",
    battery_pct: 90,
    geo: { lat: 45, lon: 9, alt_m: 40 },
    current_mission_id: missionId,
    current_sector_id: null,
    link_quality: 1,
    heading_deg: 0,
    altitude_agl_m: 40,
    dock_id: "dock-01",
    ts: "2026-08-19T13:00:03.000Z",
  };
}

const DONOR: ExecutionGroup = {
  id: "donor-group",
  objective_mission_id: "coverage-objective",
  objective_kind: "COVER",
  anomaly_id: null,
  requested_members: 2,
  members: [
    {
      agent_id: "agent-1",
      role: "COVERAGE_SLICE_1",
      mission_id: "donor-child-1",
      state: "DIVERTED",
      score: 2,
      score_breakdown: {},
      replaces_agent_id: null,
      ts: "2026-08-19T13:00:00.000Z",
    },
    {
      agent_id: "agent-2",
      role: "COVERAGE_SLICE_2",
      mission_id: "donor-child-2",
      state: "ACTIVE",
      score: 1.9,
      score_breakdown: {},
      replaces_agent_id: null,
      ts: "2026-08-19T13:00:00.000Z",
    },
  ],
  state: "DEGRADED",
  failure_reason: null,
  ts: "2026-08-19T13:00:02.000Z",
};

const RESPONSE: ExecutionGroup = {
  id: "response-group",
  objective_mission_id: "response-objective",
  objective_kind: "COOPERATIVE_VERIFY",
  anomaly_id: "alarm-1",
  requested_members: 1,
  members: [
    {
      agent_id: "agent-1",
      role: "PRIMARY_OBSERVER",
      mission_id: "response-child-1",
      state: "ACTIVE",
      score: 3,
      score_breakdown: {},
      replaces_agent_id: null,
      diverted_from_mission_id: "donor-child-1",
      diverted_from_objective_id: "coverage-objective",
      ts: "2026-08-19T13:00:02.000Z",
    },
  ],
  state: "ACTIVE",
  failure_reason: null,
  ts: "2026-08-19T13:00:02.000Z",
};

function input(): AuthorityInput {
  return {
    units: [
      unit("agent-1", "response-child-1"),
      unit("agent-2", "donor-child-2"),
    ],
    anomalies: [],
    allocations: [],
    executionGroups: [DONOR, RESPONSE],
    missions: [],
    missionRuntime: [],
    missionRuntimeLog: [],
    payloadEvents: [],
  };
}

describe("diversion truth", () => {
  it("does not double-count transferred capacity and preserves provenance", () => {
    const view = buildAuthorityView(input());
    const donor = view.objectives.find((objective) => objective.groupId === DONOR.id);
    const response = view.objectives.find(
      (objective) => objective.groupId === RESPONSE.id
    );

    expect(donor?.swarms[0].heldMembers).toBe(1);
    expect(donor?.swarms[0].underStrength).toBe(true);

    const diverted = donor?.slots.find(
      (slot) => slot.role === "COVERAGE_SLICE_1"
    );
    expect(diverted?.agentId).toBeNull();
    expect(diverted?.memberState).toBe("DIVERTED");
    expect(diverted?.divertedAgentId).toBe("agent-1");

    const receiver = response?.slots[0];
    expect(receiver?.agentId).toBe("agent-1");
    expect(receiver?.divertedFromMissionId).toBe("donor-child-1");
    expect(receiver?.divertedFromObjectiveId).toBe("coverage-objective");

    const capacity = new Map(view.capacity.map((row) => [row.agentId, row]));
    expect(capacity.get("agent-1")?.commitment).toBe("ASSIGNED");
    expect(capacity.get("agent-1")?.objectiveKey).toBe(RESPONSE.id);
    expect(capacity.get("agent-2")?.objectiveKey).toBe(DONOR.id);
  });
});
