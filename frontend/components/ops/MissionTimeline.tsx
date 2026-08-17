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

import type { Timeline, TimelineLane, TimelineTick } from "@/lib/mission-story";
import { shortId } from "@/lib/mission-story";

import { Panel } from "./primitives";

const MIN_WINDOW_MS = 30_000;
const GUTTER = 210;

function axisStepS(spanS: number): number {
  if (spanS <= 60) return 10;
  if (spanS <= 180) return 30;
  if (spanS <= 600) return 60;
  return 300;
}

export function MissionTimeline({
  timeline,
  className = "",
}: {
  timeline: Timeline;
  className?: string;
}) {
  const window = Math.max(timeline.to - timeline.from, MIN_WINDOW_MS);
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
        <span
          data-testid="concurrency-badge"
          className={`font-mono text-[12px] uppercase tracking-[0.16em] ${
            timeline.concurrent ? "text-signal-green" : "text-ash"
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
        <span className="flex items-baseline gap-2">
          <span className="font-mono text-[13px] tracking-[0.16em] text-launch-amber">
            {lane.objectiveLabel}
          </span>
          <span className="font-mono text-[13px] text-platinum">{lane.objectiveKind}</span>
        </span>
        <span className="font-mono text-[13px] tracking-[0.06em] text-orbital-blue">
          {lane.owner ?? "unassigned"}
        </span>
        <span className="font-mono text-[11px] tracking-[0.1em] text-ash">
          mission {shortId(lane.missionId)}
        </span>
      </div>

      <div className="relative min-w-0 flex-1">
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
          <Tick key={`${tick.label}-${tick.at}`} tick={tick} left={at(tick.at)} above index={index} />
        ))}
        {response.map((tick, index) => (
          <Tick key={`${tick.label}-${tick.at}`} tick={tick} left={at(tick.at)} index={index} />
        ))}
      </div>
    </div>
  );
}

function Tick({
  tick,
  left,
  above = false,
  index,
}: {
  tick: TimelineTick;
  left: number;
  above?: boolean;
  index: number;
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
  // Stagger consecutive labels so a dense burst of frames stays readable.
  const offset = index % 2 === 0 ? 0 : 12;
  const position = `calc(50% + 4px + ${offset}px)`;
  const style: React.CSSProperties = above
    ? { left: `${left}%`, bottom: position }
    : { left: `${left}%`, top: position };

  return (
    <div
      className={`absolute flex items-start gap-[3px] ${above ? "flex-col-reverse" : "flex-col"}`}
      style={style}
    >
      <span className={`block h-[9px] w-[9px] shrink-0 ${colour}`} aria-hidden="true" />
      <span
        className={`whitespace-nowrap font-mono text-[11px] uppercase leading-none tracking-[0.1em] ${text}`}
      >
        {tick.label}
      </span>
    </div>
  );
}
