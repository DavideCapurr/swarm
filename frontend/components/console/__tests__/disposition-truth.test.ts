import { describe, expect, it } from "vitest";

import type { DispositionDecision } from "@/lib/api";
import { buildAuthorityView } from "@/lib/authority";
import { TAKE_C, foldTakeC, takeCFrames } from "@/lib/demo-frames";

import { narrationFor } from "../NarrationStrip";

function heroAt(atMs: number) {
  const view = buildAuthorityView(foldTakeC(atMs, takeCFrames()));
  return view.objectives.find((objective) => objective.groupId === TAKE_C.reinforcement.swarmA) ?? null;
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
    ts: new Date(TAKE_C.t0 + 20_000).toISOString(),
  };
}

describe("disposition truth boundary", () => {
  it("uses the server-issued revision and radius instead of inferring a formation change", () => {
    const objective = heroAt(20_000);
    expect(objective).not.toBeNull();

    const line = narrationFor(
      objective,
      { phase: "idle" },
      reinforcementDisposition(objective!.missionId)
    );

    expect(line).toBe("SWARM 02 EN ROUTE · DISPOSITION R02 ISSUED · R 30 M");
    expect(line).not.toContain("FORMATION RECONFIGURING");
  });

  it("keeps the historical wording only when an old replay has no disposition frame", () => {
    expect(narrationFor(heroAt(20_000), { phase: "idle" })).toContain(
      "FORMATION RECONFIGURING"
    );
  });
});
