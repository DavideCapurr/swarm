/**
 * opsmap.ts — the site frame the operational map is drawn in.
 *
 * The Console never invents a position. Every point on the map is a server
 * frame (`UnitState.geo`, `AnomalyView.geo`, `MissionView.track`) projected
 * into a local east/north frame anchored on an observed origin. This module is
 * the projection only: it holds no state and reads no truth.
 *
 * The spherical model matches `core/swarm_core/geometry.haversine_m` so a
 * distance read off the map agrees with the `distance_m` the allocator
 * published in its score breakdown.
 */

export type MapGeo = { lat: number; lon: number };

/** Metres east / north of the frame origin. */
export type LocalPoint = { e: number; n: number };

/** Pixel coordinates inside the map viewport, origin top-left. */
export type ScreenPoint = { x: number; y: number };

export type Viewport = { width: number; height: number; padding: number };

const EARTH_RADIUS_M = 6_371_000.0;
const DEG = Math.PI / 180;

/** Project a geo point into metres east/north of `origin`. */
export function toLocal(origin: MapGeo, geo: MapGeo): LocalPoint {
  const n = EARTH_RADIUS_M * (geo.lat - origin.lat) * DEG;
  const e = EARTH_RADIUS_M * Math.cos(origin.lat * DEG) * (geo.lon - origin.lon) * DEG;
  return { e, n };
}

/** Ground distance in metres between two geo points. */
export function distanceM(a: MapGeo, b: MapGeo): number {
  const { e, n } = toLocal(a, b);
  return Math.hypot(e, n);
}

/**
 * Half-extents the frame may take, in metres.
 *
 * The frame snaps to one of these and never shrinks during a session. A map
 * that rescales continuously while a mission runs is unreadable on a
 * recording, and a jumping scale makes two takes impossible to compare.
 */
export const EXTENT_STEPS_M = [
  20, 25, 30, 40, 50, 60, 80, 100, 150, 200, 300, 500, 800, 1200, 2000, 3000,
] as const;

/** Smallest allowed half-extent that covers `required` and never regresses. */
export function snapExtent(requiredM: number, floorM = 0): number {
  const need = Math.max(requiredM, floorM);
  for (const step of EXTENT_STEPS_M) {
    if (step >= need) return step;
  }
  return EXTENT_STEPS_M[EXTENT_STEPS_M.length - 1];
}

export type LocalBounds = { minE: number; maxE: number; minN: number; maxN: number };

/** Local extent of a set of geo points, or null when there are none. */
export function localBounds(origin: MapGeo, points: readonly MapGeo[]): LocalBounds | null {
  if (points.length === 0) return null;
  let minE = Infinity;
  let maxE = -Infinity;
  let minN = Infinity;
  let maxN = -Infinity;
  for (const point of points) {
    const { e, n } = toLocal(origin, point);
    minE = Math.min(minE, e);
    maxE = Math.max(maxE, e);
    minN = Math.min(minN, n);
    maxN = Math.max(maxN, n);
  }
  return { minE, maxE, minN, maxN };
}

export function boundsCenter(bounds: LocalBounds): LocalPoint {
  return { e: (bounds.minE + bounds.maxE) / 2, n: (bounds.minN + bounds.maxN) / 2 };
}

/**
 * Half-extent needed to hold the bounds around `center`, with 12% headroom so
 * glyphs and labels never sit on the frame edge.
 */
export function boundsHalfSpan(bounds: LocalBounds, center: LocalPoint): number {
  const e = Math.max(Math.abs(bounds.maxE - center.e), Math.abs(center.e - bounds.minE));
  const n = Math.max(Math.abs(bounds.maxN - center.n), Math.abs(center.n - bounds.minN));
  return Math.max(e, n) * 1.12;
}

/** Grid spacing that keeps the graticule readable at the current extent. */
export function gridStepM(extentM: number): number {
  if (extentM <= 60) return 10;
  if (extentM <= 120) return 20;
  if (extentM <= 300) return 50;
  if (extentM <= 800) return 100;
  if (extentM <= 2000) return 250;
  return 500;
}

/** Range-ring radii from the frame origin, inside the current extent. */
export function ringRadiiM(extentM: number): number[] {
  const step = gridStepM(extentM) * 2;
  const out: number[] = [];
  for (let r = step; r <= extentM; r += step) out.push(r);
  return out;
}

export type SiteProjection = {
  origin: MapGeo;
  /** Local point the viewport is centred on. */
  centerLocal: LocalPoint;
  /** Half-extent of the square frame, in metres. */
  extentM: number;
  /** Metres represented by one pixel. */
  mPerPx: number;
  /** Geo → viewport pixels. */
  project: (geo: MapGeo) => ScreenPoint;
  /** Local east/north metres → viewport pixels. */
  projectLocal: (point: LocalPoint) => ScreenPoint;
  /** Metres → pixel length. */
  toPx: (metres: number) => number;
};

/**
 * Build the projection for one render.
 *
 * Coordinates stay anchored on `origin` — the observed home — so the graticule,
 * range rings and distance readouts all mean "from home". `centerLocal` only
 * moves what the viewport is looking at, so the scene can fill the box when
 * the fleet is working off to one side of home. Scale is isotropic: one metre
 * is the same length in both axes.
 */
export function buildProjection(
  origin: MapGeo,
  extentM: number,
  viewport: Viewport,
  centerLocal: LocalPoint = { e: 0, n: 0 }
): SiteProjection {
  const usableW = Math.max(1, viewport.width - viewport.padding * 2);
  const usableH = Math.max(1, viewport.height - viewport.padding * 2);
  const side = Math.min(usableW, usableH);
  const safeExtent = extentM > 0 ? extentM : EXTENT_STEPS_M[0];
  const pxPerM = side / (safeExtent * 2);
  const cx = viewport.width / 2;
  const cy = viewport.height / 2;

  const projectLocal = ({ e, n }: LocalPoint): ScreenPoint => ({
    x: cx + (e - centerLocal.e) * pxPerM,
    // North is up: screen y grows downwards.
    y: cy - (n - centerLocal.n) * pxPerM,
  });

  return {
    origin,
    centerLocal,
    extentM: safeExtent,
    mPerPx: 1 / pxPerM,
    project: (geo) => projectLocal(toLocal(origin, geo)),
    projectLocal,
    toPx: (metres) => metres * pxPerM,
  };
}

/** Format a lat/lon for the frame-origin readout. */
export function formatGeo(geo: MapGeo): string {
  const ns = geo.lat >= 0 ? "N" : "S";
  const ew = geo.lon >= 0 ? "E" : "W";
  return `${ns} ${Math.abs(geo.lat).toFixed(5)}  ${ew} ${Math.abs(geo.lon).toFixed(5)}`;
}

/** Compass bearing label for a heading in degrees. */
export function bearingLabel(headingDeg: number): string {
  const normalised = ((headingDeg % 360) + 360) % 360;
  return `${normalised.toFixed(0).padStart(3, "0")}°`;
}
