"use client";

/**
 * MapOverlay — objectives, physical executors, and the relationship between
 * them, drawn over the satellite ground.
 *
 * The hierarchy this draws is the architecture, in order:
 *
 *   1. objective            — what the fleet was asked to resolve
 *   2. assignment           — the ExecutionGroup SwarmOS composed around it
 *   3. physical executors   — the machines holding each role
 *   4. observed track       — where they actually flew
 *
 * Two line treatments are deliberately not interchangeable:
 *
 *   assignment — a logical relationship SwarmOS created. Fine dotted, low
 *                contrast, drawn straight, drawn on once when the group forms.
 *                It is not a path anything flies.
 *   track      — geography. Solid, continuous, and made only of positions the
 *                agent actually reported.
 *
 * One further device is load-bearing rather than decorative. SwarmOS separates
 * the roles inside a cooperative objective by *altitude*, not by ground station:
 * `_cooperative_verify_plans` builds every child VERIFY against the same `geo`
 * at `base_altitude_m + altitude_step_m * idx`. Three observers over one target
 * are therefore at one point on a plan view, stacked vertically. So an airborne
 * executor is drawn lifted off its ground position in proportion to its reported
 * `altitude_agl_m`, with a hollow ground mark and a fine leader connecting the
 * two. The true position is always the mark at the bottom of the leader; the
 * lift is what makes the role ladder — the composition itself — visible.
 *
 * Executors that are simply parked are not drawn one by one. Every aircraft in
 * this deployment launches from one physical pad — every scenario YAML gives
 * `n_drones` a single shared `dock_offset_m` — so a fleet at rest is thirty
 * darts stacked on the same pixel, which states nothing and hides everything
 * behind it. Instead the dock itself is a mark, carrying the count the server
 * reported docked on it. An executor leaves the dock mark and becomes its own
 * glyph the moment it matters: when SwarmOS puts it on the focused objective,
 * when the operator selects it, when it drops out, or when it is airborne. The
 * count is a count of `UnitState` frames, never an assertion about hardware.
 *
 * A fourth mark sits on top of an executor holding station with an active
 * bounded-response channel — the light on, the speaker playing. This is the
 * one place on the map that shows physical execution rather than composition:
 * a small badge, coloured by the same verified/simulated tier the panels use,
 * appears the instant a real `PayloadEvent` frame says the channel is active
 * and disappears the instant one says it stopped. It never infers action from
 * `ON_STATION` alone — an executor can hold station with nothing switched on.
 *
 * Geometry is SVG; captions are HTML. Small operational type is the thing this
 * surface is mostly made of, and HTML is where the type system actually lives.
 */

import { useMemo } from "react";

import type { CapacityRow, CompositionSlot, ObjectiveAuthority } from "@/lib/authority";
import { roleLabel } from "@/lib/authority";
import type { PayloadChannel } from "@/lib/mission-story";
import type { ScreenPoint } from "@/lib/opsmap";

import type { ConsoleProjection } from "./projection";

// Marker geometry, in screen pixels. These are glyph dimensions, not distances:
// nothing here claims a radius on the ground.
const OBJECTIVE_RING = 15;
const OBJECTIVE_TICK = 6;
const EXECUTOR_R = 7.5;
/** Half-width of the dock mark's outer pad, in screen pixels. */
const DOCK_R = 9.5;
/** Gap left at both ends of an assignment tether so it never touches a glyph. */
const TETHER_INSET = 20;
/**
 * Screen lift per metre of reported altitude AGL.
 *
 * Chosen against the ladder SwarmOS actually builds: 40 / 55 / 70 m for a
 * three-role cooperative objective separates into 44 / 60 / 77 px, which clears
 * the glyph and its caption at every viewport this surface is recorded at. The
 * lift is capped so a high transit cannot push a glyph out of frame or across a
 * panel.
 */
const ALT_PX_PER_M = 1.1;
const ALT_LIFT_MAX_PX = 124;

/** Screen position of an executor: its ground point, lifted by its altitude. */
function liftedPoint(ground: ScreenPoint, altitudeAglM: number): ScreenPoint {
  const lift = Math.min(ALT_LIFT_MAX_PX, Math.max(0, altitudeAglM) * ALT_PX_PER_M);
  return { x: ground.x, y: ground.y - lift };
}

