"use client";

/**
 * MissionTimeline — one swimlane per mission, on a shared wall clock.
 *
 * This is the concurrency proof. When the second objective is allocated to a
 * different agent while the first mission is still running, two lanes overlap
 * in time, each with its own owner and mission id. Nothing else on the screen
 * shows that as directly.
 *
 * Ticks sit at the server timestamp of the frame that produced them. Execution
 * steps run above the lane baseline; bounded physical response runs below it.
 */

import { useEffect, useRef, useState } from "react";

import type { Timeline, TimelineLane, TimelineTick } from "@/lib/mission-story";
import { shortId } from "@/lib/mission-story";

import { Panel } from "./primitives";

const MIN_WINDOW_MS = 30_000;
// Visual headroom only. Event timestamps stay exact; the axis simply extends
// past the newest frame so its label never clips against the viewport edge.
const RIGHT_PAD_MS = 3_500;
const GUTTER = 210;

function axisStepS(spanS: number): number {
  if (spanS <= 60) return 10;
  if (spanS <= 180) return 30;
  if (spanS <= 600) return 60;
  return 300;
}

// Label metrics for stagger arithmetic: 11px mono at 0.6em advance plus 0.1em
// tracking, and the marker square with its gap.
const LABEL_CHAR_PX = 11 * 0.7;
const LABEL_LEAD_PX = 14;
const ROW_HEIGHT_PX = 13;
const MARKER_PX = 9;
const LABEL_GAP_PX = 3;

/**
 * Assign each tick a stagger row so no two labels are painted on top of one
 * another.
 *
 * This used to be `index % 2`, which only separates ticks that happen to
 * alternate in the array — two events close in time landing on the same parity
 * collided regardless of how near they were. Rows are now assigned greedily
 * from the actual horizontal extent each label will occupy: a tick drops to the
 * first row whose previous label has already ended.
 */
function staggerRows(
  ticks: TimelineTick[],
  at: (ms: number) => number,
  trackPx: number
): number[] {
  const rowEnds: number[] = [];
  const order = ticks
    .map((tick, index) => ({ index, left: at(tick.at), label: tick.label }))
    .sort((a, b) => a.left - b.left);

  const rows = new Array<number>(ticks.length).fill(0);
  for (const item of order) {
    const widthPct =
      ((item.label.length * LABEL_CHAR_PX + LABEL_LEAD_PX) / Math.max(trackPx, 1)) * 100;
    let row = 0;
    while (row < rowEnds.length && rowEnds[row] > item.left) row++;
    rowEnds[row] = item.left + widthPct;
    rows[item.index] = row;
  }
  return rows;
}

/**
 * Measured width of the lane track, so stagger maths works in real pixels.
 *
 * Measured off a resize listener rather than a ResizeObserver, matching
 * `useBoxSize` in OperationalMapCore — the console already sizes its map this
 * way, and it keeps the component renderable anywhere a DOM exists rather than
 * only where ResizeObserver does.
 */
function useTrackWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const measure = () => {
      const rect = ref.current?.getBoundingClientRect();
      if (rect && rect.width > 1) setWidth(rect.width);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  return [ref, width] as const;
}

