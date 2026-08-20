import { describe, expect, it } from "vitest";

import type { DispositionDecision } from "@/lib/api";
import type { CompositionSlot, ObjectiveAuthority, SwarmComposition } from "@/lib/authority";

import { narrationFor } from "../NarrationStrip";

/**
 * A minimal synthetic fixture rather than a sample off the recorded Take C
 * timeline: real Take C's reinforcement window now overlaps continuously with
 * sweep-subunit diversion, so no real timestamp isolates "reinforcement
 * inbound, nothing else changing" on its own. This tests that boundary
 * directly instead of chasing a timestamp that may drift again.
 */
function slot(over: Partial<CompositionSlot> = {}): CompositionSlot {
  return {
    index: 1,
    role: "PRIMARY_OBSERVER",
    roleIsAssigned: true,
    agentId: "mav-004",
    missionId: "mission-1",
    memberState: "ACTIVE",
    phase: "ON_STATION",
    proof: null,
    score: 2.26,
    replacesAgentId: null,
    replacedAgentId: null,
    divertedAgentId: null,
    divertedFromMissionId: null,
    divertedFromObjectiveId: null,
    adapting: false,
    groupId: "group-1",
    swarmIndex: 1,
    reinforcement: false,
    ...over,
  };
}

function swarm(over: Partial<SwarmComposition> = {}): SwarmComposition {
  return {
    index: 1,
    groupId: "group-1",
    label: "EG-group-1",
    reinforcesGroupId: null,
    requestedMembers: 3,
    slots: [],
    composedMembers: 3,
    heldMembers: 3,
    underStrength: false,
    stateLabel: "ACTIVE",
    state: "EXECUTING",
    composedAt: "2026-08-15T17:28:52.000Z",
    ...over,
  };
}

function reinforcementInbound(): ObjectiveAuthority {
  const primarySlots = [slot(), slot({ index: 2, role: "SECONDARY_OBSERVER", agentId: "mav-003" })];
  const inboundSlot = slot({
    groupId: "group-2",
    swarmIndex: 2,
    reinforcement: true,
    phase: "EN_ROUTE",
  });
  return {
    key: "group-1",
    index: 1,
    kind: "INTRUSION",
    label: "M-8582edb3",
    missionId: "8582edb3",
    anomalyId: "anom-1",
    confidence: 0.99,
    detectedAt: null,
    detection: null,
    geo: null,
    groupId: "group-1",
    groupStateLabel: "EXECUTING",
    swarms: [
      swarm({ slots: primarySlots }),
      swarm({
        index: 2,
        groupId: "group-2",
        reinforcesGroupId: "group-1",
        requestedMembers: 1,
        composedMembers: 1,
        heldMembers: 1,
        slots: [inboundSlot],
      }),
    ],
    requestedMembers: 2,
    slots: [...primarySlots, inboundSlot],
    excludedUnits: [],
    activeMembers: 3,
    state: "EXECUTING",
    active: true,
    trace: [],
    routes: [],
    latestProof: null,
    decisionAt: "2026-08-15T17:28:52.000Z",
  };
}

function reinforcementDisposition(objectiveMissionId: string): DispositionDecision {
  return {
    objective_mission_id: objectiveMissionId,
    revision: 2,
    reason: "REINFORCEMENT",
    center: { lat: 47.398, lon: 8.546, alt_m: 0 },
    active_members: 3,
    radius_m: 30,
    assignments: [],
    ts: "2026-08-15T17:29:20.000Z",
  };
}

describe("disposition truth boundary", () => {
  it("uses the server-issued revision and radius instead of inferring a formation change", () => {
    const objective = reinforcementInbound();

    const line = narrationFor(
      objective,
      { phase: "idle" },
      reinforcementDisposition(objective.missionId)
    );

    expect(line).toBe("SWARM 02 EN ROUTE · DISPOSITION R02 ISSUED · R 30 M");
    expect(line).not.toContain("FORMATION RECONFIGURING");
  });

  it("does not invent formation truth when no disposition frame exists", () => {
    const line = narrationFor(reinforcementInbound(), { phase: "idle" });
    expect(line).toBe("SWARM 02 EN ROUTE");
    expect(line).not.toContain("FORMATION");
    expect(line).not.toContain("DISPOSITION");
  });
});