/**
 * A dock, and the two counts a reader needs from it: how many executors report
 * this dock as theirs at all, and how many of them are on it right now. Both
 * are counts of `UnitState` frames — the numerator falls as SwarmOS commits
 * capacity and rises again as executors return.
 */
export type DockMark = {
  dockId: string;
  /** Reporting DOCKED on this pad right now. */
  docked: number;
  /** Reporting this pad as theirs, in any state. */
  total: number;
  point: ScreenPoint;
};

export type ExecutorMark = {
  row: CapacityRow;
  /** True projected position on the ground. */
  ground: ScreenPoint;
  /** Where the glyph is drawn — `ground` lifted by reported altitude. */
  point: ScreenPoint;
  slot: CompositionSlot | null;
  /** Serving the focused objective. */
  focused: boolean;
};

function toneFor(row: CapacityRow, focused: boolean): string {
  if (row.commitment === "UNAVAILABLE") return "#FFB45C";
  if (focused) return "#7BE7FF";
  if (row.commitment === "ASSIGNED" || row.commitment === "COMMITTED") return "#A8AFB8";
  return "#7F8A98";
}

/**
 * The altitude leader.
 *
 * States the true ground position and how far the glyph above it has been
 * lifted. Drawn only when there is something to state — a docked executor sits
 * on its own mark and gets neither.
 */
function AltitudeLeader({
  ground,
  point,
  tone,
}: {
  ground: ScreenPoint;
  point: ScreenPoint;
  tone: string;
}) {
  if (ground.y - point.y < 6) return null;
  return (
    <g opacity={0.5}>
      <line
        x1={ground.x}
        y1={ground.y - 2}
        x2={point.x}
        y2={point.y + 9}
        stroke={tone}
        strokeWidth={1}
        strokeDasharray="1 3"
      />
      <circle cx={ground.x} cy={ground.y} r={2.2} fill="none" stroke={tone} strokeWidth={1} />
    </g>
  );
}

/**
 * The action badge.
 *
 * Two small marks at most — one per bounded-response channel — sitting above
 * and clear of the executor's own caption, so the two never fight for the same
 * pixels. Steady, not pulsing: CLAUDE.md's motion rule is explicit that
 * nothing on this surface repeats forever, and a channel that is on stays on
 * without needing to keep announcing it.
 */
function ActionBadges({
  point,
  channels,
}: {
  point: ScreenPoint;
  channels: PayloadChannel[];
}) {
  if (channels.length === 0) return null;
  return (
    <g>
      {channels.map((channel, i) => {
        const tone = channel.tier === "simulated" ? "#FFB45C" : "#B8FF66";
        const cx = point.x - 11 + i * 9;
        const cy = point.y - 13;
        return (
          <g key={channel.channel}>
            <circle cx={cx} cy={cy} r={4} fill="none" stroke={tone} strokeWidth={1.1} />
            <circle cx={cx} cy={cy} r={1.6} fill={tone} />
          </g>
        );
      })}
    </g>
  );
}

/**
 * The dock.
 *
 * A pad, not a vehicle and not a place of interest: a square outline with a
 * charged core, which reads as infrastructure at every size the recording uses
 * and cannot be confused with the objective's survey ring or an executor's
 * dart. It never pulses and it never changes colour with fleet state — the dock
 * is the one thing on this map that is not an event.
 */
function DockGlyph({ point, tone }: { point: ScreenPoint; tone: string }) {
  return (
    <g transform={`translate(${point.x} ${point.y})`}>
      <rect
        x={-DOCK_R}
        y={-DOCK_R}
        width={DOCK_R * 2}
        height={DOCK_R * 2}
        rx={2.5}
        fill="none"
        stroke={tone}
        strokeWidth={1.2}
        opacity={0.75}
      />
      <rect
        x={-DOCK_R + 4}
        y={-DOCK_R + 4}
        width={(DOCK_R - 4) * 2}
        height={(DOCK_R - 4) * 2}
        rx={1.2}
        fill={tone}
        opacity={0.5}
      />
    </g>
  );
}

