/**
 * Phase 8.A — AutonomyDecision is the Console default inversion.
 *
 * The block leads with *what SwarmOS decided* (verdict + rule) and demotes
 * the operator intents to override controls. These tests pin the four
 * stances (decided / holding / clear / manual), the Orbital-Blue rule
 * accent, and the always-present override row.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AutonomyDecision } from "@/components/AutonomyDecision";
import { makeAnomaly, makeCommand, makeSwarmState } from "./_swarmState";

vi.mock("@/lib/state", async () => {
  const actual = await vi.importActual<typeof import("@/lib/state")>(
    "@/lib/state"
  );
  return {
    ...actual,
    useSwarm: vi.fn(),
    useFocusAnomaly: vi.fn(),
  };
});

import { useFocusAnomaly, useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);
const useFocusMock = vi.mocked(useFocusAnomaly);

describe("AutonomyDecision", () => {
  it("renders nothing on the manual (autonomy-off) path", () => {
    useFocusMock.mockReturnValue(makeAnomaly({ id: "a-1" }));
    useSwarmMock.mockReturnValue(makeSwarmState({ autonomyEnabled: false }));

    const { container } = render(<AutonomyDecision />);

    expect(container.firstChild).toBeNull();
  });

  it("leads with the SwarmOS verdict + rule when a decision is bound", () => {
    const focus = makeAnomaly({ id: "a-1" });
    const command = makeCommand({
      id: "cmd-auto",
      source: "autonomy",
      action: "verify",
      target: "anomaly:a-1",
      status: "in_flight",
      rule: "R1",
    });
    useFocusMock.mockReturnValue(focus);
    useSwarmMock.mockReturnValue(
      makeSwarmState({
        autonomyEnabled: true,
        anomalies: [focus],
        commands: [command],
      })
    );

    render(<AutonomyDecision />);

    expect(screen.getByTestId("autonomy-verdict")).toHaveTextContent(
      "verifying sector"
    );
    const chip = screen.getByTestId("autonomy-rule-chip");
    expect(chip).toHaveTextContent("AUTO · r1");
    expect(chip.className).toMatch(/text-orbital-blue/);
    // override row always present
    expect(screen.getByText(/override/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /verify/i })).toBeEnabled();
  });

  it("reads the status sub-line off the bound command", () => {
    const focus = makeAnomaly({ id: "a-1", state: "escalated", band: "verified" });
    const command = makeCommand({
      id: "cmd-auto",
      source: "autonomy",
      action: "escalate",
      target: "anomaly:a-1",
      status: "completed",
      rule: "R2",
    });
    useFocusMock.mockReturnValue(focus);
    useSwarmMock.mockReturnValue(
      makeSwarmState({
        autonomyEnabled: true,
        anomalies: [focus],
        commands: [command],
      })
    );

    render(<AutonomyDecision />);

    expect(screen.getByTestId("autonomy-verdict")).toHaveTextContent(
      "escalated to operator"
    );
    expect(screen.getByText("decision logged")).toBeInTheDocument();
  });

  it("is `holding` (assessing) when autonomy has not acted on the focus yet", () => {
    const focus = makeAnomaly({ id: "a-1", confidence: 0.6 });
    useFocusMock.mockReturnValue(focus);
    useSwarmMock.mockReturnValue(
      makeSwarmState({ autonomyEnabled: true, anomalies: [focus], commands: [] })
    );

    render(<AutonomyDecision />);

    expect(screen.getByTestId("autonomy-verdict")).toHaveTextContent("holding");
    expect(
      screen.getByText(/assessing signal · confidence 060 %/)
    ).toBeInTheDocument();
    // no decision yet → no rule chip
    expect(screen.queryByTestId("autonomy-rule-chip")).not.toBeInTheDocument();
  });

  it("is `watching` (territory clear) with no focus anomaly; verify override disabled", () => {
    useFocusMock.mockReturnValue(null);
    useSwarmMock.mockReturnValue(
      makeSwarmState({ autonomyEnabled: true, anomalies: [], commands: [] })
    );

    render(<AutonomyDecision />);

    expect(screen.getByTestId("autonomy-verdict")).toHaveTextContent("watching");
    expect(screen.getByText("territory clear")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /verify/i })).toBeDisabled();
  });
});
