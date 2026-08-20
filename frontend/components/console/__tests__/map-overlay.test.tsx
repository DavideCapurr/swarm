import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  CapacityRow,
  CompositionSlot,
  ObjectiveAuthority,
  SwarmComposition,
} from "@/lib/authority";

import { MapOverlay, SWARM_CAPTION_W, swarmHullPath } from "../MapOverlay";
import { buildConsoleProjection, type SafeInset } from "../projection";

/**
 * The swarm as an entity on the map.
 *
 * The hull is the element that makes "the swarm is the unit" legible without a
 * caption doing the work, which makes it the element most able to say something
 * the runtime never published — a boundary around aircraft that are not one
 * commitment, or around a position where nothing is drawn. These hold it to the
 * composition SwarmOS actually published.
 */

const HOME = { lat: 47.398, lon: 8.546 };
const INSET: SafeInset = { left: 380, right: 380, top: 120, bottom: 132 };
const projection = buildConsoleProjection(
  { origin: HOME, center: { e: 0, n: 0 }, extentM: 300 },
  { width: 1600, height: 900 },
  INSET
);

function slot(over: Partial<CompositionSlot> = {}): CompositionSlot {
  return {
    index: 1,
    role: "PRIMARY_OBSERVER",
    roleIsAssigned: true,
    agentId: "mav-004",
    missionId: "child-a",
    memberState: "ACTIVE",
    phase: "ON_STATION",
    proof: null,
    score: 2.26,
    replacesAgentId: null,
    replacedAgentId: null,
    divertedAgentId: null,
    divertedFromMissionId: null,
    divertedFromObjectiveId: null,
    adapting: false,
    groupId: "group-1",
    swarmIndex: 1,
    reinforcement: false,
    divertedFromMissionId: null,
    ...over,
  };
}

function swarm(over: Partial<SwarmComposition> = {}): SwarmComposition {
  return {
    index: 1,
    groupId: "group-1",
    label: "EG-group-1",
    reinforcesGroupId: null,
    requestedMembers: 2,
    slots: [],
    composedMembers: 2,
    heldMembers: 2,
    underStrength: false,
    stateLabel: "ACTIVE",
    state: "EXECUTING",
    composedAt: "2026-08-15T17:29:00.000Z",
    ...over,
  };
}

/** Flying, so the map draws it as its own glyph rather than folding it into the pad. */
function row(agentId: string, dLat: number, over: Partial<CapacityRow> = {}): CapacityRow {
  return {
    agentId,
    commitment: "ASSIGNED",
    role: "PRIMARY_OBSERVER",
    objectiveKey: "group-1",
    objectiveLabel: "M-parent-1",
    missionId: "child-a",
    fsmState: "ON_STATION",
    phase: "ON_STATION",
    batteryPct: 90,
    linkQuality: 1,
    altitudeAglM: 40,
    headingDeg: 40,
    geo: { lat: HOME.lat + dLat, lon: HOME.lon },
    dockId: "dock-01",
    excluded: null,
    replacedOut: false,
    ...over,
  };
}

function objective(over: Partial<ObjectiveAuthority> = {}): ObjectiveAuthority {
  return {
    key: "group-1",
    index: 1,
    kind: "INTRUSION",
    label: "M-parent-1",
    missionId: "parent-1",
    anomalyId: "anom-1",
    confidence: 0.99,
    detectedAt: null,
    detection: null,
    geo: HOME,
    groupId: "group-1",
    groupStateLabel: "ACTIVE",
    swarms: [],
    requestedMembers: 2,
    slots: [],
    excludedUnits: [],
    activeMembers: 2,
    state: "EXECUTING",
    active: true,
    trace: [],
    routes: [],
    latestProof: null,
    decisionAt: "2026-08-15T17:29:00.000Z",
    ...over,
  };
}

function overlay(
  objectives: ObjectiveAuthority[],
  capacity: CapacityRow[],
  namedAgents: ReadonlySet<string> = new Set(capacity.map((r) => r.agentId))
) {
  if (!projection) throw new Error("projection did not build");
  return render(
    <MapOverlay
      projection={projection}
      objectives={objectives}
      capacity={capacity}
      focusKey={objectives[0]?.key ?? null}
      selectedExecutor={null}
      namedAgents={namedAgents}
      safeArea={{
        top: INSET.top,
        bottom: 900 - INSET.bottom,
        left: INSET.left,
        right: 1600 - INSET.right,
      }}
      onSelectObjective={() => {}}
      onSelectExecutor={() => {}}
    />
  );
}

/** Every vertex of a `M x y L x y … Z` path. */
function vertices(d: string): { x: number; y: number }[] {
  return [...d.matchAll(/[ML](-?[\d.]+) (-?[\d.]+)/g)].map((m) => ({
    x: Number(m[1]),
    y: Number(m[2]),
  }));
}

