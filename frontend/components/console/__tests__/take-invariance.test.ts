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
 * objectives are built from a set of related `ExecutionGroup`s, while the
 * public narration deliberately speaks in product nouns: swarms and subunits.
 * That is exactly the kind of change that moves a timestamp or rewords a line
 * without anyone noticing until the recording is watched back.
 *
 * So this replays all three takes frame by frame and pins the properties the
 * rehearsal is judged on. It asserts against the takes' own recorded content,
 * not against a hand-copied transcript: a golden list would have to be updated
 * to match a regression, which is the failure mode it exists to prevent.
 *
 * `demo-frames.ts` is read here and never written.
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
  const focused = view.objectives.find((objective) => objective.key === view.defaultFocusKey) ?? null;
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
      expect(view.objectives.filter((objective) => objective.key === focused?.key)).toHaveLength(1);
    }
  });

  it("says one line at a time without inventing reinforcement", () => {
    for (let at = 0; at <= take.script.durationMs; at += STEP_MS) {
      const { focused } = frameAt(take, at);
      const line = narrationFor(focused, { phase: "idle" });
      expect(line).toMatch(/^[A-Z0-9 /·]+$/);
      if (take.id === "c") continue;
      // Neither new line may fire on a take that has no reinforcement and no
      // partial-strength composition in it. Take C does have both — see the
      // dedicated "take c — reinforcement" block below.
      expect(line).not.toContain("REINFORCEMENT");
      expect(line).not.toContain("COORDINATED");
      expect(line).not.toContain("UNDER STRENGTH");
      expect(line).not.toContain("REASSIGNED");
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

/** One swarm per objective in takes A and B — neither of them reinforces. */
describe("takes a and b hold one swarm each", () => {
  it.each(TAKES.slice(0, 2))("take $id", (take) => {
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

/**
 * Take A's hero beat: a second objective lands while the first is still
 * executing, and the nearest executor is already committed to it. This is the
 * moment the recording proves two objectives are concurrent rather than
 * queued, so it gets its own pinned line instead of riding on the generic
 * "says one line at a time" check above.
 */
describe("take a — concurrent objective", () => {
  const take = TAKES[0];
  const lineAt = (atMs: number) => narrationFor(frameAt(take, atMs).focused, { phase: "idle" });

  it("says nothing about a busy exclusion before the second objective exists", () => {
    // T+24 is the HEAT_SPOT detection frame; the allocation that excludes
    // mav-002 BUSY does not land until T+25, so objective two does not exist
    // yet and focus is still objective one's own steady-state line.
    expect(lineAt(24_500)).not.toContain("BUSY");
  });

  it("says the busy exclusion the instant the second objective is awarded", () => {
    // T+25 is the allocation frame itself: mav-002 excluded BUSY on mission
    // one, mav-001 wins. Focus follows the newest active objective, so this
    // is already objective two's own line.
    expect(lineAt(25_500)).toBe("PRIOR SUBUNIT BUSY · SWARMOS SELECTED ANOTHER");
  });

  it("keeps the busy line while both objectives are still running", () => {
    // Sampled just before T+42, mission one's RTL-acknowledged close, with
    // both missions still active and objective two still newest.
    expect(lineAt(41_500)).toBe("PRIOR SUBUNIT BUSY · SWARMOS SELECTED ANOTHER");
  });

  it("moves on once the second objective verifies", () => {
    expect(lineAt(60_000)).toBe("OBJECTIVE VERIFIED · MISSION COMPLETE");
  });
});

/**
 * Take C's hero objective is the one recorded take that reinforces: swarm 01
 * composes under strength, swarm 02 joins to answer it, and the T+21/T+23
 * failover happens inside swarm 02 while swarm 01 is untouched by it.
 */
describe("take c — reinforcement", () => {
  const take = TAKES[2];
  const heroAt = (atMs: number) => {
    const { view } = frameAt(take, atMs);
    // The hero objective is the one carrying the reinforcement metadata's
    // group id — never the sweep, which has no `reinforces_group_id` at all.
    return view.objectives.find((o) => o.groupId === TAKE_C.reinforcement.swarmA) ?? null;
  };

  it("composes swarm 01 alone and under strength before swarm 02 exists", () => {
    // Sampled right after ACTIVE (T+19) and before the first wave of sweep
    // subunits joins at T+19.5: just the two pad-launched roles.
    const objective = heroAt(19_000);
    expect(objective?.swarms.length).toBe(1);
    expect(objective?.swarms[0].reinforcesGroupId).toBeNull();
    expect(objective?.swarms[0].composedMembers).toBe(2);
    expect(objective?.swarms[0].requestedMembers).toBe(6);
    expect(objective?.swarms[0].underStrength).toBe(true);
  });

  it("dispatches swarm 02 as a reinforcement of swarm 01, never a third role on it", () => {
    const objective = heroAt(33_000);
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

  it("says UNDER STRENGTH, then REINFORCEMENT, then COORDINATED, in that order", () => {
    const lineAt = (atMs: number) => narrationFor(heroAt(atMs), { phase: "idle" });
    // Wave one has settled onto its containment stations (arrival ~T+29.2-29.5)
    // and swarm 02 does not exist yet (dispatch is T+32): swarm 01 is short one
    // role and nothing else is currently changing.
    expect(lineAt(30_800)).toContain("UNDER STRENGTH");
    // Swarm 02 is FORMING (T+32-33): the reinforcement is dispatched, not yet active.
    expect(lineAt(32_500)).toContain("REINFORCEMENT");
    // Both swarms are active and wave two has arrived (~T+43.9-45.1) and settled,
    // well clear of the T+38.5 failure and its T+40.5 replacement — reinforcement
    // is on station, so the objective reads coordinated rather than just inbound.
    expect(lineAt(50_000)).toContain("COORDINATED");
  });

  it("says a sweep subunit is being diverted while the first wave is inbound", () => {
    // T+19.5-19.9: three subunits leave the sweep pattern for swarm 01, before
    // any of them has reported ON_STATION on its new role.
    const line = narrationFor(heroAt(19_600), { phase: "idle" });
    expect(line).toContain("REASSIGNED");
  });

  it("keeps focus on the hero objective through the whole recorded failover", () => {
    for (let at = 19_000; at <= (TAKE_C.reinforcement.replacedAtS + 5) * 1000; at += STEP_MS) {
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

/**
 * The sweep itself: a moving formation, shrinking as SwarmOS diverts subunits
 * off it, never double-booked with the objective it feeds.
 */
describe("take c — sweep and diversion", () => {
  const frames = takeCFrames();
  const sweepStrengthAt = (atMs: number) => {
    const slice = foldTakeC(atMs, frames);
    const group = slice.executionGroups.find((g) => g.objective_kind === "AREA_SWEEP");
    return group?.members.length ?? null;
  };

  it("keeps a never-diverted subunit's track moving, not held on one point", () => {
    // mav-005 is SWEEP index 0 — never one of the five diverted agents — and
    // both instants fall after its own arrival and before recall (T+48).
    const at = (ms: number) => foldTakeC(ms, frames).units.find((u) => u.agent_id === "mav-005");
    const early = at(15_000);
    const later = at(30_000);
    expect(early && later).toBeTruthy();
    expect(early!.geo).not.toEqual(later!.geo);
  });

  it("steps the sweep's own roster down as SwarmOS diverts subunits off it", () => {
    // Full 30 before the first wave, 27 once it joins swarm 01, 25 once the
    // second wave joins swarm 02 — `requested_members` stays 30 throughout, so
    // this is capacity SwarmOS committed elsewhere, not capacity it never had.
    expect(sweepStrengthAt(19_000)).toBe(30);
    expect(sweepStrengthAt(20_000)).toBe(27);
    expect(sweepStrengthAt(33_500)).toBe(25);
  });

  it('publishes every diversion with the real mode:"diversion" shape', () => {
    const slice = foldTakeC(TAKE_C.durationMs, frames);
    const diversions = slice.allocations.filter((d) => d.mode === "diversion");
    expect(diversions).toHaveLength(5);
    for (const d of diversions) {
      // A diverted unit never bid — 0 would render as a real auction result.
      expect(d.winner_score).toBeNull();
      expect(d.diverted_from_mission_id).toBeTruthy();
      // The winner is the executor, never also an exclusion on its own award —
      // the same invariant `test_diversion_truth.py` holds on the backend.
      expect(d.excluded_units.some((u) => u.agent_id === d.winner_agent_id)).toBe(false);
    }
  });

  it("never holds one agent on both the sweep and the hero objective at once", () => {
    for (let at = 0; at <= TAKE_C.durationMs; at += 1_000) {
      const slice = foldTakeC(at, frames);
      const sweepIds = new Set(
        (slice.executionGroups.find((g) => g.objective_kind === "AREA_SWEEP")?.members ?? []).map(
          (m) => m.agent_id
        )
      );
      const heroIds = new Set(
        slice.executionGroups
          .filter((g) => g.objective_kind === "COOPERATIVE_VERIFY")
          .flatMap((g) => g.members.map((m) => m.agent_id))
      );
      for (const id of sweepIds) expect(heroIds.has(id)).toBe(false);
    }
  });
});
