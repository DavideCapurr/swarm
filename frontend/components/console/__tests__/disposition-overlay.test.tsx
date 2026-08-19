import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DispositionDecision } from "@/lib/api";

import { DispositionOverlay } from "../DispositionOverlay";
import { buildConsoleProjection } from "../projection";

const CENTER = { lat: 47.398, lon: 8.546, alt_m: 0 };
const projection = buildConsoleProjection(
  { origin: CENTER, center: { e: 0, n: 0 }, extentM: 120 },
  { width: 1600, height: 900 },
  { left: 380, right: 380, top: 120, bottom: 132 }
);

const decision: DispositionDecision = {
  objective_mission_id: "objective-1",
  revision: 2,
  reason: "REINFORCEMENT",
  center: CENTER,
  active_members: 3,
  radius_m: 30,
  assignments: [
    {
      group_id: "group-a",
      agent_id: "mav-004",
      role: "PRIMARY_OBSERVER",
      mission_id: "child-a2",
      geo: { lat: 47.39827, lon: 8.546, alt_m: 40 },
    },
    {
      group_id: "group-a",
      agent_id: "mav-002",
      role: "OVERWATCH",
      mission_id: "child-b2",
      geo: { lat: 47.397865, lon: 8.546345, alt_m: 70 },
    },
    {
      group_id: "group-b",
      agent_id: "mav-001",
      role: "SECONDARY_OBSERVER",
      mission_id: "child-c2",
      geo: { lat: 47.397865, lon: 8.545655, alt_m: 55 },
    },
  ],
  ts: "2026-08-19T13:00:00.000Z",
};

describe("DispositionOverlay", () => {
  it("renders the exact SwarmOS revision, radius and assignments", () => {
    if (!projection) throw new Error("projection did not build");
    render(<DispositionOverlay projection={projection} decision={decision} />);

    const overlay = screen.getByTestId("disposition-overlay");
    expect(overlay).toHaveAttribute("data-disposition-revision", "2");
    expect(overlay).toHaveAttribute("data-disposition-radius-m", "30");
    expect(screen.getByTestId("disposition-label")).toHaveTextContent(
      "SWARMOS DISP R2 · REINFORCEMENT · R 30 M"
    );

    for (const assignment of decision.assignments) {
      const slot = screen.getByTestId(`disposition-slot-${assignment.agent_id}`);
      expect(slot).toHaveAttribute("data-role", assignment.role);
      expect(slot).toHaveAttribute("data-mission-id", assignment.mission_id);
    }
  });

  it("renders no formation claim when SwarmOS published no disposition", () => {
    if (!projection) throw new Error("projection did not build");
    render(<DispositionOverlay projection={projection} decision={null} />);

    expect(screen.queryByTestId("disposition-overlay")).toBeNull();
    expect(screen.queryByTestId("disposition-label")).toBeNull();
  });
});
