/**
 * Phase 7.C — AnomalySummary renders the AUTO chip when autonomy in flight.
 *
 * The chip says `AUTO · verify` (or `· escalate`/`· dismiss`) while a
 * non-terminal autonomy command targets the focus anomaly. As soon as
 * the command terminates (completed/rejected/timed_out) the chip
 * disappears.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AnomalySummary } from "@/components/AnomalySummary";
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

describe("AnomalySummary", () => {
  it("renders AUTO · verify when an autonomy VERIFY command is in flight", () => {
    const anomaly = makeAnomaly({ id: "a-1" });
    const inFlight = makeCommand({
      id: "cmd-auto",
      source: "autonomy",
      action: "verify",
      target: "anomaly:a-1",
      status: "in_flight",
      rule: "R1",
    });
    useFocusMock.mockReturnValue(anomaly);
    useSwarmMock.mockReturnValue(
      makeSwarmState({ anomalies: [anomaly], commands: [inFlight] })
    );

    render(<AnomalySummary />);

    const chip = screen.getByTestId("anomaly-auto-chip");
    expect(chip).toHaveTextContent("AUTO · verify");
    expect(chip.className).toMatch(/text-orbital-blue/);
  });

  it("hides the AUTO chip when the autonomy command has completed", () => {
    const anomaly = makeAnomaly({ id: "a-1" });
    const completed = makeCommand({
      id: "cmd-auto-done",
      source: "autonomy",
      action: "verify",
      target: "anomaly:a-1",
      status: "completed",
      rule: "R1",
    });
    useFocusMock.mockReturnValue(anomaly);
    useSwarmMock.mockReturnValue(
      makeSwarmState({ anomalies: [anomaly], commands: [completed] })
    );

    render(<AnomalySummary />);

    expect(screen.queryByTestId("anomaly-auto-chip")).not.toBeInTheDocument();
  });
});
