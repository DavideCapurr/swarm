import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TAKE_A, foldTakeA, takeAFrames } from "@/lib/demo-frames";
import { shortId } from "@/lib/mission-story";

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
    ...slice,
  };
  return render(<OperationalConsole frame={frame} />);
}

describe("mission-level narrative", () => {
  it("separates central ownership from physical execution", () => {
    renderAt(2.5);

    const objective = screen.getByTestId(`objective-${TAKE_A.missionOne}`);
    expect(objective).toHaveTextContent("ALLOCATED");
    expect(objective).toHaveTextContent("OWNED");
    expect(objective).not.toHaveTextContent("EXECUTING");

    const loop = screen.getByTestId("control-loop-strip");
    expect(loop).toHaveTextContent("OBJ 01 · INTRUSION");
    expect(loop).toHaveTextContent("SELECT mav-002");
    expect(loop).toHaveTextContent(`${shortId(TAKE_A.missionOne)} → mav-002`);
    expect(loop).toHaveTextContent("NO RUNTIME FRAME");
    expect(loop).toHaveTextContent("PENDING");
    expect(loop).toHaveTextContent("SWARMOS DECIDES · PHYSICAL AGENTS EXECUTE");
  });

  it("makes the BUSY adaptation legible in one causal line", () => {
    renderAt(26);

    const loop = screen.getByTestId("control-loop-strip");
    expect(loop).toHaveTextContent("OBJ 02 · HEAT_SPOT");
    expect(loop).toHaveTextContent("mav-002 EXCLUDED · BUSY");
    expect(loop).toHaveTextContent("SELECT mav-001");
    expect(loop).toHaveTextContent(`${shortId(TAKE_A.missionTwo)} → mav-001`);
    expect(loop).toHaveTextContent("EN ROUTE");

    expect(screen.getByTestId(`objective-${TAKE_A.missionOne}`)).toHaveTextContent("EXECUTING");
    expect(screen.getByTestId(`objective-${TAKE_A.missionTwo}`)).toHaveTextContent("EXECUTING");
  });

  it("returns verified PX4 evidence into the same decision loop", () => {
    renderAt(20);

    const loop = screen.getByTestId("control-loop-strip");
    expect(loop).toHaveTextContent("ON STATION");
    expect(loop).toHaveTextContent("MISSION_ITEM_REACHED");
  });
});
