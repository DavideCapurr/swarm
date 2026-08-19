import { describe, expect, it } from "vitest";

import { FORBIDDEN_WORDS } from "@/lib/copy";
import type { CompositionSlot, ObjectiveAuthority, ObjectiveState } from "@/lib/authority";

import { narrationFor } from "../NarrationStrip";

/**
 * The narration line is the one element on this surface addressed to somebody
 * who cannot pause it, which makes it the one element most able to say
 * something the rest of the surface is not saying. These tests hold it to the
 * two rules that keep it honest: it is a function of state SwarmOS published,
 * and it speaks the product's voice.
 */

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
    adapting: false,
    ...over,
  };
}

function objective(
  state: ObjectiveState,
  over: Partial<ObjectiveAuthority> = {}
): ObjectiveAuthority {
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
    requestedMembers: 3,
    slots: [slot(), slot({ index: 2, role: "SECONDARY_OBSERVER", agentId: "mav-003" }), slot({ index: 3, role: "OVERWATCH", agentId: "mav-002" })],
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

  it("follows the objective through composition and execution", () => {
    expect(narrationFor(objective("COMPOSING"), { phase: "idle" })).toBe(
      "OBJECTIVE DETECTED · SWARMOS EVALUATING"
    );
    expect(narrationFor(objective("EXECUTING"), { phase: "idle" })).toBe(
      "EXECUTIONGROUP EXECUTING · 03 / 03 ROLES ACTIVE"
    );
    expect(narrationFor(objective("VERIFIED"), { phase: "idle" })).toBe(
      "OBJECTIVE VERIFIED · MISSION COMPLETE"
    );
  });

  it("drops the role count when a holder has failed, as the panel does", () => {
    const degraded = objective("EXECUTING", {
      slots: [
        slot(),
        slot({ index: 2, role: "SECONDARY_OBSERVER", agentId: "mav-003", memberState: "FAILED" }),
        slot({ index: 3, role: "OVERWATCH", agentId: "mav-002" }),
      ],
    });
    expect(narrationFor(degraded, { phase: "idle" })).toBe(
      "EXECUTIONGROUP EXECUTING · 02 / 03 ROLES ACTIVE"
    );
  });

  it("never claims an ExecutionGroup on a single-executor objective", () => {
    const single = objective("EXECUTING", {
      groupId: null,
      requestedMembers: 1,
      slots: [slot({ role: "VERIFY", roleIsAssigned: false })],
    });
    expect(narrationFor(single, { phase: "idle" })).toBe(
      "SINGLE EXECUTOR ON OBJECTIVE · 01 / 01 ASSIGNED"
    );
  });

  it("lets the beat outrank the settled state, because the beat just changed", () => {
    expect(
      narrationFor(objective("EXECUTING"), {
        phase: "adapting",
        role: "SECONDARY_OBSERVER",
        lostAgent: "mav-003",
      })
    ).toBe("EXECUTOR LOST · SWARMOS SELECTING REPLACEMENT");

    expect(
      narrationFor(objective("EXECUTING"), {
        phase: "restored",
        role: "SECONDARY_OBSERVER",
        fromAgent: "mav-003",
        toAgent: "mav-001",
        active: 3,
        required: 3,
      })
    ).toBe("REPLACEMENT DISPATCHED · GROUP RESTORED");
  });

  it("still announces the adaptation when the beat timer has expired", () => {
    expect(narrationFor(objective("ADAPTING"), { phase: "idle" })).toBe(
      "EXECUTOR LOST · SWARMOS SELECTING REPLACEMENT"
    );
  });

  it("speaks no forbidden word in any line it can produce", () => {
    const lines = [
      narrationFor(null, { phase: "idle" }),
      narrationFor(objective("COMPOSING"), { phase: "idle" }),
      narrationFor(objective("EXECUTING"), { phase: "idle" }),
      narrationFor(objective("ADAPTING"), { phase: "idle" }),
      narrationFor(objective("VERIFIED"), { phase: "idle" }),
      narrationFor(objective("FAILED"), { phase: "idle" }),
      narrationFor(objective("EXECUTING", { groupId: null, requestedMembers: 1 }), {
        phase: "idle",
      }),
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
      // The operator sends intents; nothing here may read as a manual command.
      expect(line).not.toMatch(/\b(manual|pilot|fly|land now)\b/i);
    }
    expect(offences, JSON.stringify(offences)).toEqual([]);
  });
});
