"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { buildAuthorityView, compositionDigest } from "@/lib/authority";
import { buildPayloadChannels } from "@/lib/mission-story";
import type { MapGeo } from "@/lib/opsmap";
import { telemetrySourceLabel } from "@/lib/telemetry-source";
import type { LinkState } from "@/lib/state";
import type {
  AllocationDecision,
  AnomalyView,
  DispositionDecision,
  ExecutionGroup,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "@/lib/api";

import { MapCanvas, useImageryStatus } from "./MapCanvas";
import { MapOverlay } from "./MapOverlay";
import { DetectionPanel, DETECTION_WIDTH } from "./DetectionPanel";
import { MissionTrace, TRACE_WIDTH } from "./MissionTrace";
import { NarrationStrip, NARRATION_HEIGHT } from "./NarrationStrip";
import { NavigationRail, RAIL_WIDTH } from "./NavigationRail";
import { PhysicalCapacityPanel, CAPACITY_WIDTH } from "./PhysicalCapacityPanel";
import { SwarmAuthorityPanel, AUTHORITY_WIDTH } from "./SwarmAuthorityPanel";
import { SwarmMapKey } from "./SwarmMapKey";
import { SystemStatus, STATUS_HEIGHT } from "./SystemStatus";
import {
  anchorOrigin,
  buildConsoleProjection,
  buildTiles,
  targetFrame,
  type SafeInset,
} from "./projection";
import { useAdaptationBeat } from "./useAdaptation";
import { useCameraGlide } from "./useCameraGlide";

export type SurfaceFrame = {
  link: LinkState;
  clockText: string;
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: AllocationDecision[];
  executionGroups: ExecutionGroup[];
  /** Latest server-issued station geometry. Old replay fixtures may omit it. */
  dispositions?: DispositionDecision[];
  missions: MissionView[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  replay?: boolean;
};

const TOP_PANEL_TOP = STATUS_HEIGHT + NARRATION_HEIGHT + 22;

const INSET: SafeInset = {
  left: RAIL_WIDTH + DETECTION_WIDTH + 34,
  right: AUTHORITY_WIDTH + 44,
  top: TOP_PANEL_TOP,
  bottom: 132,
};

const DEFAULT_BOX = { width: 1600, height: 900 };

function useViewportBox() {
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

export function ConsoleSurface({ frame }: { frame: SurfaceFrame }) {
  const { ref, box } = useViewportBox();

  const view = useMemo(
    () =>
      buildAuthorityView({
        units: frame.units,
        anomalies: frame.anomalies,
        allocations: frame.allocations,
        executionGroups: frame.executionGroups,
        missions: frame.missions,
        missionRuntime: frame.missionRuntime,
        missionRuntimeLog: frame.missionRuntimeLog,
        payloadEvents: frame.payloadEvents,
      }),
    [
      frame.units,
      frame.anomalies,
      frame.allocations,
      frame.executionGroups,
      frame.missions,
      frame.missionRuntime,
      frame.missionRuntimeLog,
      frame.payloadEvents,
    ]
  );

  const [heldFocus, setHeldFocus] = useState<string | null>(null);
  const [selectedExecutor, setSelectedExecutor] = useState<string | null>(null);
  const focusKey =
    heldFocus && view.objectives.some((o) => o.key === heldFocus)
      ? heldFocus
      : view.defaultFocusKey;
  const focused = view.objectives.find((o) => o.key === focusKey) ?? null;
  const focusedDisposition = useMemo(
    () =>
      focused
        ? (frame.dispositions ?? []).find(
            (decision) => decision.objective_mission_id === focused.missionId
          ) ?? null
        : null,
    [focused, frame.dispositions]
  );

  const namedAgents = useMemo(() => {
    const named = new Set<string>();
    for (const slot of focused ? compositionDigest(focused.slots).rows : []) {
      if (slot.agentId) named.add(slot.agentId);
    }
    return named;
  }, [focused]);

  const beat = useAdaptationBeat(focused);

  const originRef = useRef<MapGeo | null>(null);
  const framed = useMemo<MapGeo[]>(() => {
    const live = (geo: MapGeo) => Number.isFinite(geo.lat) && geo.lat !== 0;
    if (!focused || !focused.active) {
      const site = view.capacity.map((row) => row.geo).filter(live);
      for (const objective of view.objectives) {
        if (objective.geo) site.push(objective.geo);
      }
      return site;
    }
    const onObjective = new Set(
      focused.slots.map((slot) => slot.agentId).filter((id): id is string => Boolean(id))
    );
    const out: MapGeo[] = view.capacity
      .filter((row) => onObjective.has(row.agentId) || row.fsmState !== "DOCKED")
      .map((row) => row.geo)
      .filter(live);
    if (focused.geo) out.push(focused.geo);
    for (const assignment of focusedDisposition?.assignments ?? []) {
      if (live(assignment.geo)) out.push(assignment.geo);
    }
    return out.length > 0 ? out : view.capacity.map((row) => row.geo).filter(live);
  }, [focused, focusedDisposition, view.capacity, view.objectives]);

  if (!originRef.current) {
    originRef.current = anchorOrigin(view.capacity.map((row) => row.geo));
  }

  const aspect = Math.max(
    1,
    (box.width - INSET.left - INSET.right) / (box.height - INSET.top - INSET.bottom)
  );
  const wanted = useMemo(() => targetFrame(originRef.current, framed, aspect), [framed, aspect]);
  const solved = useCameraGlide(wanted);

  const projection = useMemo(
    () => buildConsoleProjection(solved, box, INSET),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [solved.origin?.lat, solved.origin?.lon, solved.center.e, solved.center.n, solved.extentM, box.width, box.height]
  );

  const tiles = useMemo(
    () => (projection ? buildTiles(solved, projection, box) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projection, solved.center.e, solved.center.n, solved.extentM, box.width, box.height]
  );
  const imagery = useImageryStatus(tiles[0]?.url ?? null);

  const safeArea = useMemo(
    () => ({
      top: INSET.top,
      bottom: box.height - INSET.bottom,
      left: INSET.left,
      right: box.width - INSET.right,
    }),
    [box.height, box.width]
  );

  const channels = useMemo(() => {
    if (!focused) return [];
    const missionIds = new Set(
      focused.slots.map((slot) => slot.missionId).filter((id): id is string => Boolean(id))
    );
    return buildPayloadChannels(
      frame.payloadEvents.filter((event) => missionIds.has(event.mission_id))
    );
  }, [focused, frame.payloadEvents]);

  const telemetrySource = useMemo(() => telemetrySourceLabel(frame.units), [frame.units]);
  const committed = view.capacity.filter(
    (row) => row.commitment === "ASSIGNED" || row.commitment === "COMMITTED"
  ).length;

  return (
    <div
      ref={ref}
      data-testid="console-surface"
      data-extent-m={solved.extentM.toFixed(1)}
      className="relative h-screen w-screen overflow-hidden bg-[#050605]"
    >
      <MapCanvas tiles={tiles} status={imagery}>
        {projection ? (
          <MapOverlay
            projection={projection}
            objectives={view.objectives}
            capacity={view.capacity}
            disposition={focusedDisposition}
            focusKey={focusKey}
            selectedExecutor={selectedExecutor}
            namedAgents={namedAgents}
            channels={channels}
            safeArea={safeArea}
            onSelectObjective={setHeldFocus}
            onSelectExecutor={setSelectedExecutor}
          />
        ) : null}
      </MapCanvas>

      <NavigationRail active="map" />

      {focused?.detection ? (
        <div className="pointer-events-none absolute z-30" style={{ left: RAIL_WIDTH + 16, top: TOP_PANEL_TOP }}>
          <DetectionPanel objective={focused} />
        </div>
      ) : null}

      <SystemStatus
        link={frame.link}
        telemetrySource={telemetrySource}
        executorsTotal={view.capacity.length}
        executorsCommitted={committed}
        clockText={frame.clockText}
        replay={frame.replay}
      />

      <div
        className="pointer-events-none absolute z-30 flex justify-center"
        style={{ left: RAIL_WIDTH + 16, right: 20, top: STATUS_HEIGHT + 10 }}
      >
        <NarrationStrip focused={focused} beat={beat} />
      </div>

      <div
        className="pointer-events-none absolute z-30 flex justify-center"
        style={{ left: INSET.left, right: INSET.right, top: TOP_PANEL_TOP + 6 }}
      >
        <SwarmMapKey focused={focused} />
      </div>

      <div className="pointer-events-none absolute z-30" style={{ right: 20, top: TOP_PANEL_TOP }}>
        <SwarmAuthorityPanel
          objectives={view.objectives}
          focused={focused}
          beat={beat}
          capacity={view.capacity}
          channels={channels}
          onSelectObjective={setHeldFocus}
        />
      </div>

      <div className="pointer-events-none absolute z-30" style={{ left: RAIL_WIDTH + 16, bottom: 20 }}>
        <PhysicalCapacityPanel
          capacity={view.capacity}
          selected={selectedExecutor}
          objectives={view.objectives}
          namedAgents={namedAgents}
          onSelect={setSelectedExecutor}
        />
      </div>

      <div
        className="pointer-events-none absolute z-30 flex justify-center"
        style={{
          left: RAIL_WIDTH + 16 + CAPACITY_WIDTH + 28,
          right: 20 + AUTHORITY_WIDTH + 28,
          bottom: 20,
        }}
      >
        <div style={{ width: Math.min(TRACE_WIDTH, 10_000), maxWidth: "100%" }}>
          <MissionTrace stages={focused?.trace ?? []} objectiveLabel={focused?.label ?? null} />
        </div>
      </div>

      <style jsx global>{`
        [data-testid^="swarm-hull-"] path:first-child {
          opacity: 0.06 !important;
        }
        [data-testid^="swarm-hull-"] path:last-child {
          opacity: 0.46 !important;
          stroke-width: 1.2 !important;
        }
        [data-testid^="swarm-caption-"] > div:first-child,
        [data-testid^="swarm-caption-"] > div:last-child {
          opacity: 0.52;
        }
      `}</style>
    </div>
  );
}