/**
 * How much smaller an executor the surface is not naming is drawn.
 *
 * Size is rank. Thirty aircraft on one objective are presence — the fleet is
 * there, it is pointed somewhere, and that is all the map has to say about it.
 * The three or four the composition names are what the viewer is being asked to
 * follow, and they stay full size so they read first.
 *
 * It buys clearance as well as hierarchy: a smaller mark needs roughly half the
 * pixels between it and its neighbour before the two touch, which is what lets
 * a thirty-ship line fit one screen with air left in it.
 */
const FLEET_GLYPH_SCALE = 0.62;

/** Directional dart. Heading is the server's `heading_deg`; 0° is north. */
function ExecutorGlyph({
  point,
  headingDeg,
  tone,
  state,
  scale = 1,
}: {
  point: ScreenPoint;
  headingDeg: number;
  tone: string;
  state: "assigned" | "spare" | "unavailable";
  scale?: number;
}) {
  const filled = state === "assigned";
  return (
    <g
      transform={`translate(${point.x} ${point.y}) rotate(${headingDeg}) scale(${scale})`}
    >
      <path
        d="M0 -8.5 L5.6 6.5 L0 3.4 L-5.6 6.5 Z"
        fill={filled ? tone : "none"}
        stroke={tone}
        // Compensated so a scaled-down mark keeps the same hairline weight as
        // everything else on the surface rather than thinning out.
        strokeWidth={1.4 / scale}
        strokeLinejoin="round"
        opacity={state === "spare" ? 0.7 : 1}
      />
      {state === "unavailable" ? (
        // A disconnected mark, not an alarm: the dart is struck through rather
        // than made to flash.
        <path
          d="M-8 -8 L8 8"
          stroke={tone}
          strokeWidth={1.4 / scale}
          strokeLinecap="round"
          transform={`rotate(${-headingDeg})`}
        />
      ) : null}
    </g>
  );
}

/** Survey mark. Distinct from a location pin at every size. */
function ObjectiveGlyph({
  point,
  tone,
  focused,
  appearKey,
}: {
  point: ScreenPoint;
  tone: string;
  focused: boolean;
  appearKey: string;
}) {
  return (
    <g transform={`translate(${point.x} ${point.y})`}>
      {focused ? (
        // One restrained pulse when the objective arrives, then nothing. A mark
        // that blinks forever stops meaning anything.
        <circle
          key={appearKey}
          r={OBJECTIVE_RING}
          fill="none"
          stroke={tone}
          strokeWidth={1}
          className="objective-appear"
        />
      ) : null}
      <circle
        r={OBJECTIVE_RING}
        fill="none"
        stroke={tone}
        strokeWidth={focused ? 1.3 : 1}
        opacity={focused ? 0.9 : 0.5}
      />
      <path
        d={`M0 ${-OBJECTIVE_RING - OBJECTIVE_TICK} V${-OBJECTIVE_RING + 3}
            M0 ${OBJECTIVE_RING - 3} V${OBJECTIVE_RING + OBJECTIVE_TICK}
            M${-OBJECTIVE_RING - OBJECTIVE_TICK} 0 H${-OBJECTIVE_RING + 3}
            M${OBJECTIVE_RING - 3} 0 H${OBJECTIVE_RING + OBJECTIVE_TICK}`}
        stroke={tone}
        strokeWidth={focused ? 1.3 : 1}
        strokeLinecap="round"
        opacity={focused ? 0.95 : 0.5}
      />
      <circle r={3} fill={tone} opacity={focused ? 1 : 0.6} />
    </g>
  );
}

/**
 * Assignment tether — a relationship, drawn as one.
 *
 * Inset at both ends, dotted at a wide pitch, and held well below the contrast
 * of anything geographic. It draws on once when SwarmOS composes the role, then
 * settles; it never accumulates into permanent spaghetti because only the
 * focused objective draws them.
 */
function Tether({
  from,
  to,
  tone,
  drawKey,
  fading,
}: {
  from: ScreenPoint;
  to: ScreenPoint;
  tone: string;
  drawKey: string;
  fading: boolean;
}) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy);
  if (length < TETHER_INSET * 2 + 6) return null;
  const ux = dx / length;
  const uy = dy / length;
  const a = { x: from.x + ux * TETHER_INSET, y: from.y + uy * TETHER_INSET };
  const b = { x: to.x - ux * TETHER_INSET, y: to.y - uy * TETHER_INSET };

  return (
    <line
      key={drawKey}
      x1={a.x}
      y1={a.y}
      x2={b.x}
      y2={b.y}
      stroke={tone}
      strokeWidth={1}
      strokeDasharray="1.5 5"
      strokeLinecap="round"
      opacity={fading ? 0.14 : 0.42}
      className="tether-draw"
      style={{ transition: "opacity 420ms cubic-bezier(0.2, 0.7, 0.1, 1)" }}
    />
  );
}

