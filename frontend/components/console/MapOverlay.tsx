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
 * Geometry is SVG; captions are HTML. Small operational type is the thing this
 * surface is mostly made of, and HTML is where the type system actually lives.
 */

import { useMemo } from "react";

import type { CapacityRow, CompositionSlot, ObjectiveAuthority } from "@/lib/authority";
import { roleLabel } from "@/lib/authority";
import type { ScreenPoint } from "@/lib/opsmap";

import type { ConsoleProjection } from "./projection";

// Marker geometry, in screen pixels. These are glyph dimensions, not distances:
// nothing here claims a radius on the ground.
const OBJECTIVE_RING = 15;
const OBJECTIVE_TICK = 6;
const EXECUTOR_R = 7.5;
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

/** Directional dart. Heading is the server's `heading_deg`; 0° is north. */
function ExecutorGlyph({
  point,
  headingDeg,
  tone,
  state,
}: {
  point: ScreenPoint;
  headingDeg: number;
  tone: string;
  state: "assigned" | "spare" | "unavailable";
}) {
  const filled = state === "assigned";
  return (
    <g transform={`translate(${point.x} ${point.y}) rotate(${headingDeg})`}>
      <path
        d="M0 -8.5 L5.6 6.5 L0 3.4 L-5.6 6.5 Z"
        fill={filled ? tone : "none"}
        stroke={tone}
        strokeWidth={1.4}
        strokeLinejoin="round"
        opacity={state === "spare" ? 0.7 : 1}
      />
      {state === "unavailable" ? (
        // A disconnected mark, not an alarm: the dart is struck through rather
        // than made to flash.
        <path
          d="M-8 -8 L8 8"
          stroke={tone}
          strokeWidth={1.4}
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
/** An objective caption is three tiers tall. */
const OBJECTIVE_CAPTION_H = 46;

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

function placeCaptions(
  marks: ExecutorMark[],
  reserved: readonly ScreenPoint[],
  heights: ReadonlyMap<string, number>
): Map<string, ScreenPoint> {
  // Objective captions are seeded as already-placed blocks rather than solved
  // alongside the executors: an objective is the top of the hierarchy, so it
  // keeps its position and everything else moves around it.
  const placed: { x: number; y: number; h: number }[] = reserved.map((point) => ({
    ...point,
    h: OBJECTIVE_CAPTION_H,
  }));
  const out = new Map<string, ScreenPoint>();
  for (const mark of marks) {
    const h = heights.get(mark.row.agentId) ?? CAPTION_H;
    let y = mark.point.y + CAPTION_DY;
    const x = mark.point.x + CAPTION_DX;
    while (
      placed.some(
        (other) =>
          Math.abs(other.x - x) < CAPTION_W &&
          Math.abs(other.y - y) < (other.h + h) / 2 + CAPTION_GAP
      )
    ) {
      y += h + CAPTION_GAP;
    }
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
  onSelectObjective,
  onSelectExecutor,
}: {
  projection: ConsoleProjection;
  objectives: ObjectiveAuthority[];
  capacity: CapacityRow[];
  focusKey: string | null;
  selectedExecutor: string | null;
  onSelectObjective: (key: string) => void;
  onSelectExecutor: (agentId: string | null) => void;
}) {
  const focused = objectives.find((o) => o.key === focusKey) ?? null;

  const marks = useMemo<ExecutorMark[]>(() => {
    const slotByAgent = new Map<string, CompositionSlot>();
    for (const slot of focused?.slots ?? []) {
      if (slot.agentId) slotByAgent.set(slot.agentId, slot);
    }
    return capacity
      .filter((row) => Number.isFinite(row.geo.lat) && row.geo.lat !== 0)
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
  }, [capacity, focused, projection]);

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
            at: { x: point.x + OBJECTIVE_RING + 12, y: point.y - 34 },
          };
        }),
    [objectives, projection]
  );

  const captionHeights = useMemo(() => {
    const out = new Map<string, number>();
    for (const mark of marks) {
      out.set(
        mark.row.agentId,
        captionDetail(mark, selectedExecutor === mark.row.agentId) ? CAPTION_H_WIDE : CAPTION_H
      );
    }
    return out;
  }, [marks, selectedExecutor]);

  const captions = useMemo(
    () => placeCaptions(marks, objectiveCaptions.map((c) => c.at), captionHeights),
    [marks, objectiveCaptions, captionHeights]
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
          <g key={mark.row.agentId}>
            <AltitudeLeader
              ground={mark.ground}
              point={mark.point}
              tone={toneFor(mark.row, mark.focused)}
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

      {/* Executor captions. Prioritised: spare capacity keeps its id but drops
          the second line, so the map does not fill with text. */}
      {marks.map((mark) => {
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
