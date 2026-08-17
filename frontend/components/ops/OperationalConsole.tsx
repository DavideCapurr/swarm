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
 *   objective (left) → fleet state (left) → SwarmOS decision (right)
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

  return (
    <main className="flex h-screen min-h-0 flex-col gap-2 bg-absolute-black p-2 text-platinum">
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

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(340px,16%)_minmax(0,1fr)_minmax(470px,26%)] gap-2">
        <div className="flex min-h-0 flex-col gap-2">
          <ObjectiveQueue
            className="max-h-[46%] shrink-0"
            stories={stories}
            focusMissionId={focusMissionId}
            onFocus={setPinned}
          />
          <FleetPanel className="min-h-0 flex-1" rows={fleetRows} />
          <ImageryAside src={SCENE_IMAGERY} present={stories.length > 0} />
        </div>

        <OperationalMap units={fleetRows} stories={stories} focusMissionId={focusMissionId} />

        <DecisionRail story={focusStory} group={group} payloadChannels={payloadChannels} />
      </div>

      <MissionTimeline className="h-[280px] shrink-0" timeline={timeline} />
    </main>
  );
}
