import { describe, expect, it } from "vitest";

import { FORBIDDEN_WORDS } from "@/lib/copy";
import type {
  CompositionSlot,
  ObjectiveAuthority,
  ObjectiveState,
  SwarmComposition,
} from "@/lib/authority";

import { narrationFor } from "../NarrationStrip";

function slot(over: Partial<CompositionSlot> = {}): CompositionSlot {
  return {
    index: 1,
    role: "PRIMARY_OBSERVER",
    roleIsAssigned: true,
    agentId: "mav-004",
    missionId: "mission-1",
    memberState: "ACTIVE",
    phase: "EN_ROUTE",
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

function objective(
  state: ObjectiveState,
  over: Partial<ObjectiveAuthority> = {}
): ObjectiveAuthority {
  const slots = [
    slot(),
    slot({ index: 2, role: "SECONDARY_OBSERVER", agentId: "mav-003" }),
    slot({ index: 3, role: "OVERWATCH", agentId: "mav-002" }),
  ];
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
    groupStateLabel: state,
    swarms: [
      swarm({
        state: state === "ADAPTING" ? "ADAPTING" : "EXECUTING",
        slots,
      }),
    ],
    requestedMembers: 3,
    slots,
    activeMembers: 3,
    state,
    active: state !== "VERIFIED" && state !== "FAILED",
    trace: [],
    routes: [],
    latestProof: null,
    decisionAt: "2026-08-15T17:28:52.000Z",
    ...over,
  };
}

describe("narrationFor", () => {
  it("says nothing about an objective before there is one", () => {
    expect(narrationFor(null, { phase: "idle" })).toBe("AWAITING FLEET STATE");
  });

  it("follows the objective through composition and execution in product nouns", () => {
    expect(narrationFor(objective("COMPOSING"), { phase: "idle" })).toBe(
      "OBJECTIVE DETECTED · SWARMOS COMPOSING SWARM"
    );
    expect(narrationFor(objective("EXECUTING"), { phase: "idle" })).toBe(
      "SWARM 01 EXECUTING · 03 / 03 ROLES COVERED"
    );
    expect(narrationFor(objective("VERIFIED"), { phase: "idle" })).toBe(
      "OBJECTIVE VERIFIED · MISSION COMPLETE"
    );
  });

  it("drops objective coverage when a role holder has failed", () => {
    const degradedSlots = [
      slot(),
      slot({
        index: 2,
        role: "SECONDARY_OBSERVER",
        agentId: "mav-003",
        memberState: "FAILED",
      }),
      slot({ index: 3, role: "OVERWATCH", agentId: "mav-002" }),
    ];
    const degraded = objective("EXECUTING", {
      slots: degradedSlots,
      swarms: [swarm({ slots: degradedSlots })],
    });
    expect(narrationFor(degraded, { phase: "idle" })).toBe(
      "SWARM 01 EXECUTING · 02 / 03 ROLES COVERED"
    );
  });

  it("never claims a swarm on a single-subunit objective", () => {
    const single = objective("EXECUTING", {
      groupId: null,
      swarms: [],
      requestedMembers: 1,
      slots: [slot({ role: "VERIFY", roleIsAssigned: false, groupId: null })],
    });
    expect(narrationFor(single, { phase: "idle" })).toBe(
      "SINGLE SUBUNIT ON OBJECTIVE · 01 / 01 ASSIGNED"
    );
  });

  it("lets the adaptation beat outrank the settled state", () => {
    expect(
      narrationFor(objective("EXECUTING"), {
        phase: "adapting",
        role: "SECONDARY_OBSERVER",
        lostAgent: "mav-003",
      })
    ).toBe("SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT");

    expect(
      narrationFor(objective("EXECUTING"), {
        phase: "restored",
        role: "SECONDARY_OBSERVER",
        fromAgent: "mav-003",
        toAgent: "mav-001",
        active: 3,
        required: 3,
      })
    ).toBe("SUBUNIT REPLACED · SWARM RESTORED");
  });

  it("still announces adaptation after the beat timer expires", () => {
    expect(narrationFor(objective("ADAPTING"), { phase: "idle" })).toBe(
      "SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT"
    );
  });

  it("states why the second swarm appears while it is composing", () => {
    const reinforced = objective("EXECUTING", {
      swarms: [
        swarm(),
        swarm({
          index: 2,
          groupId: "group-2",
          reinforcesGroupId: "group-1",
          requestedMembers: 2,
          composedMembers: 0,
          heldMembers: 0,
          underStrength: true,
          stateLabel: "FORMING",
          state: "COMPOSING",
        }),
      ],
    });
    expect(narrationFor(reinforced, { phase: "idle" })).toBe(
      "REINFORCEMENT REQUIRED · SWARM 02 DISPATCHED"
    );
  });

  it("shows the formation reconfiguring while the reinforcement is inbound", () => {
    const inbound = objective("EXECUTING", {
      swarms: [
        swarm(),
        swarm({
          index: 2,
          groupId: "group-2",
          reinforcesGroupId: "group-1",
          requestedMembers: 2,
          composedMembers: 2,
          heldMembers: 2,
          slots: [
            slot({
              groupId: "group-2",
              swarmIndex: 2,
              reinforcement: true,
              phase: "EN_ROUTE",
            }),
          ],
        }),
      ],
    });
    expect(narrationFor(inbound, { phase: "idle" })).toBe(
      "SWARM 02 EN ROUTE · FORMATION RECONFIGURING"
    );
  });

  it("calls the swarms coordinated only once reinforcement reaches station", () => {
    const reinforcementSlots = [
      slot({
        groupId: "group-2",
        swarmIndex: 2,
        reinforcement: true,
        phase: "ON_STATION",
        role: "SECONDARY_OBSERVER",
        agentId: "mav-011",
      }),
      slot({
        index: 2,
        groupId: "group-2",
        swarmIndex: 2,
        reinforcement: true,
        phase: "ON_STATION",
        role: "OVERWATCH",
        agentId: "mav-012",
      }),
    ];
    const combined = objective("EXECUTING", {
      requestedMembers: 5,
      slots: [
        slot(),
        slot({ index: 2, role: "SECONDARY_OBSERVER", agentId: "mav-003" }),
        slot({ index: 3, role: "OVERWATCH", agentId: "mav-002" }),
        ...reinforcementSlots,
      ],
      swarms: [
        swarm(),
        swarm({
          index: 2,
          groupId: "group-2",
          reinforcesGroupId: "group-1",
          requestedMembers: 2,
          composedMembers: 2,
          heldMembers: 2,
          slots: reinforcementSlots,
        }),
      ],
    });
    expect(narrationFor(combined, { phase: "idle" })).toBe(
      "02 SWARMS COORDINATED · 03 / 03 ROLES COVERED"
    );
  });

  it("states a composition shortfall rather than leaving it to a count", () => {
    const partialSlots = [slot(), slot({ index: 2, role: "OVERWATCH", agentId: "mav-002" })];
    const partial = objective("EXECUTING", {
      slots: partialSlots,
      swarms: [
        swarm({
          slots: partialSlots,
          composedMembers: 2,
          heldMembers: 2,
          underStrength: true,
        }),
      ],
    });
    expect(narrationFor(partial, { phase: "idle" })).toBe(
      "SWARM 01 UNDER STRENGTH · 02 / 03 ROLES COVERED"
    );
  });

  it("lets the adaptation beat outrank a shortfall it is fixing", () => {
    const partialSlots = [slot(), slot({ index: 2, role: "OVERWATCH", agentId: "mav-002" })];
    const partial = objective("EXECUTING", {
      slots: partialSlots,
      swarms: [
        swarm({
          slots: partialSlots,
          composedMembers: 2,
          heldMembers: 2,
          underStrength: true,
        }),
      ],
    });
    expect(
      narrationFor(partial, {
        phase: "adapting",
        role: "OVERWATCH",
        lostAgent: "mav-002",
      })
    ).toBe("SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT");
  });

  it("speaks no forbidden word in any line it can produce", () => {
    const reinforcementOnStation = slot({
      groupId: "group-2",
      swarmIndex: 2,
      reinforcement: true,
      phase: "ON_STATION",
    });
    const lines = [
      narrationFor(null, { phase: "idle" }),
      narrationFor(objective("COMPOSING"), { phase: "idle" }),
      narrationFor(objective("EXECUTING"), { phase: "idle" }),
      narrationFor(objective("ADAPTING"), { phase: "idle" }),
      narrationFor(objective("VERIFIED"), { phase: "idle" }),
      narrationFor(objective("FAILED"), { phase: "idle" }),
      narrationFor(
        objective("EXECUTING", { groupId: null, swarms: [], requestedMembers: 1 }),
        { phase: "idle" }
      ),
      narrationFor(
        objective("EXECUTING", {
          swarms: [
            swarm(),
            swarm({
              index: 2,
              groupId: "group-2",
              reinforcesGroupId: "group-1",
              state: "COMPOSING",
            }),
          ],
        }),
        { phase: "idle" }
      ),
      narrationFor(
        objective("EXECUTING", {
          swarms: [
            swarm(),
            swarm({
              index: 2,
              groupId: "group-2",
              reinforcesGroupId: "group-1",
              requestedMembers: 2,
              slots: [reinforcementOnStation],
            }),
          ],
        }),
        { phase: "idle" }
      ),
      narrationFor(objective("EXECUTING"), {
        phase: "adapting",
        role: "SECONDARY_OBSERVER",
        lostAgent: "mav-003",
      }),
      narrationFor(objective("EXECUTING"), {
        phase: "restored",
        role: "SECONDARY_OBSERVER",
        fromAgent: "mav-003",
        toAgent: "mav-001",
        active: 3,
        required: 3,
      }),
    ];

    const offences: { word: string; line: string }[] = [];
    for (const line of lines) {
      for (const word of FORBIDDEN_WORDS) {
        // eslint-disable-next-line security/detect-non-literal-regexp -- bounded scan over an in-repo const list
        if (new RegExp(`\\b${word}\\b`, "i").test(line)) offences.push({ word, line });
      }
      expect(line).not.toMatch(/\b(manual|pilot|fly|land now)\b/i);
    }
    expect(offences, JSON.stringify(offences)).toEqual([]);
  });
});
