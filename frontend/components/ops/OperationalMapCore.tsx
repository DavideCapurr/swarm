"use client";

/**
 * OperationalMap — the primary surface.
 *
 * A procedural site frame drawn in SVG. There is no tile provider: the map is
 * a local east/north projection of the geo SwarmOS actually published, so the
 * scene is deterministic, offline, guaranteed dark, and every metre on it
 * agrees with the allocator's own distance model (`lib/opsmap.ts`).
 *
 * Nothing here is decorative. Each mark is an agent, an objective, an
 * assignment, an observed track, or the frame that makes those readable.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import {
  boundsCenter,
  boundsHalfSpan,
  buildProjection,
  formatGeo,
  gridStepM,
  localBounds,
  ringRadiiM,
  snapExtent,
  type LocalPoint,
  type MapGeo,
} from "@/lib/opsmap";
import type { FleetRow, ObjectiveStory } from "@/lib/mission-story";
import { tokens } from "@/lib/tokens";

import { Eyebrow } from "./primitives";

const DEFAULT_BOX = { width: 1600, height: 1100 };
const PADDING = 44;

// Agent caption block: offset below the glyph, line height, collision width.
const LABEL_DY = 34;
const LABEL_H = 36;
const LABEL_W = 150;

// Map chrome colours. Anything that exists in the design tokens is read from
// there rather than re-typed, so a palette change cannot leave the map behind —
// this block previously pinned the pre-AA ash for `label` and drifted.
// `grid` and `axis` are map-only structure tints with no token equivalent.
const C = {
  frame: tokens.color.gunmetal,
  grid: "#12171C",
  coarse: tokens.color.gunmetal,
  axis: "#232B33",
  label: tokens.color.ash,
  silver: tokens.color.mutedSilver,
  platinum: tokens.color.platinum,
  orbital: tokens.color.orbitalBlue,
  green: tokens.color.signalGreen,
  amber: tokens.color.launchAmber,
};

/** Measured size of the map box. Falls back to the design size before layout. */
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

/**
 * The frame origin is the first agent position this session observed — the
 * home the fleet launched from — and it is held for the rest of the session, so
 * every distance on the map means "from home".
 *
 * The view centre and the extent are deliberately sticky: the extent only ever
 * grows, and the centre only moves when the scene has drifted a long way out of
 * frame. A map that re-centres or re-scales continuously is unreadable on a
 * recording and makes two takes impossible to compare.
 */
function useSiteFrame(units: FleetRow[], stories: ObjectiveStory[]) {
  const originRef = useRef<MapGeo | null>(null);
  const extentRef = useRef<number>(0);
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

  // Two SITL aircraft can launch metres apart, which puts their glyphs on top of
  // each other. Stack the labels instead of letting them overprint — the order
  // is by agent id, so it is stable frame to frame.
  const labelOffsets = useMemo(() => {
    const offsets = new Map<string, number>();
    if (!projection) return offsets;
    // Collide the label blocks themselves, not the glyphs: two agents at
    // different heights can still end up with their captions on the same line.
    const placed: { x: number; y: number }[] = [];
    for (const unit of units) {
      const point = projection.project(unit.geo);
      let offset = 0;
      while (
        placed.some(
          (other) =>
            Math.abs(other.x - point.x) < LABEL_W &&
            Math.abs(other.y - (point.y + LABEL_DY + offset)) < LABEL_H
        )
      ) {
        offset += LABEL_H;
      }
      placed.push({ x: point.x, y: point.y + LABEL_DY + offset });
      offsets.set(unit.agentId, offset);
    }
    return offsets;
  }, [projection, units]);

  return (
    <div
      ref={ref}
      className="relative h-full w-full overflow-hidden border border-gunmetal bg-absolute-black"
      data-testid="operational-map"
    >
      {projection && origin ? (
        <svg
          width={box.width}
          height={box.height}
          viewBox={`0 0 ${box.width} ${box.height}`}
          className="block h-full w-full"
          role="img"
          aria-label="Operational site map"
        >
          <Graticule projection={projection} box={box} />
          <Rings projection={projection} />
          <Home projection={projection} />
          {stories.map((story) => (
            <Track key={`track-${story.missionId}`} story={story} projection={projection} />
          ))}
          {stories.map((story) => (
            <Assignment
              key={`link-${story.missionId}`}
              story={story}
              units={units}
              projection={projection}
              focused={story.missionId === focusMissionId}
            />
          ))}
          {stories.map((story) => (
            <ObjectiveMark
              key={`obj-${story.missionId}`}
              story={story}
              projection={projection}
              focused={story.missionId === focusMissionId}
            />
          ))}
          {units.map((unit) => (
            <AgentMark
              key={`unit-${unit.agentId}`}
              unit={unit}
              stories={stories}
              projection={projection}
              labelOffset={labelOffsets.get(unit.agentId) ?? 0}
            />
          ))}
        </svg>
      ) : (
        <div className="flex h-full items-center justify-center">
          <Eyebrow>awaiting fleet position frames</Eyebrow>
        </div>
      )}

      <MapChrome origin={origin} extentM={extentM} unitCount={units.length} />
      <Legend />
    </div>
  );
}

