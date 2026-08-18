import { describe, expect, it } from "vitest";

import type {
  AllocationDecision,
  ExecutionGroup,
  MissionRuntimeEvent,
  UnitState,
} from "../api";
import { buildAuthorityView, type AuthorityInput } from "../authority";

/**
 * The composition layer is where this surface could most easily start inventing
 * things — a role nobody assigned, a replacement nobody made, spare capacity
 * that is actually committed. These tests hold it to server truth.
 */

function unit(agentId: string, over: Partial<UnitState> = {}): UnitState {
  return {
    agent_id: agentId,
    vendor: "mavlink",
    model: "px4-iris-sitl",
    fsm_state: "EN_ROUTE",
    battery_pct: 90,
    geo: { lat: 47.398, lon: 8.546, alt_m: 30 },
    current_mission_id: null,
    current_sector_id: null,
    link_quality: 1,
    heading_deg: 40,
    altitude_agl_m: 30,
    dock_id: "dock-01",
    ts: "2026-08-15T17:29:00.000Z",
    ...over,
  };
}

function runtime(
  missionId: string,
  agentId: string,
  phase: string,
  ts: string
): MissionRuntimeEvent {
  return {
    id: `${missionId}-${phase}`,
    mission_id: missionId,
    agent_id: agentId,
    phase,
    progress_pct: 10,
    evidence: null,
    error: null,
    ts,
  };
}

const GROUP: ExecutionGroup = {
  id: "group-1",
  objective_mission_id: "parent-1",
  objective_kind: "COOPERATIVE_VERIFY",
  anomaly_id: "anom-1",
  requested_members: 3,
  state: "ACTIVE",
  failure_reason: null,
  ts: "2026-08-15T17:29:14.000Z",
  members: [
    {
      agent_id: "mav-004",
      role: "PRIMARY_OBSERVER",
      mission_id: "child-a",
      state: "ACTIVE",
      score: 2.26,
      score_breakdown: {},
      replaces_agent_id: null,
      ts: "2026-08-15T17:29:00.000Z",
    },
    {
      agent_id: "mav-003",
      role: "SECONDARY_OBSERVER",
      mission_id: "child-b",
      state: "REPLACED",
      score: 2.25,
      score_breakdown: {},
      replaces_agent_id: null,
      ts: "2026-08-15T17:29:07.000Z",
    },
    {
      agent_id: "mav-002",
      role: "OVERWATCH",
      mission_id: "child-c",
      state: "ACTIVE",
      score: 2.25,
      score_breakdown: {},
      replaces_agent_id: null,
      ts: "2026-08-15T17:29:00.000Z",
    },
    {
      agent_id: "mav-001",
      role: "SECONDARY_OBSERVER",
      mission_id: "child-d",
      state: "ACTIVE",
      score: 2.25,
      score_breakdown: {},
      replaces_agent_id: "mav-003",
      ts: "2026-08-15T17:29:14.000Z",
    },
  ],
};

/** A child mission's own award. The group is the objective; this is not. */
function childAward(missionId: string, agentId: string): AllocationDecision {
  return {
    mission_id: missionId,
    mission_kind: "VERIFY",
    anomaly_id: "anom-1",
    mode: "auction",
    eligible_units: [],
    excluded_units: [],
    winner_agent_id: agentId,
    winner_score: 2.25,
    ts: "2026-08-15T17:29:00.000Z",
  };
}

function input(over: Partial<AuthorityInput> = {}): AuthorityInput {
  return {
    units: [unit("mav-001"), unit("mav-002"), unit("mav-003"), unit("mav-004")],
    anomalies: [],
    allocations: [],
    executionGroups: [],
    missions: [],
    missionRuntime: [],
    missionRuntimeLog: [],
    payloadEvents: [],
    ...over,
  };
}