export function MissionTimeline({
  timeline,
  className = "",
}: {
  timeline: Timeline;
  className?: string;
}) {
  const visibleTo = timeline.to + RIGHT_PAD_MS;
  const window = Math.max(visibleTo - timeline.from, MIN_WINDOW_MS);
  const spanS = window / 1000;
  const step = axisStepS(spanS);
  const marks: number[] = [];
  for (let s = 0; s <= spanS; s += step) marks.push(s);

  const at = (ms: number) => ((ms - timeline.from) / window) * 100;

  return (
    <Panel
      className={className}
      title="Mission timeline"
      right={
        /* A count of what the lanes below already show. Panel headers describe;
           they do not signal, so this reads at label weight. */
        <span
          data-testid="concurrency-badge"
          className={`font-mono text-[12px] uppercase tracking-[0.16em] ${
            timeline.concurrent ? "text-platinum" : "text-ash"
          }`}
        >
          {timeline.concurrent
            ? `CONCURRENT MISSION OWNERSHIP · ${timeline.lanes.filter((l) => l.active).length} EXECUTING`
            : `${timeline.lanes.length} MISSION${timeline.lanes.length === 1 ? "" : "S"}`}
        </span>
      }
      bodyClassName="overflow-hidden"
    >
      {timeline.lanes.length === 0 ? (
        <div className="px-3 py-5">
          <span className="font-mono text-[13px] text-ash">NO MISSION LANE</span>
        </div>
      ) : (
        <div className="flex h-full flex-col">
          {/* Axis */}
          <div className="relative flex h-[24px] shrink-0 border-b border-gunmetal">
            <div style={{ width: GUTTER }} className="shrink-0 border-r border-gunmetal" />
            <div className="relative flex-1">
              {marks.map((s) => (
                <span
                  key={s}
                  className="absolute top-0 flex h-full items-center border-l border-gunmetal pl-1 font-mono text-[11px] tabular-nums tracking-[0.1em] text-ash"
                  style={{ left: `${(s / spanS) * 100}%` }}
                >
                  +{s}s
                </span>
              ))}
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
            {timeline.lanes.map((lane) => (
              <Lane key={lane.missionId} lane={lane} at={at} />
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

function Lane({ lane, at }: { lane: TimelineLane; at: (ms: number) => number }) {
  const steps = lane.ticks.filter((tick) => tick.tier === "step");
  const response = lane.ticks.filter((tick) => tick.tier !== "step");
  const start = Number.isFinite(lane.startedAt) ? at(lane.startedAt) : 0;
  const end = lane.ticks.length > 0 ? at(lane.ticks[lane.ticks.length - 1].at) : start;
  const [trackRef, trackPx] = useTrackWidth<HTMLDivElement>();
  // Above and below the baseline are independent bands, so they stagger apart.
  const stepRows = staggerRows(steps, at, trackPx);
  const responseRows = staggerRows(response, at, trackPx);

  return (
    <div
      data-testid={`lane-${lane.missionId}`}
      className="flex min-h-[100px] flex-1 border-b border-gunmetal last:border-b-0"
    >
      <div
        style={{ width: GUTTER }}
        className={`flex shrink-0 flex-col justify-center gap-[3px] border-r border-l-2 border-gunmetal px-3 ${
          lane.active ? "border-l-orbital-blue" : "border-l-graphite"
        }`}
      >
        <span className="flex min-w-0 items-baseline gap-2">
          {/* Objective label and owner are identifiers. The lane's own state is
              already carried by its left border and baseline colour. */}
          <span className="shrink-0 font-mono text-[13px] tracking-[0.16em] text-muted-silver">
            {lane.objectiveLabel}
          </span>
          <span className="truncate font-mono text-[13px] text-platinum">{lane.objectiveKind}</span>
        </span>
        <span className="truncate font-mono text-[13px] tracking-[0.06em] text-platinum">
          {lane.owner ?? "unassigned"}
        </span>
        <span className="font-mono text-[11px] tracking-[0.1em] text-ash">
          mission {shortId(lane.missionId)}
        </span>
      </div>

      <div ref={trackRef} className="relative min-w-0 flex-1">
        {/* Lane baseline spanning the mission's own extent. */}
        <div
          className={`absolute top-1/2 h-px ${lane.active ? "bg-orbital-blue/50" : "bg-graphite"}`}
          style={{ left: `${start}%`, width: `${Math.max(0, end - start)}%` }}
        />
        {lane.active ? (
          <div
            className="absolute top-1/2 h-px bg-orbital-blue/25"
            style={{ left: `${end}%`, right: 0 }}
          />
        ) : null}

        {steps.map((tick, index) => (
          <Tick key={`${tick.label}-${tick.at}`} tick={tick} left={at(tick.at)} above row={stepRows[index]} />
        ))}
        {response.map((tick, index) => (
          <Tick key={`${tick.label}-${tick.at}`} tick={tick} left={at(tick.at)} row={responseRows[index]} />
        ))}
      </div>
    </div>
  );
}

function Tick({
  tick,
  left,
  above = false,
  row,
}: {
  tick: TimelineTick;
  left: number;
  above?: boolean;
  row: number;
}) {
  const colour =
    tick.tier === "verified"
      ? "bg-signal-green"
      : tick.tier === "simulated"
        ? "bg-launch-amber"
        : tick.proof
          ? "bg-signal-green"
          : "bg-orbital-blue";
  const text =
    tick.tier === "verified"
      ? "text-signal-green"
      : tick.tier === "simulated"
        ? "text-launch-amber"
        : tick.proof
          ? "text-signal-green"
          : "text-platinum";
  // The marker stays on the baseline — it *is* the time reading, so it must not
  // move — and only the label steps away into its stagger row. Offsetting the
  // whole group meant a lower row's marker landed on the row above's text.
  const markerAt = "calc(50% + 4px)";
  const labelAt = `calc(50% + ${4 + MARKER_PX + LABEL_GAP_PX + row * ROW_HEIGHT_PX}px)`;
  const place = (offset: string): React.CSSProperties =>
    above ? { left: `${left}%`, bottom: offset } : { left: `${left}%`, top: offset };

  return (
    <>
      <span
        aria-hidden="true"
        className={`absolute block h-[9px] w-[9px] ${colour}`}
        style={place(markerAt)}
      />
      <span
        className={`absolute whitespace-nowrap font-mono text-[11px] uppercase leading-none tracking-[0.1em] ${text}`}
        style={place(labelAt)}
      >
        {tick.label}
      </span>
    </>
  );
}
