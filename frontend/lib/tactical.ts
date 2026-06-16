/**
 * tactical.ts — procedural dark tactical basemap geometry.
 *
 * SWARM renders its own basemap rather than pulling a third-party raster tile
 * set: the surface must be guaranteed dark (design system §5.2 — no light
 * chrome), deterministic, and work with no network. This module turns a map
 * centre into the GeoJSON a tactical grid is drawn from — a fine + coarse
 * graticule, range rings from the dock, the owner-land parcel, and the axial
 * crosshair. All monochrome; accent colour is reserved for live state.
 */

export type LngLat = [number, number];

const M_PER_DEG = 111_000; // equirectangular approximation (matches the sim)

/** Offset metres east/north of `center` into a [lon, lat] pair. */
export function metersToLngLat(
  center: LngLat,
  eastM: number,
  northM: number
): LngLat {
  const [lon, lat] = center;
  const dLat = northM / M_PER_DEG;
  const dLon = eastM / (M_PER_DEG * Math.cos((lat * Math.PI) / 180));
  return [lon + dLon, lat + dLat];
}

function ring(center: LngLat, radiusM: number, points = 72): LngLat[] {
  const out: LngLat[] = [];
  for (let i = 0; i <= points; i++) {
    const a = (i / points) * Math.PI * 2;
    out.push(metersToLngLat(center, radiusM * Math.sin(a), radiusM * Math.cos(a)));
  }
  return out;
}

function line(coords: LngLat[], props: Record<string, unknown> = {}): GeoJSON.Feature {
  return {
    type: "Feature",
    properties: props,
    geometry: { type: "LineString", coordinates: coords },
  };
}

function fc(features: GeoJSON.Feature[]): GeoJSON.FeatureCollection {
  return { type: "FeatureCollection", features };
}

export type TacticalGeometry = {
  /** Fine graticule — faintest. */
  grid: GeoJSON.FeatureCollection;
  /** Coarse graticule every 5 fine cells — a touch brighter. */
  coarse: GeoJSON.FeatureCollection;
  /** Concentric range rings from the dock. */
  rings: GeoJSON.FeatureCollection;
  /** Ring distance labels ("100 m", …) as Points. */
  ringLabels: GeoJSON.FeatureCollection;
  /** Owner-land parcel boundary (fill + outline). */
  parcel: GeoJSON.FeatureCollection;
  /** Axial crosshair through the dock. */
  axes: GeoJSON.FeatureCollection;
};

export type TacticalOptions = {
  extentM?: number; // half-width of the grid
  fineStepM?: number; // fine graticule spacing
  coarseEveryM?: number; // coarse graticule spacing
  ringStepM?: number; // range-ring spacing
  ringCount?: number; // number of range rings
  parcelWidthM?: number; // owner-land parcel E-W extent
  parcelHeightM?: number; // owner-land parcel N-S extent
};

/**
 * Build the tactical basemap geometry around `center`.
 *
 * Defaults are tuned for the ~2 ha owner-land scene at zoom 14.5.
 */
export function buildTactical(
  center: LngLat,
  opts: TacticalOptions = {}
): TacticalGeometry {
  const extentM = opts.extentM ?? 900;
  const fineStepM = opts.fineStepM ?? 60;
  const coarseEveryM = opts.coarseEveryM ?? 300;
  const ringStepM = opts.ringStepM ?? 100;
  const ringCount = opts.ringCount ?? 4;
  const parcelWidthM = opts.parcelWidthM ?? 200;
  const parcelHeightM = opts.parcelHeightM ?? 100;

  const grid: GeoJSON.Feature[] = [];
  const coarse: GeoJSON.Feature[] = [];
  for (let d = -extentM; d <= extentM + 0.1; d += fineStepM) {
    const isCoarse = Math.abs(d % coarseEveryM) < 0.5;
    const vertical = line([
      metersToLngLat(center, d, -extentM),
      metersToLngLat(center, d, extentM),
    ]);
    const horizontal = line([
      metersToLngLat(center, -extentM, d),
      metersToLngLat(center, extentM, d),
    ]);
    (isCoarse ? coarse : grid).push(vertical, horizontal);
  }

  const rings: GeoJSON.Feature[] = [];
  const ringLabels: GeoJSON.Feature[] = [];
  for (let i = 1; i <= ringCount; i++) {
    const r = i * ringStepM;
    rings.push(line(ring(center, r), { r }));
    ringLabels.push({
      type: "Feature",
      properties: { label: `${r} m` },
      geometry: { type: "Point", coordinates: metersToLngLat(center, 0, r) },
    });
  }

  const hw = parcelWidthM / 2;
  const hh = parcelHeightM / 2;
  const parcelRing: LngLat[] = [
    metersToLngLat(center, -hw, -hh),
    metersToLngLat(center, hw, -hh),
    metersToLngLat(center, hw, hh),
    metersToLngLat(center, -hw, hh),
    metersToLngLat(center, -hw, -hh),
  ];
  const parcel: GeoJSON.Feature[] = [
    {
      type: "Feature",
      properties: { kind: "parcel" },
      geometry: { type: "Polygon", coordinates: [parcelRing] },
    },
  ];

  const axes: GeoJSON.Feature[] = [
    line([
      metersToLngLat(center, -extentM, 0),
      metersToLngLat(center, extentM, 0),
    ]),
    line([
      metersToLngLat(center, 0, -extentM),
      metersToLngLat(center, 0, extentM),
    ]),
  ];

  return {
    grid: fc(grid),
    coarse: fc(coarse),
    rings: fc(rings),
    ringLabels: fc(ringLabels),
    parcel: fc(parcel),
    axes: fc(axes),
  };
}
