/**
 * projection.ts — the site frame the full-bleed map is drawn in.
 *
 * The Console never invents a position. Every mark is a server frame
 * (`UnitState.geo`, `AnomalyView.geo`, `MissionView.track`) projected into the
 * local east/north frame `lib/opsmap.ts` defines, whose spherical model matches
 * the allocator's own distance model.
 *
 * Two things are added on top of `opsmap`:
 *
 *   1. a screen offset, because the operating surfaces float over the map and
 *      the geography has to be composed into the part of the viewport they
 *      leave clear rather than into the raw pixel centre;
 *   2. the Web Mercator tile cover for the satellite basemap underneath.
 */

import {
  boundsCenter,
  buildProjection,
  localBounds,
  type LocalBounds,
  type LocalPoint,
  type MapGeo,
  type ScreenPoint,
  type SiteProjection,
} from "@/lib/opsmap";

const TILE_SIZE = 256;
const MAX_TILE_ZOOM = 19;
const MAX_MERCATOR_LAT = 85.05112878;
const WEB_MERCATOR_RADIUS_M = 6_378_137;
const LOCAL_EARTH_RADIUS_M = 6_371_000;
const DEG = Math.PI / 180;

/**
 * Closest half-extent the camera is allowed to hold.
 *
 * A cooperative objective ends with every observer over the same point,
 * separated only by altitude, so the framing it asks for collapses toward zero.
 * The floor is what the close-in actually settles on: 45 m holds the objective
 * and the ground around it at a scale where the site is still legible. It
 * changes the camera, never a coordinate.
 *
 * 55 m is the balance point measured on the recording viewport: a cooperative
 * objective works inside about 40 m of its target, which at this extent fills
 * the clear area of the frame at roughly 6 px per metre — enough that two
 * aircraft holding station metres apart still read as two aircraft, while a
 * full city block of context stays in shot.
 */
export const MIN_EXTENT_M = 45;

/**
 * Half-extent needed to hold `bounds` around `center`.
 *
 * `opsmap.boundsHalfSpan` takes the larger of the two axes and adds 12%. On a
 * 16:9 viewport the projection then inscribes that square in the *shorter*
 * side, so a scene that is wide and shallow — which is what a fleet converging
 * on one objective looks like — pays for vertical space it never uses. This
 * measures the axes against the box it is actually being drawn into.
 */
function halfSpanFor(
  bounds: LocalBounds,
  center: LocalPoint,
  aspect: number
): number {
  const e = Math.max(Math.abs(bounds.maxE - center.e), Math.abs(center.e - bounds.minE));
  const n = Math.max(Math.abs(bounds.maxN - center.n), Math.abs(center.n - bounds.minN));
  // The projection scales by the shorter side, so the east axis only needs the
  // extent it exceeds the aspect ratio by.
  return Math.max(n, e / Math.max(aspect, 1)) * 1.04;
}

export type Box = { width: number; height: number };

/** Pixels the operating surfaces occupy, so geography composes into what is left. */
export type SafeInset = { left: number; right: number; top: number; bottom: number };

export type Frame = {
  origin: MapGeo | null;
  center: LocalPoint;
  extentM: number;
};

/** Offset in pixels from the raw viewport centre to the centre of the clear area. */
export function safeOffset(box: Box, inset: SafeInset): ScreenPoint {
  return {
    x: (inset.left - inset.right) / 2,
    y: (inset.top - inset.bottom) / 2,
  };
}

export type ConsoleProjection = SiteProjection & {
  /** Where the frame origin — the observed home — lands on screen. */
  originPoint: ScreenPoint;
};

export function buildConsoleProjection(
  frame: Frame,
  box: Box,
  inset: SafeInset
): ConsoleProjection | null {
  if (!frame.origin) return null;
  const offset = safeOffset(box, inset);
  // The usable square is measured inside the inset so the scene is solved for
  // the clear area, then drawn across the whole viewport. The padding is the
  // margin captions need past the outermost glyph, nothing more — at 56 it was
  // taking 112 px out of a 620 px usable height, which the transit paid for.
  const padding = 26;
  const usable = {
    width: Math.max(1, box.width - inset.left - inset.right),
    height: Math.max(1, box.height - inset.top - inset.bottom),
  };
  const base = buildProjection(
    frame.origin,
    frame.extentM,
    { width: usable.width, height: usable.height, padding },
    frame.center
  );
  // `base` centres on the usable box; shift it back into viewport coordinates.
  const shiftX = (box.width - usable.width) / 2 + offset.x;
  const shiftY = (box.height - usable.height) / 2 + offset.y;
  const move = (point: ScreenPoint): ScreenPoint => ({
    x: point.x + shiftX,
    y: point.y + shiftY,
  });

  return {
    ...base,
    project: (geo) => move(base.project(geo)),
    projectLocal: (point) => move(base.projectLocal(point)),
    originPoint: move(base.projectLocal({ e: 0, n: 0 })),
  };
}

/**
 * Solve where the camera wants to be, from the marks that matter right now.
 *
 * This is a target, not a position — `useCameraGlide` is what actually moves.
 * It is recomputed every frame and it is deliberately not sticky: the whole
 * point is that the framing follows the mission. A fleet spread across a long
 * transit pulls the camera out; the same fleet converging on station lets it
 * come back in; a replacement launching from unused capacity on the far side of
 * the site pulls it out again.
 *
 * The origin is the exception. It is the first agent position the session
 * observed — the home the fleet launched from — and it is held for the rest of
 * the session, so every distance still means "from home".
 */
