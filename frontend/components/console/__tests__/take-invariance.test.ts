import { describe, expect, it } from "vitest";

import { buildAuthorityView } from "@/lib/authority";
import {
  TAKE_A,
  TAKE_B,
  foldTakeA,
  foldTakeB,
  takeAFrames,
  takeBFrames,
} from "@/lib/demo-frames";

import { narrationFor } from "../NarrationStrip";

/**
 * Historical static bench captures A and B, held to what they already say.
 *
 * Take C is intentionally absent. It is generated from the causal simulator
 * runtime and tested through `causal-take-c.test.ts`, not through authored demo
 * fixtures.
 */
const TAKES = [
  { id: "a", script: TAKE_A, frames: takeAFrames(), fold: foldTakeA },
  { id: "b", script: TAKE_B, frames: takeBFrames(), fold: foldTakeB },
] as const;

const STEP_MS = 500;

function frameAt(take: (typeof TAKES)[number], atMs: number) {
  const view = buildAuthorityView(take.fold(atMs, take.frames as never));
  const focused = view.objectives.find((objective) => objective.key === view.defaultFocusKey) ?? null;
  return { view, focused };
}

describe.each(TAKES)("take $id", (take) => {
  it("dates each objective's composition once and never re-dates it", () => {
    const seen = new Map<string, Set<string>>();
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      for (const objective of frameAt(take, at).view.objectives) {
        const composed = objective.trace.find((stage) => stage.name === "COMPOSED");
        if (composed?.state !== "done") continue;
        const held = seen.get(objective.key) ?? new Set<string>();
        held.add(String(composed.at));
        seen.set(objective.key, held);
      }
    }

    expect(seen.size).toBeGreaterThan(0);
    for (const [key, values] of seen) {
      expect(values.size, `${key} re-dated: ${[...values].join(" → ")}`).toBe(1);
    }
  });

  it("never splits one objective into two, or loses one it was holding", () => {
    let held = 0;
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const count = frameAt(take, at).view.objectives.length;
      expect(count).toBeGreaterThanOrEqual(held);
      held = count;
    }
  });

  it("keeps focus on one objective at a time, and only on one it is holding", () => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const { view, focused } = frameAt(take, at);
      if (view.objectives.length === 0) {
        expect(focused).toBeNull();
        continue;
      }
      expect(focused).not.toBeNull();
      expect(view.objectives.filter((objective) => objective.key === focused?.key)).toHaveLength(1);
    }
  });

  it("says one line at a time without inventing reinforcement", () => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const { focused } = frameAt(take, at);
      const line = narrationFor(focused, { phase: "idle" });
      expect(line).toMatch(/^[A-Z0-9 /·]+$/);
      expect(line).not.toContain("REINFORCEMENT");
      expect(line).not.toContain("COORDINATED");
      expect(line).not.toContain("UNDER STRENGTH");
    }
  });
});

describe("take b — the ADAPTED sequence", () => {
  const take = TAKES[1];
  const adaptedAt = (atMs: number) => {
    const objective = frameAt(take, atMs).view.objectives[0];
    return objective.trace.find((stage) => stage.name === "ADAPTED");
  };

  it("owes nothing before the failure", () => {
    expect(adaptedAt(20_000)).toMatchObject({ state: "not_required", at: null });
  });

  it("is actively resolving while the role stands vacant", () => {
    const stage = adaptedAt(21_500);
    expect(stage?.state).toBe("active");
    expect(stage?.at).toBeTruthy();
  });

  it("has no replacement frame to date it in the gap after the swap", () => {
    expect(adaptedAt(23_500)).toMatchObject({ state: "done", at: null });
  });

  it("dates the adaptation from the replacement's first frame", () => {
    const stage = adaptedAt(24_500);
    expect(stage?.state).toBe("done");
    expect(stage?.at).toBe(new Date(TAKE_B.t0 + 24_000).toISOString());
  });
});

describe("takes a and b hold one swarm each", () => {
  it.each(TAKES)("take $id", (take) => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      for (const objective of frameAt(take, at).view.objectives) {
        expect(objective.swarms.length).toBeLessThanOrEqual(1);
        expect(objective.swarms.every((swarm) => swarm.reinforcesGroupId === null)).toBe(
          true
        );
        if (objective.swarms.length === 1) {
          expect(objective.slots).toEqual(objective.swarms[0].slots);
          expect(objective.requestedMembers).toBe(objective.swarms[0].requestedMembers);
        }
      }
    }
  });
});
