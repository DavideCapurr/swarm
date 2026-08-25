import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { buildAuthorityView, type AuthorityInput } from "@/lib/authority";
import type {
  ExecutionGroup,
  MissionDecision,
  MissionDecisionReview,
  UnitState,
} from "@/lib/api";

import { MissionAuthorityPanel } from "../MissionAuthorityPanel";

/**
 * An objective holding more than one swarm, as the panel states it.
 *
 * Built through `buildAuthorityView` rather than from a hand-written view
 * model: the thing under test is whether the panel says what SwarmOS published,
 * and a fixture that skipped the grouping could pass while the grouping was
 * wrong.
 */

function unit(agentId: string): UnitState {
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
  };
}

function member(agentId: string, role: string, missionId: string, ts: string) {
  return {
    agent_id: agentId,
    role,
    mission_id: missionId,
    state: "ACTIVE" as const,
    score: 2.2,
    score_breakdown: {},
    replaces_agent_id: null,
    ts,
  };
}

/** Asked for three roles, filled two — ADR-0012 partial-strength composition. */
const ORIGIN: ExecutionGroup = {
  id: "group-1",
  objective_mission_id: "parent-1",
  objective_kind: "COOPERATIVE_VERIFY",
  anomaly_id: "anom-1",
  requested_members: 3,
  state: "ACTIVE",
  failure_reason: null,
  ts: "2026-08-15T17:29:00.000Z",
  members: [
    member("mav-004", "PRIMARY_OBSERVER", "child-a", "2026-08-15T17:29:00.000Z"),
    member("mav-002", "OVERWATCH", "child-c", "2026-08-15T17:29:00.000Z"),
  ],
};

const REINFORCEMENT: ExecutionGroup = {
  id: "group-2",
  objective_mission_id: "parent-1",
  objective_kind: "COOPERATIVE_VERIFY",
  anomaly_id: "anom-1",
  reinforces_group_id: "group-1",
  requested_members: 1,
  state: "ACTIVE",
  failure_reason: null,
  ts: "2026-08-15T17:29:40.000Z",
  members: [
    member("mav-001", "SECONDARY_OBSERVER", "child-d", "2026-08-15T17:29:40.000Z"),
  ],
};

function panel(
  groups: ExecutionGroup[],
  decision?: MissionDecision,
  onReview?: (decisionId: string, action: "approve" | "reject") => Promise<void>,
  decisionReview?: MissionDecisionReview
) {
  const input: AuthorityInput = {
    units: [unit("mav-001"), unit("mav-002"), unit("mav-004")],
    anomalies: [],
    allocations: [],
    executionGroups: groups,
    missions: [],
    missionRuntime: [],
    missionRuntimeLog: [],
    payloadEvents: [],
  };
  const view = buildAuthorityView(input);
  const focused = view.objectives.find((o) => o.key === view.defaultFocusKey) ?? null;
  return render(
    <MissionAuthorityPanel
      objectives={view.objectives}
      focused={focused}
      beat={{ phase: "idle" }}
      capacity={view.capacity}
      channels={[]}
      decision={decision}
      decisionReview={decisionReview}
      canReview={Boolean(onReview)}
      onReview={onReview}
      onSelectObjective={() => {}}
    />
  );
}

