import { describe, expect, it } from "vitest";

import { buildAuthorityView } from "@/lib/authority";
import {
  TAKE_A,
  TAKE_B,
  TAKE_C,
  foldTakeA,
  foldTakeB,
  foldTakeC,
  takeAFrames,
  takeBFrames,
  takeCFrames,
} from "@/lib/demo-frames";

import { narrationFor } from "../NarrationStrip";

/**
 * The recorded takes, held to what they already say.
 *
 * The swarm layer restructures the view model every take is rendered through:
 * objectives are now built from a *set* of related `ExecutionGroup`s rather than
 * one at a time, and the composition, the trace and the narration all read off
 * the result. That is exactly the kind of change that moves a timestamp or
 * rewords a line without anyone noticing until the recording is watched back.
 *
 * So this replays all three takes frame by frame and pins the properties the
 * rehearsal is judged on. It asserts against the takes' own recorded content,
 * not against a hand-copied transcript: a golden list would have to be updated
 * to match a regression, which is the failure mode it exists to prevent.
 *
 * `demo-frames.ts` is read here and never written — the take belongs to a later
 * phase.
 */

const TAKES = [
  { id: "a", script: TAKE_A, frames: takeAFrames(), fold: foldTakeA },
  { id: "b", script: TAKE_B, frames: takeBFrames(), fold: foldTakeB },
  { id: "c", script: TAKE_C, frames: takeCFrames(), fold: foldTakeC },
] as const;

const STEP_MS = 500;

/** The surface's own reading of one instant of a take. */
function frameAt(take: (typeof TAKES)[number], atMs: number) {
  const view = buildAuthorityView(take.fold(atMs, take.frames as never));
  const focused = view.objectives.find((o) => o.key === view.defaultFocusKey) ?? null;
  return { view, focused };
}

describe.each(TAKES)("take $id", (take) => {
  it("dates each objective's composition once and never re-dates it", () => {
    // `decisionAt` is `composedAt` — the earliest member timestamp, not the
    // newest frame. A COMPOSED stage that walked forward would re-order the
    // objectives and hand focus to whichever one published last.
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
    // A reinforcement joins the objective it serves. Nothing in these takes is
    // a reinforcement, so the objective count is the group count plus the
    // single-executor awards, and it only ever grows.
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
      expect(view.objectives.filter((o) => o.key === focused?.key)).toHaveLength(1);
    }
  });

  it("says one line at a time, from the state the panels are showing", () => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const { focused } = frameAt(take, at);
      const line = narrationFor(focused, { phase: "idle" });
      expect(line).toMatch(/^[A-Z0-9 /·]+$/);
      // Neither new line may fire on a take that has no reinforcement and no
      // partial-strength composition in it.
      expect(line).not.toContain("REINFORCEMENT");
      expect(line).not.toContain("COMBINED");
      expect(line).not.toContain("UNDER STRENGTH");
    }
  });
});

/**
 * The adaptation sequence, which is the beat the whole rehearsal is built on.
 *
 * ADAPTED is the one conditional stage in the ladder, and its reading changes
 * four times inside three seconds. Each of these is a different fact and they
 * are easy to collapse into one another.
 */
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
    // SwarmOS has put the replacement in, so the failed member's own frames are
    // no longer any role's. The replacement has not reported yet. Dating the
    // stage from the failure here would claim the new executor was flying
    // before it was.
    expect(adaptedAt(23_500)).toMatchObject({ state: "done", at: null });
  });

  it("dates the adaptation from the replacement's first frame", () => {
    const stage = adaptedAt(24_500);
    expect(stage?.state).toBe("done");
    expect(stage?.at).toBe(new Date(TAKE_B.t0 + 24_000).toISOString());
  });
});

/** One swarm per objective in every recorded take — none of them reinforces. */
describe("the recorded takes hold one swarm each", () => {
  it.each(TAKES)("take $id", (take) => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      for (const objective of frameAt(take, at).view.objectives) {
        expect(objective.swarms.length).toBeLessThanOrEqual(1);
        expect(objective.swarms.every((swarm) => swarm.reinforcesGroupId === null)).toBe(
          true
        );
        // The flattened roles are exactly the swarm's roles, so every consumer
        // reading `slots` sees what it saw before the swarm layer existed.
        if (objective.swarms.length === 1) {
          expect(objective.slots).toEqual(objective.swarms[0].slots);
          expect(objective.requestedMembers).toBe(objective.swarms[0].requestedMembers);
        }
      }
    }
  });
});
