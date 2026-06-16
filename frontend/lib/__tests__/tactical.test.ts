import { describe, it, expect } from "vitest";

import { buildTactical, metersToLngLat, type LngLat } from "@/lib/tactical";

const CENTER: LngLat = [8.03, 44.7]; // Langhe, IT — the demo scene centre.

describe("metersToLngLat", () => {
  it("returns the centre unchanged at a zero offset", () => {
    expect(metersToLngLat(CENTER, 0, 0)).toEqual(CENTER);
  });

  it("moves north by ~1 degree of latitude per 111 km", () => {
    const [, lat] = metersToLngLat(CENTER, 0, 111_000);
    expect(lat).toBeCloseTo(45.7, 6);
  });

  it("moves east (lon up) and north (lat up) for positive offsets", () => {
    const [lon, lat] = metersToLngLat(CENTER, 250, 250);
    expect(lon).toBeGreaterThan(CENTER[0]);
    expect(lat).toBeGreaterThan(CENTER[1]);
  });

  it("scales longitude by 1/cos(lat) so east metres widen near the pole", () => {
    // At 44.7°N, a degree of longitude is shorter than a degree of latitude,
    // so the same metre offset produces a larger longitude delta.
    const [lonE] = metersToLngLat(CENTER, 1000, 0);
    const [, latN] = metersToLngLat(CENTER, 0, 1000);
    const dLon = lonE - CENTER[0];
    const dLat = latN - CENTER[1];
    expect(dLon).toBeGreaterThan(dLat);
  });
});

describe("buildTactical", () => {
  it("is deterministic — identical centres yield identical geometry", () => {
    expect(buildTactical(CENTER)).toEqual(buildTactical(CENTER));
  });

  it("returns every named layer as a FeatureCollection", () => {
    const geo = buildTactical(CENTER);
    for (const key of [
      "grid",
      "coarse",
      "rings",
      "ringLabels",
      "parcel",
      "axes",
    ] as const) {
      expect(geo[key].type).toBe("FeatureCollection");
      expect(Array.isArray(geo[key].features)).toBe(true);
    }
  });

  it("emits one ring and one ring label per ringCount, with metric labels", () => {
    const geo = buildTactical(CENTER, { ringCount: 4, ringStepM: 100 });
    expect(geo.rings.features).toHaveLength(4);
    expect(geo.ringLabels.features).toHaveLength(4);
    const labels = geo.ringLabels.features.map((f) => f.properties?.label);
    expect(labels).toEqual(["100 m", "200 m", "300 m", "400 m"]);
  });

  it("honours custom ring options", () => {
    const geo = buildTactical(CENTER, { ringCount: 2, ringStepM: 50 });
    expect(geo.rings.features).toHaveLength(2);
    expect(geo.ringLabels.features.map((f) => f.properties?.label)).toEqual([
      "50 m",
      "100 m",
    ]);
  });

  it("places each ring label due north of the centre at its radius", () => {
    const geo = buildTactical(CENTER, { ringCount: 1, ringStepM: 100 });
    const pt = geo.ringLabels.features[0].geometry as GeoJSON.Point;
    const [lon, lat] = pt.coordinates as [number, number];
    expect(lon).toBeCloseTo(CENTER[0], 9); // same meridian
    expect(lat).toBeGreaterThan(CENTER[1]); // north of centre
  });

  it("draws the owner-land parcel as a single closed polygon", () => {
    const geo = buildTactical(CENTER);
    expect(geo.parcel.features).toHaveLength(1);
    const poly = geo.parcel.features[0].geometry as GeoJSON.Polygon;
    expect(poly.type).toBe("Polygon");
    const ring = poly.coordinates[0];
    expect(ring).toHaveLength(5); // 4 corners + closing vertex
    expect(ring[0]).toEqual(ring[ring.length - 1]); // closed
  });

  it("draws the axial crosshair as two line strings through the dock", () => {
    const geo = buildTactical(CENTER);
    expect(geo.axes.features).toHaveLength(2);
    for (const f of geo.axes.features) {
      expect(f.geometry.type).toBe("LineString");
    }
  });

  it("splits the graticule into coarse and fine lines on the coarse spacing", () => {
    // extent 900, fine step 60, coarse every 300 → coarse positions at
    // {-900,-600,-300,0,300,600,900} = 7, each emitting a V+H line = 14;
    // the remaining 24 positions emit the fine grid = 48 lines.
    const geo = buildTactical(CENTER);
    expect(geo.coarse.features).toHaveLength(14);
    expect(geo.grid.features).toHaveLength(48);
    for (const f of [...geo.grid.features, ...geo.coarse.features]) {
      expect(f.geometry.type).toBe("LineString");
      expect((f.geometry as GeoJSON.LineString).coordinates).toHaveLength(2);
    }
  });
});