/** Observed track — only positions the agent actually reported. */
function Track({
  points,
  tone,
  focused,
}: {
  points: ScreenPoint[];
  tone: string;
  focused: boolean;
}) {
  if (points.length < 2) return null;
  const d = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  return (
    <path
      d={d}
      fill="none"
      stroke={tone}
      strokeWidth={focused ? 1.6 : 1.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      opacity={focused ? 0.62 : 0.3}
    />
  );
}

// ── Captions ─────────────────────────────────────────────────────────────────

/**
 * Caption placement.
 *
 * Four SITL aircraft launch from within metres of each other, which puts their
 * glyphs — and therefore their captions — on top of one another. Captions are
 * pushed down in whole block heights until they stop colliding, in a stable
 * order, so two frames of a recording never disagree about where a label sits.
 */
const CAPTION_W = 124;
/** One line of id. Most executors never need more than this on the map. */
const CAPTION_H = 17;
/** Two lines — an id plus the one thing worth saying about this executor. */
const CAPTION_H_WIDE = 31;
const CAPTION_DX = 12;
const CAPTION_DY = -6;
/** Clear air between two caption blocks. Three pixels survives no encoder. */
const CAPTION_GAP = 9;
/** An objective caption is three tiers tall. So is a dock caption. */
const OBJECTIVE_CAPTION_H = 46;
const DOCK_CAPTION_H = 46;

/** Hold a fixed caption block inside the band the panels leave clear. */
function clampCaption(y: number, h: number, safe: { top: number; bottom: number }): number {
  return Math.max(safe.top, Math.min(y, safe.bottom - h));
}

/**
 * Whether this executor gets a caption at all.
 *
 * The design brief's own rule is to prioritise the currently relevant
 * executors, and with four aircraft that rule cost nothing to ignore. With a
 * few dozen it is the difference between a map and a wall of identifiers: a
 * deployed fleet is presence, not a roster, and the panels carry every id on
 * screen anyway. So a caption is earned by being one of the executors the
 * surface names — the same set the composition panel lists — by having dropped
 * out, or by being the one the operator selected.
 *
 * It also keeps the collision solver's input small: it is quadratic in the
 * number of captions, not in the number of executors.
 */
function captionVisible(
  mark: ExecutorMark,
  selected: boolean,
  namedAgents: ReadonlySet<string>
): boolean {
  return (
    namedAgents.has(mark.row.agentId) ||
    selected ||
    mark.row.commitment === "UNAVAILABLE"
  );
}

/**
 * What, if anything, goes under the id.
 *
 * The map is not the roster — the authority and capacity panels carry every
 * role, every state and every reading, and they are always on screen. So the
 * map says the second line only where it changes what the viewer should do:
 * an executor that has dropped out, and the one being inspected.
 */
function captionDetail(
  mark: ExecutorMark,
  selected: boolean
): string | null {
  if (mark.row.commitment === "UNAVAILABLE") return "UNAVAILABLE";
  if (!selected) return null;
  if (mark.slot?.roleIsAssigned) return roleLabel(mark.slot.role);
  if (mark.row.phase) return mark.row.phase.replaceAll("_", " ");
  return mark.row.fsmState.replaceAll("_", " ");
}

type CaptionBlock = { x: number; y: number; h: number };

/**
 * Blocks are anchored top-left, so they are compared as intervals.
 *
 * The older test measured the gap between two *tops* against half the sum of
 * the heights, which is only correct when the blocks are the same height: a
 * 46 px objective or dock caption sitting 41 px above a 17 px executor caption
 * read as clear and overlapped it.
 */
function overlaps(placed: readonly CaptionBlock[], x: number, y: number, h: number): boolean {
  return placed.some(
    (other) =>
      Math.abs(other.x - x) < CAPTION_W &&
      y < other.y + other.h + CAPTION_GAP &&
      other.y < y + h + CAPTION_GAP
  );
}

/**
 * Where a caption block ends up, given what is already on the map.
 *
 * Pushing down is the preferred direction, but it is not unbounded: a whole
 * group launching from one pad stacks four blocks off the bottom of the clear
 * area and onto the panels floating there. When downward runs out, the same
 * search runs upward from the mark, where there is room. The result is held
 * inside the band the panels leave clear either way — type painted over a panel
 * is the one defect a recording cannot recover from.
 */
export function solveCaptionY(
  placed: readonly CaptionBlock[],
  x: number,
  start: number,
  h: number,
  safe: { top: number; bottom: number }
): number {
  let y = clampCaption(start, h, safe);
  const from = y;
  while (overlaps(placed, x, y, h) && y + h <= safe.bottom) y += h + CAPTION_GAP;
  if (overlaps(placed, x, y, h) || y + h > safe.bottom) {
    y = from;
    while (overlaps(placed, x, y, h) && y - h >= safe.top) y -= h + CAPTION_GAP;
  }
  return clampCaption(y, h, safe);
}

function placeCaptions(
  marks: ExecutorMark[],
  /** Blocks already on the map — objective captions, then dock captions. */
  reserved: readonly CaptionBlock[],
  heights: ReadonlyMap<string, number>,
  /** Vertical band the map may write in — the viewport minus the panels. */
  safe: { top: number; bottom: number }
): Map<string, ScreenPoint> {
  const placed: CaptionBlock[] = [...reserved];
  const out = new Map<string, ScreenPoint>();

  for (const mark of marks) {
    const h = heights.get(mark.row.agentId) ?? CAPTION_H;
    const x = mark.point.x + CAPTION_DX;
    const y = solveCaptionY(placed, x, mark.point.y + CAPTION_DY, h, safe);
    placed.push({ x, y, h });
    out.set(mark.row.agentId, { x, y });
  }
  return out;
}

export function MapOverlay({
  projection,
  objectives,
  capacity,
  focusKey,
  selectedExecutor,
  /** Bounded-response channels for the focused objective, latest frame each. */
  channels = [],
  namedAgents,
  safeArea,
  onSelectObjective,
  onSelectExecutor,
}: {
  projection: ConsoleProjection;
  objectives: ObjectiveAuthority[];
  capacity: CapacityRow[];
  focusKey: string | null;
  selectedExecutor: string | null;
  channels?: PayloadChannel[];
  /** Executors the surface names — the composition rows, not the whole fleet. */
  namedAgents: ReadonlySet<string>;
  /** Vertical band the operating surfaces leave clear, in viewport pixels. */
  safeArea: { top: number; bottom: number };
  onSelectObjective: (key: string) => void;
  onSelectExecutor: (agentId: string | null) => void;
}) {
  const focused = objectives.find((o) => o.key === focusKey) ?? null;

  // Only a channel a server frame actually reported as active earns a badge —
  // "LIGHT ON" / "SPEAKER ACTIVE" specifically, never inferred from station.
  const activeByAgent = useMemo(() => {
    const out = new Map<string, PayloadChannel[]>();
    for (const channel of channels) {
      if (!channel.agentId) continue;
      if (channel.state !== "LIGHT ON" && channel.state !== "SPEAKER ACTIVE") continue;
      const bucket = out.get(channel.agentId);
      if (bucket) bucket.push(channel);
      else out.set(channel.agentId, [channel]);
    }
    return out;
  }, [channels]);

  const { marks, docks } = useMemo<{ marks: ExecutorMark[]; docks: DockMark[] }>(() => {
    const slotByAgent = new Map<string, CompositionSlot>();
    for (const slot of focused?.slots ?? []) {
      if (slot.agentId) slotByAgent.set(slot.agentId, slot);
    }

    const live = capacity.filter(
      (row) => Number.isFinite(row.geo.lat) && row.geo.lat !== 0
    );

    // How much capacity each pad holds, and how much of it is home. Counted
    // over every executor that names the dock, including the ones drawn as
    // their own glyph — being on the focused objective does not move an
    // aircraft off the pad it is still sitting on.
    const dockTotal = new Map<string, number>();
    const dockDocked = new Map<string, number>();
    for (const row of live) {
      if (!row.dockId) continue;
      dockTotal.set(row.dockId, (dockTotal.get(row.dockId) ?? 0) + 1);
      if (row.fsmState === "DOCKED") {
        dockDocked.set(row.dockId, (dockDocked.get(row.dockId) ?? 0) + 1);
      }
    }

    // An executor draws itself when it is part of what is happening: on the
    // focused objective, selected, dropped out, or off the pad. Everything else
    // is capacity sitting on a dock, and the dock draws it.
    const parked = new Map<string, CapacityRow[]>();
    const own: CapacityRow[] = [];
    for (const row of live) {
      const involved =
        namedAgents.has(row.agentId) ||
        selectedExecutor === row.agentId ||
        row.commitment === "UNAVAILABLE" ||
        row.fsmState !== "DOCKED";
      if (involved || !row.dockId) {
        own.push(row);
        continue;
      }
      const bucket = parked.get(row.dockId);
      if (bucket) bucket.push(row);
      else parked.set(row.dockId, [row]);
    }

    // Any executor left on the pad is drawn as the pad. Even one is worth
    // stating that way: `01 / 34 DOCKED` says the reserve is down to its last
    // machine, which an anonymous dart in the corner does not.
    const docksOut: DockMark[] = [];
    for (const [dockId, rows] of parked) {
      if (rows.length === 0) continue;
      docksOut.push({
        dockId,
        docked: dockDocked.get(dockId) ?? rows.length,
        total: dockTotal.get(dockId) ?? rows.length,
        point: projection.project(rows[0].geo),
      });
    }

    const marksOut = own
      .map((row) => {
        const ground = projection.project(row.geo);
        return {
          row,
          ground,
          point: liftedPoint(ground, row.altitudeAglM),
          slot: slotByAgent.get(row.agentId) ?? null,
          focused: slotByAgent.has(row.agentId),
        };
      })
      // Assigned executors are drawn last so they sit above spare capacity when
      // two aircraft overlap.
      .sort((a, b) => Number(a.focused) - Number(b.focused));

    return { marks: marksOut, docks: docksOut };
  }, [capacity, focused, projection, selectedExecutor, namedAgents]);

  const objectiveCaptions = useMemo(
    () =>
      objectives
        .filter((objective) => objective.geo)
        .map((objective) => {
          const point = projection.project(
            objective.geo as { lat: number; lon: number }
          );
          return {
            key: objective.key,
            at: {
              x: point.x + OBJECTIVE_RING + 12,
              // The caption reaches past its glyph, and the camera composes the
              // glyph itself into the clear area — so the overhang is the part
              // that can still land on the status bar, the narration band or
              // the panels along the bottom. Held inside the band.
              y: clampCaption(point.y - 34, OBJECTIVE_CAPTION_H, safeArea),
            },
          };
        }),
    [objectives, projection, safeArea]
  );

  const captioned = useMemo(
    () =>
      marks.filter((mark) =>
        captionVisible(mark, selectedExecutor === mark.row.agentId, namedAgents)
      ),
    [marks, selectedExecutor, namedAgents]
  );

  const captionHeights = useMemo(() => {
    const out = new Map<string, number>();
    for (const mark of captioned) {
      out.set(
        mark.row.agentId,
        captionDetail(mark, selectedExecutor === mark.row.agentId) ? CAPTION_H_WIDE : CAPTION_H
      );
    }
    return out;
  }, [captioned, selectedExecutor]);

  // An objective is the top of the hierarchy and keeps the position its glyph
  // asks for. A dock is infrastructure and yields to it — with the fleet home
  // and an objective resolved over the same ground, the two captions want the
  // same pixels, and the dock is the one that can move.
  const objectiveBlocks = useMemo(
    () => objectiveCaptions.map((c) => ({ ...c.at, h: OBJECTIVE_CAPTION_H })),
    [objectiveCaptions]
  );

  const dockCaptions = useMemo(() => {
    const placed: { x: number; y: number; h: number }[] = [...objectiveBlocks];
    return docks.map((dock) => {
      const x = dock.point.x + DOCK_R + 12;
      const y = solveCaptionY(placed, x, dock.point.y - 30, DOCK_CAPTION_H, safeArea);
      placed.push({ x, y, h: DOCK_CAPTION_H });
      return { dock, at: { x, y } };
    });
  }, [docks, objectiveBlocks, safeArea]);

  const captions = useMemo(
    () =>
      placeCaptions(
        captioned,
        [
          ...objectiveBlocks,
          ...dockCaptions.map((c) => ({ ...c.at, h: DOCK_CAPTION_H })),
        ],
        captionHeights,
        safeArea
      ),
    [captioned, objectiveBlocks, dockCaptions, captionHeights, safeArea]
  );

  return (
    <>
      <svg
        className="pointer-events-none absolute inset-0 z-10 h-full w-full"
        aria-hidden="true"
      >
        {/* 4 — observed tracks, furthest back. */}
        {objectives.map((objective) =>
          objective.routes.map((route) => (
            <Track
              key={`${objective.key}:${route.missionId}`}
              points={route.points.map((p) => projection.project(p))}
              tone={objective.key === focusKey ? "#7BE7FF" : "#7F8A98"}
              focused={objective.key === focusKey}
            />
          ))
        )}

        {/* 2 — assignment. Only the focused objective draws its group, so the
            map never accumulates every relationship the session ever held. */}
        {focused?.geo
          ? focused.slots.map((slot) => {
              const mark = marks.find((m) => m.row.agentId === slot.agentId);
              if (!mark || !focused.geo) return null;
              const failing = slot.memberState === "FAILED" || slot.adapting;
              return (
                <Tether
                  key={`${focused.key}:${slot.role}:${slot.agentId}`}
                  drawKey={`${focused.key}:${slot.role}:${slot.agentId}`}
                  from={mark.point}
                  to={projection.project(focused.geo)}
                  tone={failing ? "#FFB45C" : "#7BE7FF"}
                  fading={failing}
                />
              );
            })
          : null}

        {/* 0 — docks. Furthest down the hierarchy: infrastructure the fleet
            launches from, drawn under everything that is happening. */}
        {docks.map((dock) => (
          <DockGlyph key={dock.dockId} point={dock.point} tone="#A8AFB8" />
        ))}

        {/* 1 — objectives. */}
        {objectives.map((objective) =>
          objective.geo ? (
            <ObjectiveGlyph
              key={objective.key}
              appearKey={objective.key}
              point={projection.project(objective.geo)}
              tone={objective.key === focusKey ? "#7BE7FF" : "#A8AFB8"}
              focused={objective.key === focusKey}
            />
          ) : null
        )}

        {/* 3 — physical executors, each above its own ground mark. */}
        {marks.map((mark) => (
          /* Published so a test — and a recording check — can assert where an
             executor was drawn without reaching into React. */
          <g key={mark.row.agentId} data-testid={`executor-mark-${mark.row.agentId}`}>
            {/* The leader states a true ground position under a lifted glyph.
                It earns its ink where the lift is doing work — the role ladder
                over one objective, or an executor being inspected. Drawn for
                every aircraft in a deployed formation it is thirty dotted
                lines saying the same thing. */}
            {mark.focused || selectedExecutor === mark.row.agentId ? (
              <AltitudeLeader
                ground={mark.ground}
                point={mark.point}
                tone={toneFor(mark.row, mark.focused)}
              />
            ) : null}
            {/* 4 — what it is doing, when it is doing something. */}
            <ActionBadges
              point={mark.point}
              channels={activeByAgent.get(mark.row.agentId) ?? []}
            />
            {selectedExecutor === mark.row.agentId ? (
              <circle
                cx={mark.point.x}
                cy={mark.point.y}
                r={EXECUTOR_R + 5}
                fill="none"
                stroke="#EEF0F3"
                strokeWidth={1}
                opacity={0.75}
              />
            ) : null}
            <ExecutorGlyph
              point={mark.point}
              headingDeg={mark.row.headingDeg}
              tone={toneFor(mark.row, mark.focused)}
              scale={
                namedAgents.has(mark.row.agentId) ||
                selectedExecutor === mark.row.agentId ||
                mark.row.commitment === "UNAVAILABLE"
                  ? 1
                  : FLEET_GLYPH_SCALE
              }
              state={
                mark.row.commitment === "UNAVAILABLE"
                  ? "unavailable"
                  : mark.row.commitment === "SPARE"
                    ? "spare"
                    : "assigned"
              }
            />
          </g>
        ))}
      </svg>

      {/* Objective captions. */}
      {objectiveCaptions.map(({ key, at }) => {
        const objective = objectives.find((o) => o.key === key);
        if (!objective) return null;
        const isFocus = objective.key === focusKey;
        return (
          <button
            key={objective.key}
            type="button"
            onClick={() => onSelectObjective(objective.key)}
            data-testid={`objective-caption-${objective.key}`}
            className="absolute z-20 text-left"
            style={{
              left: at.x,
              top: at.y,
              transition: "opacity 300ms cubic-bezier(0.2, 0.7, 0.1, 1)",
              opacity: isFocus ? 1 : 0.62,
            }}
          >
            <div
              className={`font-grotesk text-[11px] font-medium uppercase leading-none tracking-[0.2em] ${
                isFocus ? "text-orbital-blue" : "text-muted-silver"
              }`}
            >
              {objective.kind}
            </div>
            <div className="mt-[5px] font-mono text-[13px] leading-none tracking-[0.08em] text-platinum">
              {objective.label}
            </div>
            <div className="mt-[5px] font-mono text-[9px] uppercase leading-none tracking-[0.18em] text-ash">
              {isFocus ? "OWNED · SWARMOS" : objective.state}
            </div>
          </button>
        );
      })}

      {/* Dock captions. The numerator is the number of `UnitState` frames
          reporting DOCKED on this pad right now, the denominator every executor
          that names it — so the count falls as SwarmOS commits capacity and
          rises again as executors return. */}
      {dockCaptions.map(({ dock, at }) => (
        <div
          key={dock.dockId}
          data-testid={`dock-caption-${dock.dockId}`}
          className="pointer-events-none absolute z-20 text-left"
          style={{ left: at.x, top: at.y }}
        >
          <div className="font-grotesk text-[11px] font-medium uppercase leading-none tracking-[0.2em] text-muted-silver">
            dock
          </div>
          <div className="mt-[5px] font-mono text-[13px] leading-none tracking-[0.08em] text-platinum">
            <span data-testid={`dock-count-${dock.dockId}`}>
              {String(dock.docked).padStart(2, "0")} / {String(dock.total).padStart(2, "0")}
            </span>{" "}
            DOCKED
          </div>
          <div className="mt-[5px] font-mono text-[9px] uppercase leading-none tracking-[0.18em] text-ash">
            {dock.dockId}
          </div>
        </div>
      ))}

      {/* Executor captions. Prioritised: only the executors on the focused
          objective, the one selected, and anything that has dropped out are
          named. Everything else keeps its glyph and loses its label. */}
      {captioned.map((mark) => {
        const at = captions.get(mark.row.agentId);
        if (!at) return null;
        const unavailable = mark.row.commitment === "UNAVAILABLE";
        const selected = selectedExecutor === mark.row.agentId;
        const secondary = captionDetail(mark, selected);
        return (
          <button
            key={mark.row.agentId}
            type="button"
            onClick={() =>
              onSelectExecutor(selectedExecutor === mark.row.agentId ? null : mark.row.agentId)
            }
            data-testid={`executor-caption-${mark.row.agentId}`}
            className="absolute z-20 text-left"
            style={{
              left: at.x,
              top: at.y,
              transition: "opacity 300ms cubic-bezier(0.2, 0.7, 0.1, 1)",
              opacity: mark.focused || unavailable ? 1 : 0.66,
            }}
          >
            <div
              className={`font-mono text-[11px] leading-none tracking-[0.1em] ${
                unavailable
                  ? "text-launch-amber"
                  : mark.focused
                    ? "text-platinum"
                    : "text-muted-silver"
              }`}
            >
              {mark.row.agentId}
            </div>
            {secondary ? (
              <div
                className={`mt-[4px] font-mono text-[9px] uppercase leading-none tracking-[0.16em] ${
                  unavailable ? "text-launch-amber/80" : mark.focused ? "text-orbital-blue" : "text-ash"
                }`}
              >
                {secondary}
              </div>
            ) : null}
          </button>
        );
      })}
    </>
  );
}