// ── Frame ─────────────────────────────────────────────────────────────────────

function Graticule({
  projection,
  box,
}: {
  projection: NonNullable<ReturnType<typeof buildProjection>>;
  box: { width: number; height: number };
}) {
  const step = gridStepM(projection.extentM);
  const lines: React.ReactNode[] = [];
  // Cover the whole visible box, not just the square frame: the view centre can
  // sit away from the origin, and a graticule that stops short reads as an edge.
  const halfW = (box.width / 2) * projection.mPerPx;
  const halfH = (box.height / 2) * projection.mPerPx;
  const eFrom = Math.floor((projection.centerLocal.e - halfW) / step) * step;
  const eTo = projection.centerLocal.e + halfW;
  const nFrom = Math.floor((projection.centerLocal.n - halfH) / step) * step;
  const nTo = projection.centerLocal.n + halfH;
  for (let d = eFrom; d <= eTo + 0.001; d += step) {
    const coarse = Math.abs(d % (step * 5)) < 0.001;
    const v = projection.projectLocal({ e: d, n: 0 }).x;
    lines.push(
      <line
        key={`v${d}`}
        x1={v}
        y1={0}
        x2={v}
        y2={box.height}
        stroke={coarse ? C.coarse : C.grid}
        strokeWidth={1}
      />
    );
  }
  for (let d = nFrom; d <= nTo + 0.001; d += step) {
    const coarse = Math.abs(d % (step * 5)) < 0.001;
    const h = projection.projectLocal({ e: 0, n: d }).y;
    lines.push(
      <line
        key={`h${d}`}
        x1={0}
        y1={h}
        x2={box.width}
        y2={h}
        stroke={coarse ? C.coarse : C.grid}
        strokeWidth={1}
      />
    );
  }
  const centre = projection.projectLocal({ e: 0, n: 0 });
  return (
    <g>
      {lines}
      <line x1={0} y1={centre.y} x2={box.width} y2={centre.y} stroke={C.axis} strokeWidth={1} />
      <line x1={centre.x} y1={0} x2={centre.x} y2={box.height} stroke={C.axis} strokeWidth={1} />
    </g>
  );
}

function Rings({ projection }: { projection: NonNullable<ReturnType<typeof buildProjection>> }) {
  const centre = projection.projectLocal({ e: 0, n: 0 });
  return (
    <g>
      {ringRadiiM(projection.extentM).map((r) => (
        <g key={r}>
          <circle
            cx={centre.x}
            cy={centre.y}
            r={projection.toPx(r)}
            fill="none"
            stroke={C.axis}
            strokeWidth={1}
            strokeDasharray="2 6"
          />
          <text
            x={centre.x + 5}
            y={centre.y - projection.toPx(r) - 5}
            fill={C.label}
            fontFamily={tokens.font.mono}
            fontSize={14}
            letterSpacing="0.08em"
          >
            {r} m
          </text>
        </g>
      ))}
    </g>
  );
}

function Home({ projection }: { projection: NonNullable<ReturnType<typeof buildProjection>> }) {
  const p = projection.projectLocal({ e: 0, n: 0 });
  return (
    <g>
      <rect
        x={p.x - 6}
        y={p.y - 6}
        width={12}
        height={12}
        fill="none"
        stroke={C.silver}
        strokeWidth={1.5}
      />
      {/* The square alone marks home. Its caption used to float beside it at a
          fixed offset and collided with whichever objective caption happened to
          sit near the origin — and the origin is already stated exactly, as
          lat/lon, in the site-frame block at the top left. Redundant chrome
          competing with live data is what made this map hard to read. */}
    </g>
  );
}

