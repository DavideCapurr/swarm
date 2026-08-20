import { describe, expect, it } from "vitest";

import type { ObjectiveAuthority } from "@/lib/authority";

import { narrationFor } from "../NarrationStrip";

function terminalObjective(state: "VERIFIED" | "FAILED"): ObjectiveAuthority {
  // narrationFor must short-circuit on authoritative terminal objective state;
  // no transient presentation beat is allowed to overwrite that truth.
  return { state } as ObjectiveAuthority;
}

describe("terminal narration truth", () => {
  it("keeps VERIFIED visible even while a replacement-restored beat is alive", () => {
    expect(
      narrationFor(terminalObjective("VERIFIED"), {
        phase: "restored",
        role: "PRIMARY_OBSERVER",
        fromAgent: "sim-4",
        toAgent: "sim-6",
        active: 3,
        required: 3,
      })
    ).toBe("OBJECTIVE VERIFIED · MISSION COMPLETE");
  });

  it("keeps FAILED visible even while an adaptation beat is alive", () => {
    expect(
      narrationFor(terminalObjective("FAILED"), {
        phase: "adapting",
        role: "PRIMARY_OBSERVER",
        lostAgent: "sim-4",
      })
    ).toBe("OBJECTIVE CLOSED · NOT VERIFIED");
  });
});
