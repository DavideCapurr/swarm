import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { OperationalConsole, type ConsoleFrame } from "./OperationalConsole";

function frame(sessionLabel: string): ConsoleFrame {
  return {
    link: "connected",
    sessionLabel,
    operatorId: "op-demo",
    role: "viewer",
    clockText: "12:00:00 UTC",
    units: [],
    anomalies: [],
    allocations: [],
    missionRuntime: [],
    missionRuntimeLog: [],
    payloadEvents: [],
    missions: [],
    now: Date.UTC(2026, 7, 15, 12, 0, 0),
    executionGroups: [
      {
        id: "4efceb04bdda4f3e88f9da18dbb158c6",
        objective_mission_id: "8582edb3f2984289ab756602ac03aad5",
        objective_kind: "COOPERATIVE_VERIFY",
        anomaly_id: "d3e97452bda44cbc99cd5e16d67aed2f",
        requested_members: 3,
        state: "DEGRADED",
        failure_reason: null,
        ts: "2026-08-15T17:29:14.245648Z",
        members: [],
      },
    ],
  };
}

describe("recording bench truth boundary", () => {
  it("marks TAKE B as a separate PX4 SITL bench", () => {
    render(<OperationalConsole frame={frame("take b")} />);

    const boundary = screen.getByTestId("take-b-bench-boundary");
    expect(boundary).toHaveTextContent("TAKE B · SEPARATE PX4 SITL BENCH");
    expect(boundary).toHaveTextContent("NOT CONTINUOUS WITH TAKE A · SITL ONLY");
  });

  it("does not stamp TAKE A as a separate bench", () => {
    render(<OperationalConsole frame={frame("take a")} />);
    expect(screen.queryByTestId("take-b-bench-boundary")).not.toBeInTheDocument();
  });
});