export function targetFrame(
  origin: MapGeo | null,
  points: readonly MapGeo[],
  /** Width / height of the area the scene is composed into. */
  aspect = 1
): Frame & { center: LocalPoint } {
  if (!origin) return { origin: null, center: { e: 0, n: 0 }, extentM: MIN_EXTENT_M };

  const bounds = localBounds(origin, points);
  if (!bounds) return { origin, center: { e: 0, n: 0 }, extentM: MIN_EXTENT_M };

  const center = boundsCenter(bounds);
  const extentM = Math.max(MIN_EXTENT_M, halfSpanFor(bounds, center, aspect));
  return { origin, center, extentM };
}

/** Pick the origin once, from the first real position the session sees. */
export function anchorOrigin(points: readonly MapGeo[]): MapGeo | null {
  const anchor = points.find((p) => Number.isFinite(p.lat) && p.lat !== 0);
  return anchor ? { lat: anchor.lat, lon: anchor.lon } : null;
}

// ── Satellite basemap ────────────────────────────────────────────────────────

export type Tile = {
  key: string;
  url: string;
  left: number;
  top: number;
  size: number;
};

/**
 * Esri World Imagery — the satellite basemap.
 *
 * Pinned in the Console CSP (`connect-src` in next.config.mjs). It carries no
 * operational claim: tile failure removes context, never state. The site frame,
 * executors, objectives and tracks are local and stay authoritative either way.
 */
const IMAGERY_HOST = "https://server.arcgisonline.com";
const IMAGERY_PATH = "/ArcGIS/rest/services/World_Imagery/MapServer/tile";

export const IMAGERY_ATTRIBUTION =
  "SATELLITE IMAGERY · ESRI · MAXAR · EARTHSTAR GEOGRAPHICS · GEOGRAPHIC CONTEXT ONLY";
export const IMAGERY_UNAVAILABLE =
  "SATELLITE IMAGERY UNAVAILABLE · SITE FRAME ONLY · NO GEOGRAPHIC CONTEXT";

export function tileUrl(z: number, x: number, y: number): string {
  return `${IMAGERY_HOST}${IMAGERY_PATH}/${z}/${y}/${x}`;
}

function localToGeo(origin: MapGeo, point: LocalPoint): MapGeo {
  return {
    lat: origin.lat + point.n / (LOCAL_EARTH_RADIUS_M * DEG),
    lon: origin.lon + point.e / (LOCAL_EARTH_RADIUS_M * Math.cos(origin.lat * DEG) * DEG),
  };
}

function worldPixel(geo: MapGeo, zoom: number) {
  const lat = Math.max(-MAX_MERCATOR_LAT, Math.min(MAX_MERCATOR_LAT, geo.lat));
  const worldSize = TILE_SIZE * 2 ** zoom;
  const sin = Math.sin(lat * DEG);
  return {
    x: ((geo.lon + 180) / 360) * worldSize,
    y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * worldSize,
  };
}

/**
 * Tile cover for the current camera.
 *
 * The integer zoom is rounded *up* from the fractional one, so tiles are drawn
 * at 0.5–1.0 scale. Downscaled imagery stays crisp; upscaled imagery does not,
 * and this surface is delivered as a recording.
 */
export function buildTiles(
  frame: Frame & { center: LocalPoint },
  projection: ConsoleProjection,
  box: Box
): Tile[] {
  if (!frame.origin) return [];
  const centerGeo = localToGeo(frame.origin, frame.center);
  const groundCircumference =
    2 * Math.PI * WEB_MERCATOR_RADIUS_M * Math.cos(centerGeo.lat * DEG);
  const fractionalZoom = Math.max(
    1,
    Math.min(22, Math.log2(groundCircumference / (TILE_SIZE * Math.max(projection.mPerPx, 1e-4))))
  );
  const zoom = Math.max(1, Math.min(MAX_TILE_ZOOM, Math.ceil(fractionalZoom)));
  const scale = 2 ** (fractionalZoom - zoom);
  const centerWorld = worldPixel(centerGeo, zoom);
  const tileCount = 2 ** zoom;

  // The camera centre does not sit at the pixel centre — the operating surfaces
  // pushed it — so tiles are laid out around wherever that centre actually is.
  const centerPx = projection.projectLocal(frame.center);

  const xMin = Math.floor((centerWorld.x - centerPx.x / scale) / TILE_SIZE);
  const xMax = Math.floor((centerWorld.x + (box.width - centerPx.x) / scale) / TILE_SIZE);
  const yMin = Math.max(
    0,
    Math.floor((centerWorld.y - centerPx.y / scale) / TILE_SIZE)
  );
  const yMax = Math.min(
    tileCount - 1,
    Math.floor((centerWorld.y + (box.height - centerPx.y) / scale) / TILE_SIZE)
  );

  const tiles: Tile[] = [];
  for (let y = yMin; y <= yMax; y += 1) {
    for (let x = xMin; x <= xMax; x += 1) {
      const wrappedX = ((x % tileCount) + tileCount) % tileCount;
      tiles.push({
        key: `${zoom}/${x}/${y}`,
        url: tileUrl(zoom, wrappedX, y),
        left: centerPx.x + (x * TILE_SIZE - centerWorld.x) * scale,
        top: centerPx.y + (y * TILE_SIZE - centerWorld.y) * scale,
        // The +1 closes the sub-pixel seam between neighbouring tiles.
        size: TILE_SIZE * scale + 1,
      });
    }
  }
  return tiles;
}