// ── Entities ──────────────────────────────────────────────────────────────────

function Track({
  story,
  projection,
}: {
  story: ObjectiveStory;
  projection: NonNullable<ReturnType<typeof buildProjection>>;
}) {
  if (story.track.length < 2) return null;
  const points = story.track.map((geo) => {
    const p = projection.project(geo);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  });
  return (
    <polyline
      points={points.join(" ")}
      fill="none"
      stroke={C.orbital}
      strokeOpacity={0.32}
      strokeWidth={1.5}
    />
  );
}

function Assignment({
  story,
  units,
  projection,
  focused,
}: {
  story: ObjectiveStory;
  units: FleetRow[];
  projection: NonNullable<ReturnType<typeof buildProjection>>;
  focused: boolean;
}) {
  if (!story.owner || !story.geo) return null;
  const owner = units.find((unit) => unit.agentId === story.owner);
  if (!owner) return null;
  const from = projection.project(owner.geo);
  const to = projection.project(story.geo);
  const arrived = story.latestStep === "ON STATION" || story.latestStep === "RTL";
  // The assignment is drawn, not captioned. A `owner → label` caption used to
  // sit at the midpoint of this line, which lands directly on both endpoints'
  // own captions whenever the agent is close to its objective — exactly the
  // moment the map matters most. The line, its colour and the legend already
  // say which agent is assigned where, and both ends are labelled.
  return (
    <g>
      <line
        x1={from.x}
        y1={from.y}
        x2={to.x}
        y2={to.y}
        stroke={arrived ? C.green : C.orbital}
        strokeOpacity={focused ? 0.85 : 0.4}
        strokeWidth={focused ? 1.5 : 1}
        strokeDasharray={arrived ? undefined : "5 5"}
      />
    </g>
  );
}

function ObjectiveMark({
  story,
  projection,
  focused,
}: {
  story: ObjectiveStory;
  projection: NonNullable<ReturnType<typeof buildProjection>>;
  focused: boolean;
}) {
  if (!story.geo) return null;
  const p = projection.project(story.geo);
  const r = 11;
  return (
    <g data-testid={`map-objective-${story.label.replace(" ", "-")}`}>
      <path
        d={`M ${p.x} ${p.y - r} L ${p.x + r} ${p.y} L ${p.x} ${p.y + r} L ${p.x - r} ${p.y} Z`}
        fill="none"
        stroke={C.amber}
        strokeWidth={focused ? 2 : 1.25}
      />
      <line x1={p.x - 3} y1={p.y} x2={p.x + 3} y2={p.y} stroke={C.amber} strokeWidth={1.25} />
      <line x1={p.x} y1={p.y - 3} x2={p.x} y2={p.y + 3} stroke={C.amber} strokeWidth={1.25} />
      {/* Objective labels always sit above the marker; agent labels always sit
          below theirs. The two can be metres apart on this site frame, so the
          separation has to come from the layout, not from luck. */}
      {/* 21px of baseline separation for a 20px face. At the previous 17px the
          objective label's own em box ran into its confidence line. */}
      <text
        x={p.x}
        y={p.y - r - 32}
        textAnchor="middle"
        fill={C.silver}
        fontFamily={tokens.font.mono}
        fontSize={20}
        letterSpacing="0.16em"
      >
        {story.label}
      </text>
      <text
        x={p.x}
        y={p.y - r - 11}
        textAnchor="middle"
        fill={focused ? C.platinum : C.silver}
        fontFamily={tokens.font.mono}
        fontSize={17}
        letterSpacing="0.1em"
      >
        {story.confidence != null
          ? `${story.kind} · ${(story.confidence * 100).toFixed(0)}%`
          : story.kind}
      </text>
    </g>
  );
}

