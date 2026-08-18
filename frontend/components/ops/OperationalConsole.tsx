"use client";

/**
 * OperationalConsole — the whole operator surface, composed from server frames.
 *
 * Deliberately presentational: it takes a frame and renders it. `useSwarm()` is
 * wired in one level up so the same surface can be driven from live SwarmOS
 * truth or from a recorded frame script without either path special-casing the
 * other.
 *
 * Reading order enforced by the layout:
 *   sensor input → objective (left) → fleet state (left) → SwarmOS decision (right)
 *   → mission ownership (right) → physical execution (map + right)
 *   → verified evidence (right) → adaptation (bottom timeline).
 */

import { useEffect, useMemo, useState } from "react";

import type {
  AllocationDecision,
  AnomalyView,
  ExecutionGroup,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "@/lib/api";
import {
  buildFleetRows,
  buildPayloadChannels,
  buildStories,
  buildTimeline,
  serverPhaseLabel,
  shortId,
  type ObjectiveStory,
} from "@/lib/mission-story";
import type { LinkState } from "@/lib/state";

import { CommandBar } from "./CommandBar";
import { DecisionRail } from "./DecisionRail";
import { FleetPanel } from "./FleetPanel";
import { MissionTimeline } from "./MissionTimeline";
import { ObjectiveQueue, ImageryAside } from "./ObjectiveQueue";
import { OperationalMap } from "./OperationalMap";

const SCENE_IMAGERY = "/sim-feed/intrusion-pov.mp4";

export type ConsoleFrame = {
  link: LinkState;
  sessionLabel: string;
  operatorId: string;
  role: string | null;
  clockText: string;
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: AllocationDecision[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  executionGroups: ExecutionGroup[];
  missions: MissionView[];
  /** Set only by the recorded-frame harness; stamps the bar so it can't pass for live. */
  replay?: boolean;
  /** Fixed clock for deterministic rendering in tests. */
  now?: number;
};

/**
 * Ticking wall clock for the timeline's live right edge, so a running mission
 * reads as running. Held in state rather than read during render — a render
 * must be reproducible from its inputs.
 */
function useWallClock(enabled: boolean): number {
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (!enabled) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, [enabled]);
  return now;
}

/**
 * One-line causal readout of the focused objective.
 *
 * This is intentionally redundant with the richer panels. A first-time viewer
 * should be able to understand what SwarmOS does before learning how to read
 * the entire Console: reported sensor input → objective → central decision →
 * ownership → physical execution → evidence. Every value is already present in
 * the focused story.
 */
function ControlLoopStrip({ story }: { story: ObjectiveStory | null }) {
  if (!story) {
    return (
      <div className="flex h-[48px] shrink-0 items-center border border-gunmetal bg-obsidian px-3">
        <span className="font-mono text-[13px] tracking-[0.14em] text-ash">CONTROL LOOP</span>
        <span className="ml-4 min-w-0 truncate font-mono text-[14px] tracking-[0.08em] text-muted-silver">
          SENSOR INPUT → OBJECTIVE → SWARMOS DECIDES → PHYSICAL AGENTS EXECUTE → VERIFIED EVIDENCE RETURNS
        </span>
        <span className="ml-auto shrink-0 pl-3 font-mono text-[13px] tracking-[0.1em] text-ash">
          SWARMOS DECIDES · PHYSICAL AGENTS EXECUTE
        </span>
      </div>
    );
  }

  const excluded = story.candidates.find((candidate) => candidate.kind === "excluded");
  const verified = story.evidence.filter((row) => row.tier === "verified").at(-1);
  const phase = serverPhaseLabel(story.serverPhase);
  const source = story.detectedBy ?? "swarm anomaly bus";

  return (
    <div
      className="flex h-[50px] shrink-0 items-center gap-3 overflow-hidden border border-gunmetal bg-surface-2 px-3 shadow-inset-highlight"
      data-testid="control-loop-strip"
    >
      <span className="shrink-0 font-mono text-[13px] tracking-[0.14em] text-ash">CONTROL LOOP</span>
      {/* The strip is a causal chain of facts. Only two links are genuinely
          state — the exclusion that constrained the decision, and whether
          evidence came back — so only those carry colour. */}
      <LoopValue
        label="input → objective"
        value={`${source} → ${story.label} · ${story.kind} · ${story.missionKind}`}
        tone="silver"
      />
      <Arrow />
      {excluded ? (
        <>
          <LoopValue
            label="constraint"
            value={`${excluded.agentId} EXCLUDED · ${excluded.reason}`}
            tone="amber"
          />
          <Arrow />
        </>
      ) : null}
      <LoopValue
        label="SwarmOS decision"
        value={story.owner ? `SELECT ${story.owner}` : "NO AWARD"}
        tone="orbital"
      />
      <Arrow />
      <LoopValue
        label="mission ownership"
        value={`${shortId(story.missionId)} → ${story.owner ?? "—"}`}
        tone="platinum"
      />
      <Arrow />
      <LoopValue
        label="physical execution"
        value={phase}
        tone={story.serverPhase === "ON_STATION" || story.serverPhase === "DONE" ? "green" : "orbital"}
      />
      <Arrow />
      <LoopValue
        label="verified evidence"
        value={verified?.proof ?? "PENDING"}
        tone={verified ? "green" : "silver"}
      />
      {/* A standing legend for the architecture boundary, not a live reading —
          so it sits at label weight rather than in the live-channel accent. */}
      <span className="ml-auto shrink-0 border-l border-gunmetal pl-3 font-mono text-[11px] leading-tight tracking-[0.08em] text-ash">
        SWARMOS DECIDES · PHYSICAL AGENTS EXECUTE
      </span>
    </div>
  );
}

function LoopValue({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "amber" | "orbital" | "green" | "platinum" | "silver";
}) {
  const toneClass = {
    amber: "text-launch-amber",
    orbital: "text-orbital-blue",
    green: "text-signal-green",
    platinum: "text-platinum",
    silver: "text-muted-silver",
  }[tone];

  return (
    <span className="flex min-w-0 shrink flex-col gap-[2px] whitespace-nowrap">
      <span className="font-mono text-[11px] uppercase leading-none tracking-[0.12em] text-ash">{label}</span>
      <span className={`truncate font-mono text-[14px] leading-none tracking-[0.07em] ${toneClass}`}>{value}</span>
    </span>
  );
}

// The field separator sits at the label tier. It was graphite, which measured
// 1.47:1 on obsidian — below even the 3:1 non-text floor, so the arrow that
// carries the left-to-right reading order was effectively invisible.
function Arrow() {
  return <span className="shrink-0 font-mono text-[14px] text-ash">→</span>;
}

export function OperationalConsole({ frame }: { frame: ConsoleFrame }) {
  const stories = useMemo(
    () =>
      buildStories({
        allocations: frame.allocations,
        anomalies: frame.anomalies,
        missionRuntime: frame.missionRuntime,
        missionRuntimeLog: frame.missionRuntimeLog,
        payloadEvents: frame.payloadEvents,
        missions: frame.missions,
      }),
    [
      frame.allocations,
      frame.anomalies,
      frame.missionRuntime,
      frame.missionRuntimeLog,
      frame.payloadEvents,
      frame.missions,
    ]
  );

  const group = useMemo(() => {
    const ordered = frame.executionGroups
      .slice()
      .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
    return ordered.at(-1);
  }, [frame.executionGroups]);

  const fleetRows = useMemo(
    () => buildFleetRows(frame.units, stories, frame.executionGroups),
    [frame.units, stories, frame.executionGroups]
  );

  const newestMissionId = stories.at(-1)?.missionId ?? null;
  const [pinned, setPinned] = useState<string | null>(null);
  // A newly allocated objective takes focus: the adaptation beat is the point
  // of the second event and must not need a click to be seen.
  useEffect(() => setPinned(null), [newestMissionId]);
  const focusMissionId =
    pinned && stories.some((story) => story.missionId === pinned) ? pinned : newestMissionId;
  const focusStory = stories.find((story) => story.missionId === focusMissionId) ?? null;

  // The scene clip is a permanently labelled simulated reference, not evidence.
  // Prefer the intrusion source because the bundled clip depicts that first
  // objective; never relabel it as the later thermal input.
  const imageryStory = stories.find((story) => story.kind === "INTRUSION") ?? focusStory;

  // Fleet-wide, not focus-scoped: the light is on because of the *first*
  // objective while SwarmOS is already allocating the second, and that overlap
  // is exactly what the surface has to show.
  const payloadChannels = useMemo(
    () => buildPayloadChannels(stories.flatMap((story) => story.payloadEvents)),
    [stories]
  );

  const wallClock = useWallClock(frame.now == null);
  const timeline = useMemo(
    () => buildTimeline(stories, frame.now ?? wallClock),
    [stories, frame.now, wallClock]
  );

  const owning = fleetRows.filter((row) => row.missionId).length;
  const objectivesOpen = stories.filter((story) => story.active).length;
  const separateTakeBBench = Boolean(
    group && frame.sessionLabel.trim().toLowerCase().includes("take b")
  );

  return (
    <main className="flex h-screen min-h-0 flex-col gap-2 bg-surface-0 p-2 text-platinum">
      <CommandBar
        link={frame.link}
        sessionLabel={frame.sessionLabel}
        operatorId={frame.operatorId}
        role={frame.role}
        fleetTotal={fleetRows.length}
        fleetOwning={owning}
        objectivesOpen={objectivesOpen}
        clockText={frame.clockText}
        replay={frame.replay}
      />

      <ControlLoopStrip story={focusStory} />

      {separateTakeBBench ? (
        <div
          data-testid="take-b-bench-boundary"
          className="flex h-[34px] shrink-0 items-center justify-between border border-launch-amber/55 bg-launch-amber/[0.04] px-3 font-mono uppercase"
        >
          <span className="text-[13px] font-medium tracking-[0.12em] text-launch-amber">
            TAKE B · SEPARATE PX4 SITL BENCH
          </span>
          <span className="text-[12px] tracking-[0.1em] text-muted-silver">
            NOT CONTINUOUS WITH TAKE A · SITL ONLY
          </span>
        </div>
      ) : null}

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(380px,17%)_minmax(0,1fr)_minmax(540px,28%)] gap-2">
        {/* The rail is a height budget, not three stacked boxes. Objectives and
            fleet share the flexible space and scroll inside it; the imagery
            aside is the only fixed-size element. `max-h-[46%] shrink-0`
            previously froze the queue at a height that cut its second card
            through the middle of a line, with no way to scroll to the rest. */}
        <div className="flex min-h-0 flex-col gap-2">
          <ObjectiveQueue
            className="min-h-0 flex-[5]"
            stories={stories}
            focusMissionId={focusMissionId}
            onFocus={setPinned}
          />
          <FleetPanel className="min-h-0 flex-[4]" rows={fleetRows} />
          <ImageryAside src={SCENE_IMAGERY} story={imageryStory} />
        </div>

        <OperationalMap units={fleetRows} stories={stories} focusMissionId={focusMissionId} />

        <DecisionRail story={focusStory} group={group} payloadChannels={payloadChannels} />
      </div>

      {/* 288px, not 260: the panel header, the axis row and two 100px lanes add
          up past 260, and the body clips — which cut the second lane's owner and
          mission id off the bottom of the screen. */}
      <MissionTimeline className="h-[288px] shrink-0" timeline={timeline} />
    </main>
  );
}
