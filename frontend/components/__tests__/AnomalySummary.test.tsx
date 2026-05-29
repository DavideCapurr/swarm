/**
 * Phase 7.C — AnomalySummary renders the AUTO chip when autonomy in flight.
 *
 * The chip says `AUTO · verify` (or `· escalate`/`· dismiss`) whenever the
 * latest autonomy command targets the focus anomaly — and (Phase 7 WS1d) it
 * *persists* after that command terminates, because the attribution
 * ("SwarmOS decided this") is exactly what matters once the decision lands.
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

  it("keeps the AUTO chip after the autonomy command terminates (attribution persists)", () => {
    const anomaly = makeAnomaly({ id: "a-1", state: "escalated", band: "verified" });
    const completed = makeCommand({
      id: "cmd-auto-done",
      source: "autonomy",
      action: "escalate",
      target: "anomaly:a-1",
      status: "completed",
      rule: "R2",
    });
    useFocusMock.mockReturnValue(anomaly);
    useSwarmMock.mockReturnValue(
      makeSwarmState({ anomalies: [anomaly], commands: [completed] })
    );

    render(<AnomalySummary />);

    const chip = screen.getByTestId("anomaly-auto-chip");
    expect(chip).toHaveTextContent("AUTO · escalate");
    expect(chip.className).toMatch(/text-orbital-blue/);
  });
});
