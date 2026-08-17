import { describe, expect, it } from "vitest";

import {
  boundsCenter,
  boundsHalfSpan,
  buildProjection,
  distanceM,
  formatGeo,
  gridStepM,
  localBounds,
  ringRadiiM,
  snapExtent,
  toLocal,
} from "../opsmap";

// PX4 SITL default home and the recorded take-1 objective coordinates.
const HOME = { lat: 47.397742, lon: 8.545594 };
const OBJECTIVE_ONE = { lat: 47.398, lon: 8.546 };

describe("toLocal", () => {
  it("puts north in +n and east in +e", () => {
    const { e, n } = toLocal(HOME, OBJECTIVE_ONE);
    expect(n).toBeGreaterThan(0);
    expect(e).toBeGreaterThan(0);
  });

  it("is zero at the origin", () => {
    expect(toLocal(HOME, HOME)).toEqual({ e: 0, n: 0 });
  });

  it("agrees with the allocator's distance model to within a metre", () => {
    // core/swarm_core/geometry.haversine_m over the same pair is ~41.9 m.
    expect(distanceM(HOME, OBJECTIVE_ONE)).toBeCloseTo(41.9, 0);
  });
});

describe("snapExtent", () => {
  it("snaps up to the next allowed step", () => {
    expect(snapExtent(23)).toBe(25);
    expect(snapExtent(41)).toBe(50);
  });

  it("never regresses below the floor", () => {
    expect(snapExtent(12, 100)).toBe(100);
  });

  it("saturates at the largest step", () => {
    expect(snapExtent(99_999)).toBe(3000);
  });
});

describe("bounds", () => {
  const points = [HOME, OBJECTIVE_ONE, { lat: 47.39775, lon: 8.54559 }];

  it("returns null with no points", () => {
    expect(localBounds(HOME, [])).toBeNull();
  });

  it("centres on the middle of the observed scene, not on the origin", () => {
    const bounds = localBounds(HOME, points)!;
    const center = boundsCenter(bounds);
    expect(center.n).toBeGreaterThan(1);
    expect(center.e).toBeGreaterThan(1);
  });

  it("covers every point from the chosen centre", () => {
    const bounds = localBounds(HOME, points)!;
    const center = boundsCenter(bounds);
    const half = boundsHalfSpan(bounds, center);
    for (const point of points) {
      const { e, n } = toLocal(HOME, point);
      expect(Math.abs(e - center.e)).toBeLessThanOrEqual(half);
      expect(Math.abs(n - center.n)).toBeLessThanOrEqual(half);
    }
  });
});

describe("buildProjection", () => {
  const viewport = { width: 1200, height: 800, padding: 40 };

  it("keeps one metre scale in both axes", () => {
    const p = buildProjection(HOME, 50, viewport);
    const a = p.projectLocal({ e: 0, n: 0 });
    const east = p.projectLocal({ e: 10, n: 0 });
    const north = p.projectLocal({ e: 0, n: 10 });
    expect(east.x - a.x).toBeCloseTo(a.y - north.y, 6);
  });

  it("draws north upwards", () => {
    const p = buildProjection(HOME, 50, viewport);
    expect(p.project(OBJECTIVE_ONE).y).toBeLessThan(p.project(HOME).y);
  });

  it("centres the viewport on centerLocal", () => {
    const center = { e: 20, n: -10 };
    const p = buildProjection(HOME, 50, viewport, center);
    const mid = p.projectLocal(center);
    expect(mid.x).toBeCloseTo(viewport.width / 2, 6);
    expect(mid.y).toBeCloseTo(viewport.height / 2, 6);
  });

  it("fits the extent inside the smaller viewport dimension", () => {
    const p = buildProjection(HOME, 50, viewport);
    // 100 m across the frame must fit in 800 - 2*40 = 720 px.
    expect(p.toPx(100)).toBeCloseTo(720, 6);
  });
});

describe("frame furniture", () => {
  it("keeps the graticule readable as the extent grows", () => {
    expect(gridStepM(50)).toBeLessThan(gridStepM(500));
    expect(gridStepM(5000)).toBe(500);
  });

  it("only places range rings inside the frame", () => {
    for (const r of ringRadiiM(120)) expect(r).toBeLessThanOrEqual(120);
  });

  it("formats the origin readout with hemispheres", () => {
    expect(formatGeo(HOME)).toBe("N 47.39774  E 8.54559");
    expect(formatGeo({ lat: -12.5, lon: -70.25 })).toBe("S 12.50000  W 70.25000");
  });
});
