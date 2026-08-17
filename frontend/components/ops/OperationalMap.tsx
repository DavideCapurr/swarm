"use client";

/**
 * OperationalMap — real-world context around the deterministic SWARM map.
 *
 * The operational overlay remains the existing local east/north PX4/SWARM
 * projection. CARTO Dark tiles are rendered underneath as georeferenced visual
 * context only. Tile failure never removes operational state: the local grid,
 * agents, objectives, assignments and observed tracks remain authoritative.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import {
  boundsCenter,
  boundsHalfSpan,
  buildProjection,
  localBounds,
  snapExtent,
  type LocalPoint,
  type MapGeo,
} from "@/lib/opsmap";
import type { FleetRow, ObjectiveStory } from "@/lib/mission-story";

import { OperationalMap as LocalOperationalMap } from "./OperationalMapCore";

const DEFAULT_BOX = { width: 1600, height: 1100 };
const PADDING = 44;
const LOCAL_EARTH_RADIUS_M = 6_371_000;
const WEB_MERCATOR_RADIUS_M = 6_378_137;
const DEG = Math.PI / 180;
const TILE_SIZE = 256;
const MAX_TILE_ZOOM = 19;
const MAX_MERCATOR_LAT = 85.05112878;

type Tile = {
  key: string;
  url: string;
  left: number;
  top: number;
  size: number;
};

function useBoxSize() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [box, setBox] = useState(DEFAULT_BOX);

  useEffect(() => {
    const measure = () => {
      const rect = ref.current?.getBoundingClientRect();
      if (!rect || rect.width < 2 || rect.height < 2) return;
      setBox({ width: Math.round(rect.width), height: Math.round(rect.height) });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  return { ref, box };
}

function useSiteFrame(units: FleetRow[], stories: ObjectiveStory[]) {
  const originRef = useRef<MapGeo | null>(null);
  const extentRef = useRef(0);
  const centerRef = useRef<LocalPoint | null>(null);

  const anchor = units.find((unit) => Number.isFinite(unit.geo.lat) && unit.geo.lat !== 0);
  if (!originRef.current && anchor) {
    originRef.current = { lat: anchor.geo.lat, lon: anchor.geo.lon };
  }
  const origin = originRef.current;

  const points: MapGeo[] = [];
  if (origin) {
    for (const unit of units) points.push(unit.geo);
    for (const story of stories) {
      if (story.geo) points.push(story.geo);
      for (const point of story.track) points.push(point);
    }
  }

  const bounds = origin ? localBounds(origin, points) : null;
  if (bounds) {
    const wanted = boundsCenter(bounds);
    const held = centerRef.current;
    const drifted =
      !held ||
      Math.hypot(wanted.e - held.e, wanted.n - held.n) > Math.max(8, extentRef.current * 0.3);
    if (drifted) centerRef.current = wanted;
  }

  const center = centerRef.current ?? { e: 0, n: 0 };
  const needed = bounds ? boundsHalfSpan(bounds, center) : 0;
  extentRef.current = snapExtent(needed, extentRef.current);

  return { origin, extentM: extentRef.current, center };
}

function localToGeo(origin: MapGeo, point: LocalPoint): MapGeo {
  return {
    lat: origin.lat + point.n / (LOCAL_EARTH_RADIUS_M * DEG),
    lon:
      origin.lon +
      point.e / (LOCAL_EARTH_RADIUS_M * Math.cos(origin.lat * DEG) * DEG),
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

function buildTiles(
  origin: MapGeo,
  center: LocalPoint,
  mPerPx: number,
  box: { width: number; height: number }
): Tile[] {
  const centerGeo = localToGeo(origin, center);
  const groundCircumference =
    2 * Math.PI * WEB_MERCATOR_RADIUS_M * Math.cos(centerGeo.lat * DEG);
  const fractionalZoom = Math.max(
    1,
    Math.min(21, Math.log2(groundCircumference / (TILE_SIZE * Math.max(mPerPx, 0.0001))))
  );
  const zoom = Math.max(1, Math.min(MAX_TILE_ZOOM, Math.floor(fractionalZoom)));
  const scale = 2 ** (fractionalZoom - zoom);
  const centerWorld = worldPixel(centerGeo, zoom);
  const tileCount = 2 ** zoom;

  const xMin = Math.floor((centerWorld.x - box.width / (2 * scale)) / TILE_SIZE) - 1;
  const xMax = Math.floor((centerWorld.x + box.width / (2 * scale)) / TILE_SIZE) + 1;
  const yMin = Math.max(
    0,
    Math.floor((centerWorld.y - box.height / (2 * scale)) / TILE_SIZE) - 1
  );
  const yMax = Math.min(
    tileCount - 1,
    Math.floor((centerWorld.y + box.height / (2 * scale)) / TILE_SIZE) + 1
  );

  const tiles: Tile[] = [];
  for (let y = yMin; y <= yMax; y += 1) {
    for (let x = xMin; x <= xMax; x += 1) {
      const wrappedX = ((x % tileCount) + tileCount) % tileCount;
      tiles.push({
        key: `${zoom}/${x}/${y}`,
        url: `https://a.basemaps.cartocdn.com/dark_all/${zoom}/${wrappedX}/${y}@2x.png`,
        left: box.width / 2 + (x * TILE_SIZE - centerWorld.x) * scale,
        top: box.height / 2 + (y * TILE_SIZE - centerWorld.y) * scale,
        size: TILE_SIZE * scale + 1,
      });
    }
  }
  return tiles;
}

function Basemap({
  origin,
  center,
  mPerPx,
  box,
}: {
  origin: MapGeo;
  center: LocalPoint;
  mPerPx: number;
  box: { width: number; height: number };
}) {
  const tiles = useMemo(
    () => buildTiles(origin, center, mPerPx, box),
    [origin, center, mPerPx, box]
  );

  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute inset-0"
        data-testid="real-basemap"
        style={{ filter: "grayscale(1) brightness(1.35) contrast(1.08)", opacity: 0.96 }}
      >
        {tiles.map((tile) => (
          <div
            key={tile.key}
            className="absolute bg-cover bg-center bg-no-repeat"
            style={{
              left: tile.left,
              top: tile.top,
              width: tile.size,
              height: tile.size,
              backgroundImage: `url(${tile.url})`,
            }}
          />
        ))}
      </div>
      <div className="absolute inset-0 bg-absolute-black/15" />
    </div>
  );
}

export function OperationalMap({
  units,
  stories,
  focusMissionId,
}: {
  units: FleetRow[];
  stories: ObjectiveStory[];
  focusMissionId: string | null;
}) {
  const { ref, box } = useBoxSize();
  const { origin, extentM, center } = useSiteFrame(units, stories);
  const projection = useMemo(
    () =>
      origin
        ? buildProjection(
            origin,
            extentM,
            { width: box.width, height: box.height, padding: PADDING },
            center
          )
        : null,
    [origin, extentM, box.width, box.height, center]
  );

  return (
    <div ref={ref} className="relative h-full w-full overflow-hidden bg-absolute-black">
      {origin && projection ? (
        <Basemap origin={origin} center={center} mPerPx={projection.mPerPx} box={box} />
      ) : null}

      <div className="absolute inset-0 z-10" style={{ mixBlendMode: "screen" }}>
        <LocalOperationalMap
          units={units}
          stories={stories}
          focusMissionId={focusMissionId}
        />
      </div>

      {origin ? (
        <div className="pointer-events-none absolute bottom-3 left-1/2 z-20 -translate-x-1/2 bg-absolute-black/70 px-2 py-1 font-mono text-[10px] tracking-[0.08em] text-ash">
          REAL BASEMAP · © OPENSTREETMAP CONTRIBUTORS · © CARTO · CONTEXT ONLY
        </div>
      ) : null}
    </div>
  );
}
