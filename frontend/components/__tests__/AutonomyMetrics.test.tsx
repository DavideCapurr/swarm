/**
 * WS2 (Phase 7) — AutonomyMetrics renders the honest in-Console autonomy
 * readout: real computed p50/p95 latencies, every label `(sim)`, an honest
 * empty state ("— awaiting autonomy", never "0 ms"), self-gated on
 * autonomyEnabled, and no red anywhere (design system §5.2).
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { AutonomyMetrics } from "@/components/AutonomyMetrics";
import { makeAnomaly, makeCommand, makeEvent, makeSwarmState } from "./_swarmState";

vi.mock("@/lib/state", async () => {
  const actual = await vi.importActual<typeof import("@/lib/state")>("@/lib/state");
  return { ...actual, useSwarm: vi.fn() };
});

import { useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);

// A demo-shaped autonomy fixture: SMOKE born at t0, R1 VERIFY decided +2000 ms
// later, mission dispatched +150 ms after that.
function autonomyFixture() {
  const t0 = "2026-05-26T18:00:00.000Z";
  const submitted = "2026-05-26T18:00:02.000Z"; // +2000 ms
  const inFlight = "2026-05-26T18:00:02.150Z"; // +150 ms
  const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
  const event = makeEvent({ id: "e1", kind: "anomaly", anomaly_id: "a-1", ts: t0 });
  const cmd = makeCommand({
    id: "c1",
    source: "autonomy",
    rule: "R1",
    action: "verify",
    target: "anomaly:a-1",
    submitted_at: submitted,
    in_flight_at: inFlight,
    status: "completed",
  });
  return makeSwarmState({
    autonomyEnabled: true,
    commands: [cmd],
    anomalies: [anomaly],
    events: [event],
  });
}

describe("AutonomyMetrics", () => {
  it("returns null when autonomy is disabled (zero diff for non-autonomy sites)", () => {
    useSwarmMock.mockReturnValue(makeSwarmState({ autonomyEnabled: false }));
    const { container } = render(<AutonomyMetrics />);
    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByTestId("autonomy-metrics")).not.toBeInTheDocument();
  });

  it("renders the computed p50/p95 latencies from real audit frames", () => {
    useSwarmMock.mockReturnValue(autonomyFixture());
    render(<AutonomyMetrics />);
    expect(screen.getByTestId("autonomy-metrics")).toBeInTheDocument();
    // anomaly→decision = 2000 ms, decision→dispatch = 150 ms (1-decimal display).
    expect(screen.getByText("2000.0/2000.0 ms")).toBeInTheDocument();
    expect(screen.getByText("150.0/150.0 ms")).toBeInTheDocument();
  });

  it("labels every readout (sim)", () => {
    useSwarmMock.mockReturnValue(autonomyFixture());
    render(<AutonomyMetrics />);
    expect(screen.getByText(/Autonomy \(sim\)/)).toBeInTheDocument();
    expect(screen.getByText(/anomaly → decision \(sim\)/)).toBeInTheDocument();
    expect(screen.getByText(/decision → dispatch \(sim\)/)).toBeInTheDocument();
  });

  it("shows an honest empty state and never prints 0 ms", () => {
    useSwarmMock.mockReturnValue(makeSwarmState({ autonomyEnabled: true }));
    render(<AutonomyMetrics />);
    expect(screen.getByTestId("autonomy-metrics")).toBeInTheDocument();
    // Both latency rows show the awaiting state when n=0.
    expect(screen.getAllByText("— awaiting autonomy")).toHaveLength(2);
    // No fabricated measurement.
    expect(screen.queryByText(/ ms$/)).not.toBeInTheDocument();
  });

  it("contains no red token in any rendered class (design system §5.2)", () => {
    useSwarmMock.mockReturnValue(autonomyFixture());
    const { container } = render(<AutonomyMetrics />);
    for (const el of container.querySelectorAll("*")) {
      expect(el.getAttribute("class") ?? "").not.toMatch(/red/);
    }
  });
});
