import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { foldTakeA, takeAFrames } from "@/lib/demo-frames";

import { OperationalConsole, type ConsoleFrame } from "./OperationalConsole";

const FRAMES = takeAFrames();

function renderAt(atS: number) {
  const slice = foldTakeA(atS * 1000, FRAMES);
  const frame: ConsoleFrame = {
    link: "connected",
    sessionLabel: "take a",
    operatorId: "op-demo",
    role: "viewer",
    clockText: "12:00:00 UTC",
    executionGroups: [],
    replay: true,
    ...slice,
  };
  return render(<OperationalConsole frame={frame} />);
}

describe("reported input → objective causality", () => {
  it("makes the first perimeter input and verification objective explicit", () => {
    renderAt(2.5);

    expect(screen.getByTestId("control-loop-strip")).toHaveTextContent(
      "perimeter-cam-04 → OBJ 01 · INTRUSION · VERIFY"
    );

    const objective = screen.getByTestId(
      "objective-4c97f2f2127b454eae5cf76be2d20a5e"
    );
    expect(objective).toHaveTextContent("VERIFY INTRUSION");
    expect(objective).toHaveTextContent("reported input perimeter-cam-04");

    expect(screen.getByText("REPORTED SOURCE · perimeter-cam-04")).toBeInTheDocument();
    expect(screen.getByText("VERIFY INTRUSION · 95%")).toBeInTheDocument();
    expect(screen.getByText("REPORTED INPUT → OBJ 01")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED IMAGERY · NOT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("NOT A LIVE FEED")).toBeInTheDocument();
  });

  it("switches the control loop to the second sensor without relabelling the simulated intrusion clip", () => {
    renderAt(25.5);

    expect(screen.getByTestId("control-loop-strip")).toHaveTextContent(
      "thermal-array-02 → OBJ 02 · HEAT_SPOT · VERIFY"
    );

    const second = screen.getByTestId(
      "objective-e768f1423a654f2bbb208330b62e578a"
    );
    expect(second).toHaveTextContent("VERIFY HEAT_SPOT");
    expect(second).toHaveTextContent("reported input thermal-array-02");

    expect(screen.getByText("REPORTED SOURCE · perimeter-cam-04")).toBeInTheDocument();
    expect(screen.queryByText("REPORTED SOURCE · thermal-array-02")).not.toBeInTheDocument();
  });
});