function AgentMark({
  unit,
  stories,
  projection,
  labelOffset,
}: {
  unit: FleetRow;
  stories: ObjectiveStory[];
  projection: NonNullable<ReturnType<typeof buildProjection>>;
  labelOffset: number;
}) {
  const p = projection.project(unit.geo);
  const story = stories.find((s) => s.missionId === unit.missionId);
  const owning = Boolean(story);
  const verifiedArrival = Boolean(
    story?.ladder.find((slot) => slot.step === "ON STATION" && slot.source === "observed")?.proof
  );
  const colour = verifiedArrival ? C.green : owning ? C.orbital : C.silver;

  return (
    <g data-testid={`map-agent-${unit.agentId}`}>
      {owning ? (
        <circle
          cx={p.x}
          cy={p.y}
          r={17}
          fill="none"
          stroke={colour}
          strokeOpacity={0.45}
          strokeWidth={1}
        />
      ) : null}
      <g transform={`translate(${p.x} ${p.y}) rotate(${unit.headingDeg})`}>
        <path
          d="M 0 -10 L 7 8 L 0 4 L -7 8 Z"
          fill={colour}
          fillOpacity={owning ? 0.9 : 0.55}
          stroke={colour}
          strokeWidth={1.25}
          strokeLinejoin="round"
        />
      </g>
      {labelOffset > 0 ? (
        <line
          x1={p.x}
          y1={p.y + 18}
          x2={p.x}
          y2={p.y + labelOffset + 22}
          stroke={colour}
          strokeOpacity={0.4}
          strokeWidth={1}
        />
      ) : null}
      <text
        x={p.x}
        y={p.y + LABEL_DY + labelOffset}
        textAnchor="middle"
        fill={C.platinum}
        fontFamily={tokens.font.mono}
        fontSize={18}
        letterSpacing="0.1em"
      >
        {unit.agentId}
      </text>
      <text
        x={p.x}
        y={p.y + LABEL_DY + 16 + labelOffset}
        textAnchor="middle"
        fill={colour}
        fontFamily={tokens.font.mono}
        fontSize={15}
        letterSpacing="0.14em"
      >
        {unit.fsmState}
        {unit.altitudeAglM > 1 ? ` · ${unit.altitudeAglM.toFixed(0)} m AGL` : ""}
      </text>
    </g>
  );
}

// ── Chrome ────────────────────────────────────────────────────────────────────

function MapChrome({
  origin,
  extentM,
  unitCount,
}: {
  origin: MapGeo | null;
  extentM: number;
  unitCount: number;
}) {
  const step = gridStepM(extentM);
  return (
    <>
      <div className="pointer-events-none absolute left-3 top-3 flex flex-col gap-1">
        <Eyebrow tone="platinum">site frame · local east / north</Eyebrow>
        <span className="font-mono text-[12px] tracking-[0.12em] text-ash">
          {origin ? `ORIGIN ${formatGeo(origin)}` : "ORIGIN PENDING"}
        </span>
        <span className="font-mono text-[12px] tracking-[0.12em] text-ash">
          PROJECTED FROM PX4 SITL TELEMETRY · {unitCount} AGENT
          {unitCount === 1 ? "" : "S"}
        </span>
      </div>

      <div className="pointer-events-none absolute right-3 top-3 flex flex-col items-end gap-1">
        <svg width="26" height="30" viewBox="0 0 26 30" fill="none" aria-hidden="true">
          <path
            d="M13 3 L13 25 M13 3 L8 11 M13 3 L18 11"
            stroke={C.silver}
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="font-mono text-[12px] tracking-[0.18em] text-ash">N</span>
      </div>

      <div className="pointer-events-none absolute bottom-7 left-3 flex items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[12px] tracking-[0.12em] text-ash">
            GRID {step} m · FRAME ±{extentM} m
          </span>
          <div className="flex items-center gap-2">
            <div className="relative h-[7px] w-[120px] border-x border-b border-muted-silver" />
            <span className="font-mono text-[12px] tabular-nums text-muted-silver">
              {Math.round(extentM / 2)} m
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

function Legend() {
  return (
    <div className="pointer-events-none absolute bottom-7 right-3 flex flex-col items-end gap-[5px] font-mono text-[12px] tracking-[0.1em] text-ash">
      <span className="flex items-center gap-2">
        <span className="block h-[9px] w-[9px] rotate-45 border border-launch-amber" />
        OBJECTIVE
      </span>
      <span className="flex items-center gap-2">
        <span className="block h-0 w-[16px] border-t border-dashed border-orbital-blue" />
        ASSIGNED · EXECUTING
      </span>
      <span className="flex items-center gap-2">
        <span className="block h-0 w-[16px] border-t border-signal-green" />
        ARRIVAL VERIFIED
      </span>
      <span className="flex items-center gap-2">
        <span className="block h-0 w-[16px] border-t border-orbital-blue/40" />
        OBSERVED TRACK
      </span>
    </div>
  );
}
