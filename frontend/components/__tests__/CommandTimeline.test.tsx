/**
 * Phase 7.C — CommandTimeline renders the AUTO chip on autonomy rows.
 *
 * The chip is the Console's "this came from SwarmOS, not from me"
 * signal. We verify (1) it shows up with `AUTO · {rule}` when the
 * source is "autonomy" + `rule` is set, (2) it stays absent when the
 * row is operator-issued.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { CommandTimeline } from "@/components/CommandTimeline";
import { makeCommand, makeSwarmState } from "./_swarmState";

vi.mock("@/lib/state", () => ({
  useSwarm: vi.fn(),
}));

import { useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);

describe("CommandTimeline", () => {
  it("renders AUTO · R2 for an autonomy command with rule R2", () => {
    const autonomy = makeCommand({
      id: "cmd-auto",
      source: "autonomy",
      rule: "R2",
      action: "escalate",
      status: "in_flight",
    });
    useSwarmMock.mockReturnValue(makeSwarmState({ commands: [autonomy] }));

    render(<CommandTimeline />);

    const chip = screen.getByTestId("command-auto-chip-cmd-auto");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("AUTO · R2");
    expect(chip.className).toMatch(/text-orbital-blue/);
  });

  it("omits the AUTO chip for operator-source commands", () => {
    const operator = makeCommand({
      id: "cmd-op",
      source: "operator",
      action: "verify",
      status: "accepted",
    });
    useSwarmMock.mockReturnValue(makeSwarmState({ commands: [operator] }));

    render(<CommandTimeline />);

    expect(
      screen.queryByTestId("command-auto-chip-cmd-op")
    ).not.toBeInTheDocument();
    // Operator action label still renders.
    expect(screen.getByText("Verify")).toBeInTheDocument();
  });
});
