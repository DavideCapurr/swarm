/**
 * Phase 7.F — QuietPanel surfaces the AUTO eyebrow in the Recent action
 * row when the latest command is autonomy-issued.
 *
 * Mirrors the CommandTimeline AUTO chip pattern (Phase 7.C). The eyebrow
 * is the operator's "SwarmOS decided this, not me" signal in the
 * viewport's right rail and is required by the YC demo gate.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { QuietPanel } from "@/components/QuietPanel";
import { makeCommand, makeSwarmState } from "./_swarmState";

vi.mock("@/lib/state", () => ({
  useSwarm: vi.fn(),
}));

vi.mock("@/lib/auth", async () => {
  const actual = await vi.importActual<typeof import("@/lib/auth")>("@/lib/auth");
  return {
    ...actual,
    useRole: () => "operator",
  };
});

import { useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);

describe("QuietPanel · RecentSection", () => {
  it("renders the auto · r1 eyebrow when the latest command is autonomy", () => {
    const autonomy = makeCommand({
      id: "cmd-auto",
      source: "autonomy",
      rule: "R1",
      action: "verify",
      status: "in_flight",
      submitted_at: "2026-05-26T18:30:00.000Z",
    });
    useSwarmMock.mockReturnValue(makeSwarmState({ commands: [autonomy] }));

    render(<QuietPanel onSelectAgent={() => {}} />);

    const chip = screen.getByTestId("recent-auto-chip");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent(/auto · r1 ·/);
    expect(chip.className).toMatch(/text-orbital-blue/);
  });

  it("omits the auto eyebrow when the latest command is operator-sourced", () => {
    const operator = makeCommand({
      id: "cmd-op",
      source: "operator",
      action: "verify",
      status: "accepted",
      submitted_at: "2026-05-26T18:30:00.000Z",
    });
    useSwarmMock.mockReturnValue(makeSwarmState({ commands: [operator] }));

    render(<QuietPanel onSelectAgent={() => {}} />);

    expect(screen.queryByTestId("recent-auto-chip")).not.toBeInTheDocument();
  });
});