describe("swarmHullPath", () => {
  it("has nothing to draw around nothing", () => {
    expect(swarmHullPath([])).toBeNull();
  });

  it("encloses one subunit, two, and a formation", () => {
    const cases = [
      [{ x: 500, y: 400 }],
      [
        { x: 500, y: 400 },
        { x: 640, y: 430 },
      ],
      [
        { x: 500, y: 400 },
        { x: 640, y: 430 },
        { x: 560, y: 520 },
        { x: 590, y: 300 },
      ],
    ];

    for (const points of cases) {
      const d = swarmHullPath(points, 26);
      expect(d).not.toBeNull();
      const hull = vertices(d as string);
      for (const point of points) {
        for (let i = 0; i < hull.length; i += 1) {
          const a = hull[i];
          const b = hull[(i + 1) % hull.length];
          const cross =
            (b.x - a.x) * (point.y - a.y) - (b.y - a.y) * (point.x - a.x);
          expect(cross).toBeGreaterThan(0);
        }
      }
    }
  });
});

describe("the swarm on the map", () => {
  const first = swarm({
    slots: [slot(), slot({ index: 2, role: "OVERWATCH", agentId: "mav-002" })],
  });
  const second = swarm({
    index: 2,
    groupId: "group-2",
    label: "EG-group-2",
    reinforcesGroupId: "group-1",
    slots: [
      slot({ agentId: "mav-011", groupId: "group-2", swarmIndex: 2, reinforcement: true }),
      slot({
        index: 2,
        role: "OVERWATCH",
        agentId: "mav-012",
        groupId: "group-2",
        swarmIndex: 2,
        reinforcement: true,
      }),
    ],
  });

  const capacity = [
    row("mav-004", 0.0012),
    row("mav-002", 0.0009),
    row("mav-011", -0.0011),
    row("mav-012", -0.0008),
  ];

  it("draws one hull per swarm, each captioned with its identity and strength", () => {
    const { container, getByTestId } = overlay(
      [objective({ swarms: [first, second], slots: [...first.slots, ...second.slots] })],
      capacity
    );

    expect(container.querySelectorAll('[data-testid^="swarm-hull-"]')).toHaveLength(2);
    expect(getByTestId("swarm-caption-group-1")).toHaveTextContent("execution group");
    expect(getByTestId("swarm-strength-group-1")).toHaveTextContent("02 / 02");
    expect(getByTestId("swarm-caption-group-2")).toHaveTextContent("reinforcement");
    expect(getByTestId("swarm-caption-group-2")).toHaveTextContent("EG-group-2");
  });

  it("draws one hull for one swarm", () => {
    const { container } = overlay(
      [objective({ swarms: [first], slots: first.slots })],
      capacity.slice(0, 2)
    );
    expect(container.querySelectorAll('[data-testid^="swarm-hull-"]')).toHaveLength(1);
  });

  it("draws no hull for a single-executor objective, which is no swarm", () => {
    const { container } = overlay(
      [
        objective({
          groupId: null,
          swarms: [],
          slots: [slot({ groupId: null, roleIsAssigned: false, role: "VERIFY" })],
        }),
      ],
      capacity.slice(0, 1)
    );
    expect(container.querySelectorAll('[data-testid^="swarm-hull-"]')).toHaveLength(0);
  });

  it("draws no hull around subunits the map folded into the dock mark", () => {
    const docked = capacity
      .slice(0, 2)
      .map((r) => ({ ...r, fsmState: "DOCKED", altitudeAglM: 0 }));
    const { container } = overlay(
      [objective({ swarms: [first], slots: first.slots })],
      docked,
      new Set<string>()
    );
    expect(container.querySelectorAll('[data-testid^="swarm-hull-"]')).toHaveLength(0);
  });

  it("holds a wide formation's caption inside the band the panels leave clear", () => {
    const wide = swarm({
      requestedMembers: 6,
      composedMembers: 6,
      heldMembers: 6,
      slots: Array.from({ length: 6 }, (_, i) =>
        slot({ index: i + 1, role: `SWEEP_0${i + 1}`, agentId: `mav-1${i}` })
      ),
    });
    const line = wide.slots.map((s, i) =>
      row(s.agentId as string, 0.0016 - i * 0.0006, {
        geo: { lat: HOME.lat, lon: HOME.lon - 0.0022 + i * 0.0009 },
      })
    );

    const { getByTestId } = overlay(
      [objective({ swarms: [wide], slots: wide.slots })],
      line
    );

    const left = Number.parseFloat(getByTestId(`swarm-caption-${wide.groupId}`).style.left);
    expect(left).toBeGreaterThanOrEqual(INSET.left);
    expect(left + SWARM_CAPTION_W).toBeLessThanOrEqual(1600 - INSET.right);
  });

  it("reads an under-strength swarm in amber, never red", () => {
    const short = swarm({ ...first, requestedMembers: 4, underStrength: true });
    const { getByTestId, container } = overlay(
      [objective({ swarms: [short], slots: short.slots })],
      capacity.slice(0, 2)
    );

    const strength = getByTestId("swarm-strength-group-1");
    expect(strength).toHaveTextContent("02 / 04");
    expect(strength.parentElement?.className).toContain("text-launch-amber");
    const hull = container.querySelector('[data-testid="swarm-hull-group-1"] path');
    expect(hull?.getAttribute("fill")).toBe("#FFB45C");
    expect(container.innerHTML).not.toContain("#FF0000");
  });
});