describe("an objective holding several swarms", () => {
  it("stays one tab, because it is one objective", () => {
    const { queryByTestId } = panel([ORIGIN, REINFORCEMENT]);
    // Two groups, one objective. A second tab here would be the surface
    // reporting a second thing SwarmOS is responding to, which it is not.
    expect(queryByTestId("objective-switch")).toBeNull();
  });

  it("gives each swarm its own identity and its own strength", () => {
    const { getByTestId } = panel([ORIGIN, REINFORCEMENT]);

    expect(getByTestId("swarm-group-1")).toHaveTextContent("execution group");
    expect(getByTestId("swarm-strength-group-1")).toHaveTextContent("02 / 03");
    expect(getByTestId("swarm-group-2")).toHaveTextContent("reinforcement");
    // Provenance, published: which swarm this one was sent to reinforce.
    expect(getByTestId("swarm-group-2")).toHaveTextContent("reinforces EG-group-1");
    expect(getByTestId("swarm-strength-group-2")).toHaveTextContent("01 / 01");
  });

  it("reads the under-strength swarm in amber and leaves the other alone", () => {
    const { getByTestId } = panel([ORIGIN, REINFORCEMENT]);

    expect(getByTestId("swarm-strength-group-1").className).toContain("text-launch-amber");
    expect(getByTestId("swarm-strength-group-2").className).not.toContain(
      "text-launch-amber"
    );
  });

  it("lists both swarms' roles, scoped so neither can shadow the other", () => {
    const { getByTestId } = panel([ORIGIN, REINFORCEMENT]);

    expect(getByTestId("slot-group-1-PRIMARY_OBSERVER")).toHaveTextContent("mav-004");
    expect(getByTestId("slot-group-1-OVERWATCH")).toHaveTextContent("mav-002");
    expect(getByTestId("slot-group-2-SECONDARY_OBSERVER")).toHaveTextContent("mav-001");
  });

  it("keeps a single swarm's header exactly as it was", () => {
    // The objective's own ROLES HELD already is the swarm's strength here, and
    // a per-swarm header would say it twice.
    const { queryByTestId, getByText } = panel([ORIGIN]);

    expect(queryByTestId("swarm-group-1")).toBeNull();
    expect(getByText("execution group")).toBeInTheDocument();
    expect(queryByTestId("slot-group-1-PRIMARY_OBSERVER")).not.toBeNull();
  });

  it("renders server reasons and reviews the exact immutable decision", () => {
    const onReview = vi.fn(async () => {});
    const decision: MissionDecision = {
      decision_id: "decision-1",
      objective_id: "parent-1",
      objective_revision: 1,
      decision_kind: "LAUNCH_COMPOSITION",
      requirements_snapshot: {},
      constraints_snapshot: {},
      candidate_assessments: [],
      selected_assignments: [],
      full_requirements_satisfied: true,
      authority_grant_id: null,
      authority_grant_revision: null,
      authority_verdict: "review_required",
      authority_reasons: ["EXECUTOR_OUTSIDE_DELEGATION"],
      supersedes_decision_id: null,
      created_at: "2026-08-15T17:29:00.000Z",
    };
    const { getByTestId, getByText } = panel([ORIGIN], decision, onReview);

    expect(getByTestId("mission-decision-boundary")).toHaveTextContent(
      "EXECUTOR_OUTSIDE_DELEGATION"
    );
    fireEvent.click(getByText("APPROVE EXACT"));
    expect(onReview).toHaveBeenCalledWith("decision-1", "approve");
  });

  it("renders the immutable review actor and removes stale review controls", () => {
    const onReview = vi.fn(async () => {});
    const decision: MissionDecision = {
      decision_id: "decision-1",
      objective_id: "parent-1",
      objective_revision: 1,
      decision_kind: "LAUNCH_COMPOSITION",
      requirements_snapshot: {},
      constraints_snapshot: {},
      candidate_assessments: [],
      selected_assignments: [],
      full_requirements_satisfied: true,
      authority_grant_id: "grant-1",
      authority_grant_revision: 1,
      authority_verdict: "review_required",
      authority_reasons: ["REVIEW_REQUIRED"],
      supersedes_decision_id: null,
      created_at: "2026-08-15T17:29:00.000Z",
    };
    const review: MissionDecisionReview = {
      review_id: "review-1",
      decision_id: decision.decision_id,
      objective_id: decision.objective_id,
      action: "approve",
      actor_id: "risk-owner",
      replacement_decision_id: null,
      created_at: "2026-08-15T17:29:01.000Z",
    };

    const { getByTestId, queryByText } = panel(
      [ORIGIN],
      decision,
      onReview,
      review
    );

    expect(getByTestId("mission-decision-review")).toHaveTextContent(
      "APPROVED EXACT · risk-owner"
    );
    expect(queryByText("APPROVE EXACT")).toBeNull();
    expect(queryByText("REJECT")).toBeNull();
  });
});
