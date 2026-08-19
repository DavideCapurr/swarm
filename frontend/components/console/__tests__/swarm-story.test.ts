import { describe, expect, it } from "vitest";

import { buildAuthorityView } from "@/lib/authority";
import { foldTakeC, takeCFrames } from "@/lib/demo-frames";
import { augmentTakeCForSwarmStory } from "@/lib/demo-swarm-story";

import { narrationFor } from "../NarrationStrip";

function viewAt(atMs: number) {
  const slice = augmentTakeCForSwarmStory(foldTakeC(atMs, takeCFrames()), atMs);
  const view = buildAuthorityView(slice);
  const focused = view.objectives.find((objective) => objective.key === view.defaultFocusKey) ?? null;
  return { view, focused };
}

describe("take C swarm story", () => {
  it("starts with one under-strength swarm", () => {
    const { focused } = viewAt(10_000);
    expect(focused?.swarms).toHaveLength(1);
    expect(focused?.swarms[0].heldMembers).toBe(2);
    expect(focused?.swarms[0].requestedMembers).toBe(3);
    expect(narrationFor(focused, { phase: "idle" })).toContain("SWARM 01 UNDER STRENGTH");
  });

  it("dispatches a second swarm with two live subunits", () => {
    const { focused } = viewAt(20_000);
    expect(focused?.swarms).toHaveLength(2);
    const reinforcement = focused?.swarms[1];
    expect(reinforcement?.requestedMembers).toBe(2);
    expect(reinforcement?.heldMembers).toBe(2);
    expect(reinforcement?.slots.map((slot) => slot.agentId)).toEqual(
      expect.arrayContaining(["mav-003", "mav-035"])
    );
  });

  it("reads as coordinated at the original 3-role objective, never 3/5", () => {
    const { focused } = viewAt(20_000);
    expect(narrationFor(focused, { phase: "idle" })).toBe(
      "02 SWARMS COORDINATED · 03 / 03 ROLES COVERED"
    );
  });

  it("keeps the support subunit alive when mav-003 fails", () => {
    const { focused } = viewAt(21_500);
    const reinforcement = focused?.swarms[1];
    const failed = reinforcement?.slots.find((slot) => slot.agentId === "mav-003");
    const support = reinforcement?.slots.find((slot) => slot.agentId === "mav-035");
    expect(failed?.adapting).toBe(true);
    expect(support?.memberState).toBe("ACTIVE");
  });
});
