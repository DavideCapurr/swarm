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
 * objectives are built from a set of related ExecutionGroups, while the public
 * narration deliberately speaks in product nouns: swarms and subunits.
 */

const TAKES = [
  { id: "a", script: TAKE_A, frames: takeAFrames(), fold: foldTakeA },
  { id: "b", script: TAKE_B, frames: takeBFrames(), fold: foldTakeB },
  { id: "c", script: TAKE_C, frames: takeCFrames(), fold: foldTakeC },
] as const;

const STEP_MS = 500;

function frameAt(take: (typeof TAKES)[number], atMs: number) {
  const view = buildAuthorityView(take.fold(atMs, take.frames as never));
  const focused = view.objectives.find((o) => o.key === view.defaultFocusKey) ?? null;
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
      expect(view.objectives.filter((o) => o.key === focused?.key)).toHaveLength(1);
    }
  });

  it("says one line at a time, from the state the panels are showing", () => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const { focused } = frameAt(take, at);
      const line = narrationFor(focused, { phase: "idle" });
      expect(line).toMatch(/^[A-Z0-9 /·]+$/);
      if (take.id === "c") continue;
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
  it.each(TAKES.slice(0, 2))("take $id", (take) => {
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

describe("take c — reinforcement", () => {
  const take = TAKES[2];
  const heroAt = (atMs: number) => {
    const { view } = frameAt(take, atMs);
    return view.objectives.find((o) => o.groupId === TAKE_C.reinforcement.swarmA) ?? null;
  };

  it("composes swarm 01 alone and under strength before swarm 02 exists", () => {
    const objective = heroAt(3_000);
    expect(objective?.swarms.length).toBe(1);
    expect(objective?.swarms[0].reinforcesGroupId).toBeNull();
    expect(objective?.swarms[0].composedMembers).toBe(2);
    expect(objective?.swarms[0].requestedMembers).toBe(3);
    expect(objective?.swarms[0].underStrength).toBe(true);
  });

  it("dispatches swarm 02 as a reinforcement of swarm 01", () => {
    const objective = heroAt(20_000);
    expect(objective?.swarms.length).toBe(2);
    expect(objective?.swarms[0].groupId).toBe(TAKE_C.reinforcement.swarmA);
    expect(objective?.swarms[1].groupId).toBe(TAKE_C.reinforcement.swarmB);
    expect(objective?.swarms[1].reinforcesGroupId).toBe(TAKE_C.reinforcement.swarmA);
  });

  it("never loses a swarm once dispatched", () => {
    let held = 0;
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const count = heroAt(at)?.swarms.length ?? 0;
      expect(count).toBeGreaterThanOrEqual(held);
      held = count;
    }
    expect(held).toBe(2);
  });

  it("fails mav-003 inside swarm 02 only — swarm 01's roles are untouched", () => {
    const objective = heroAt((TAKE_C.reinforcement.failAtS + 0.5) * 1000);
    expect(objective?.swarms[0].slots.some((s) => s.adapting)).toBe(false);
    expect(objective?.swarms[1].slots.some((s) => s.adapting)).toBe(true);
  });

  it("replaces mav-003 with mav-001 inside swarm 02, provenance intact", () => {
    const objective = heroAt((TAKE_C.reinforcement.replacedAtS + 1) * 1000);
    const secondary = objective?.swarms[1].slots.find((s) => s.role === "SECONDARY_OBSERVER");
    expect(secondary?.agentId).toBe("mav-001");
    expect(secondary?.replacesAgentId).toBe("mav-003");
    expect(secondary?.replacedAgentId).toBe("mav-003");
  });

  it("narrates shortfall, dispatch, widening, then coordination in order", () => {
    const lineAt = (atMs: number) => narrationFor(heroAt(atMs), { phase: "idle" });
    expect(lineAt(10_000)).toContain("UNDER STRENGTH");
    expect(lineAt(15_200)).toContain("REINFORCEMENT");
    expect(lineAt(20_000)).toContain("FORMATION RECONFIGURING");
    expect(lineAt(30_000)).toContain("COORDINATED");
  });

  it("keeps focus on the hero objective through the whole recorded failover", () => {
    for (let at = 18_000; at <= (TAKE_C.reinforcement.replacedAtS + 5) * 1000; at += STEP_MS) {
      const { view } = frameAt(take, at);
      expect(view.defaultFocusKey).toBe(TAKE_C.reinforcement.swarmA);
    }
  });

  it("verifies once both swarms complete, and settles there", () => {
    const objective = heroAt(take.script.durationMs);
    expect(objective?.state).toBe("VERIFIED");
    expect(objective?.swarms.every((s) => s.state === "VERIFIED")).toBe(true);
  });
});