describe("execution-group objectives", () => {
  it("treats the group as the objective and hides its child awards", () => {
    const view = buildAuthorityView(
      input({
        executionGroups: [GROUP],
        allocations: [
          childAward("child-a", "mav-004"),
          childAward("child-c", "mav-002"),
          childAward("child-d", "mav-001"),
        ],
      })
    );

    expect(view.objectives).toHaveLength(1);
    expect(view.objectives[0].groupId).toBe("group-1");
    expect(view.objectives[0].requestedMembers).toBe(3);
  });

  it("holds one slot per role, with the live holder and the displaced one", () => {
    const view = buildAuthorityView(input({ executionGroups: [GROUP] }));
    const slots = view.objectives[0].slots;

    expect(slots.map((slot) => slot.role)).toEqual([
      "PRIMARY_OBSERVER",
      "SECONDARY_OBSERVER",
      "OVERWATCH",
    ]);

    const secondary = slots[1];
    expect(secondary.agentId).toBe("mav-001");
    expect(secondary.replacesAgentId).toBe("mav-003");
    expect(secondary.replacedAgentId).toBe("mav-003");
    expect(secondary.roleIsAssigned).toBe(true);
  });

  it("marks the replaced agent unavailable rather than assigned", () => {
    const view = buildAuthorityView(input({ executionGroups: [GROUP] }));
    const rows = new Map(view.capacity.map((row) => [row.agentId, row]));

    expect(rows.get("mav-003")?.commitment).toBe("UNAVAILABLE");
    expect(rows.get("mav-003")?.replacedOut).toBe(true);
    expect(rows.get("mav-001")?.commitment).toBe("ASSIGNED");
    expect(rows.get("mav-001")?.role).toBe("SECONDARY_OBSERVER");
  });

  it("reports ADAPTING while a member has failed and no replacement is in", () => {
    const degraded: ExecutionGroup = {
      ...GROUP,
      state: "DEGRADED",
      members: [
        GROUP.members[0],
        { ...GROUP.members[1], state: "FAILED" },
        GROUP.members[2],
      ],
    };
    const view = buildAuthorityView(input({ executionGroups: [degraded] }));

    expect(view.objectives[0].state).toBe("ADAPTING");
    expect(view.objectives[0].slots[1].adapting).toBe(true);
    // The trace has to say an adaptation is under way, not that one completed.
    const adapted = view.objectives[0].trace.find((stage) => stage.name === "ADAPTED");
    expect(adapted?.state).toBe("active");
  });

  it("reads ADAPTED as not-required, not pending, when nothing was ever replaced", () => {
    // A clean objective was never going to need this stage. `pending` reads
    // as an unfinished step; `not_required` is the honest fact — SwarmOS
    // never had a role to recompose here.
    const clean: ExecutionGroup = {
      ...GROUP,
      members: [GROUP.members[0], GROUP.members[2]],
      requested_members: 2,
    };
    const view = buildAuthorityView(input({ executionGroups: [clean] }));

    const adapted = view.objectives[0].trace.find((stage) => stage.name === "ADAPTED");
    expect(adapted?.state).toBe("not_required");
  });
});

describe("single-executor objectives", () => {
  const decision: AllocationDecision = {
    mission_id: "mission-1",
    mission_kind: "VERIFY",
    anomaly_id: "anom-2",
    mode: "auction",
    eligible_units: [],
    excluded_units: [
      {
        agent_id: "mav-002",
        fsm_state: "ON_STATION",
        battery_pct: 88,
        reason: "BUSY",
        active_mission_id: "mission-0",
      },
    ],
    winner_agent_id: "mav-001",
    winner_score: 2.29,
    ts: "2026-08-15T12:00:30.000Z",
  };

  it("names the awarded mission kind rather than inventing a role", () => {
    const view = buildAuthorityView(input({ allocations: [decision] }));
    const slot = view.objectives[0].slots[0];

    expect(slot.role).toBe("VERIFY");
    expect(slot.roleIsAssigned).toBe(false);
    expect(view.objectives[0].groupId).toBeNull();
  });

  it("carries the exclusion reason and the exact blocking mission", () => {
    const view = buildAuthorityView(input({ allocations: [decision] }));
    const excluded = view.capacity.find((row) => row.agentId === "mav-002");

    expect(excluded?.excluded).toEqual({
      reason: "BUSY",
      activeMissionId: "mission-0",
    });
  });

  it("counts capacity SwarmOS left out as spare", () => {
    const view = buildAuthorityView(input({ allocations: [decision] }));
    const spare = view.capacity.filter((row) => row.commitment === "SPARE");

    expect(spare.map((row) => row.agentId)).toContain("mav-004");
    expect(spare.map((row) => row.agentId)).not.toContain("mav-001");
  });

  it("focuses the newest objective that is still running", () => {
    const older: AllocationDecision = {
      ...decision,
      mission_id: "mission-old",
      anomaly_id: "anom-old",
      winner_agent_id: "mav-004",
      ts: "2026-08-15T12:00:00.000Z",
    };
    const view = buildAuthorityView(
      input({
        allocations: [older, decision],
        missionRuntime: [runtime("mission-old", "mav-004", "DONE", "2026-08-15T12:00:20.000Z")],
      })
    );

    expect(view.objectives.map((o) => o.index)).toEqual([1, 2]);
    expect(view.defaultFocusKey).toBe("mission-1");
  });
});
