"use client";

/**
 * ConsoleSurface — the whole operator surface.
 *
 * The composition is a full-bleed map with operating surfaces floating over it,
 * not a dashboard that contains a map. The centre of the viewport is left to
 * the physical world; the interface holds the edges.
 *
 * Presentational by construction: it takes one frame of server truth and
 * renders it. `useSwarm()` is wired one level up, so the same surface is driven
 * by live SwarmOS frames or by the recorded-frame harness without either path
 * special-casing the other.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { buildAuthorityView } from "@/lib/authority";
import { buildPayloadChannels } from "@/lib/mission-story";
import type { MapGeo } from "@/lib/opsmap";
import { telemetrySourceLabel } from "@/lib/telemetry-source";
import type { LinkState } from "@/lib/state";
import type {
  AllocationDecision,
  AnomalyView,
  ExecutionGroup,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "@/lib/api";

import { MapCanvas, useImageryStatus } from "./MapCanvas";
import { MapOverlay } from "./MapOverlay";
import { DetectionPanel, DETECTION_WIDTH } from "./DetectionPanel";
import { MissionAuthorityPanel, AUTHORITY_WIDTH } from "./MissionAuthorityPanel";
import { MissionTrace, TRACE_WIDTH } from "./MissionTrace";
import { NavigationRail, RAIL_WIDTH } from "./NavigationRail";
import { PhysicalCapacityPanel, CAPACITY_WIDTH } from "./PhysicalCapacityPanel";
import { SystemStatus, STATUS_HEIGHT } from "./SystemStatus";
import {
  anchorOrigin,
  buildConsoleProjection,
  buildTiles,
  targetFrame,
  type SafeInset,
} from "./projection";
import { useCameraGlide } from "./useCameraGlide";

export type SurfaceFrame = {
  link: LinkState;
  clockText: string;
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: AllocationDecision[];
  executionGroups: ExecutionGroup[];
  missions: MissionView[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  /** Set only by the recorded-frame harness; stamps the surface so it cannot pass for live. */
  replay?: boolean;
};

/** Pixels the floating surfaces claim, so geography composes into what is left. */
const INSET: SafeInset = {
  left: RAIL_WIDTH + DETECTION_WIDTH + 34,
  right: AUTHORITY_WIDTH + 44,
  top: STATUS_HEIGHT + 12,
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

  // Operator focus wins while it is held; otherwise the surface follows the
  // objective SwarmOS is currently working.
  const [heldFocus, setHeldFocus] = useState<string | null>(null);
  const [selectedExecutor, setSelectedExecutor] = useState<string | null>(null);
  const focusKey =
    heldFocus && view.objectives.some((o) => o.key === heldFocus)
      ? heldFocus
      : view.defaultFocusKey;
  const focused = view.objectives.find((o) => o.key === focusKey) ?? null;

  // The camera frames the mission, not the map. The points it is solved from
  // are the focused objective and the executors SwarmOS put on it — including
  // one that has failed, because that is still part of what is happening. A
  // long transit therefore opens the frame, convergence on station closes it,
  // and a replacement launching from unused capacity opens it again.
  //
  // Observed tracks are deliberately excluded. Keeping every metre already
  // flown in frame would pin the camera wide for the rest of the take.
  const originRef = useRef<MapGeo | null>(null);
  const framed = useMemo<MapGeo[]>(() => {
    const live = (geo: MapGeo) => Number.isFinite(geo.lat) && geo.lat !== 0;
    if (!focused) return view.capacity.map((row) => row.geo).filter(live);
    const onObjective = new Set(
      focused.slots.map((slot) => slot.agentId).filter((id): id is string => Boolean(id))
    );
    const out: MapGeo[] = view.capacity
      .filter((row) => onObjective.has(row.agentId))
      .map((row) => row.geo)
      .filter(live);
    if (focused.geo) out.push(focused.geo);
    return out.length > 0 ? out : view.capacity.map((row) => row.geo).filter(live);
  }, [focused, view.capacity]);

  if (!originRef.current) {
    originRef.current = anchorOrigin(view.capacity.map((row) => row.geo));
  }

  const aspect = Math.max(
    1,
    (box.width - INSET.left - INSET.right) / (box.height - INSET.top - INSET.bottom)
  );
  const wanted = useMemo(
    () => targetFrame(originRef.current, framed, aspect),
    [framed, aspect]
  );
  const solved = useCameraGlide(wanted);

  const projection = useMemo(
    () => buildConsoleProjection(solved, box, INSET),
    // The camera is a value, not an object identity: depend on its fields.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [solved.origin?.lat, solved.origin?.lon, solved.center.e, solved.center.n, solved.extentM, box.width, box.height]
  );

  const tiles = useMemo(
    () => (projection ? buildTiles(solved, projection, box) : []),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [projection, solved.center.e, solved.center.n, solved.extentM, box.width, box.height]
  );
  const imagery = useImageryStatus(tiles[0]?.url ?? null);

  // Bounded-response channels for the focused objective only: the light and the
  // speaker are separate claims and stay separate all the way to the panel.
  const channels = useMemo(() => {
    if (!focused) return [];
    const missionIds = new Set(
      focused.slots.map((slot) => slot.missionId).filter((id): id is string => Boolean(id))
    );
    return buildPayloadChannels(
      frame.payloadEvents.filter((event) => missionIds.has(event.mission_id))
    );
  }, [focused, frame.payloadEvents]);

  const telemetrySource = useMemo(
    () => telemetrySourceLabel(frame.units),
    [frame.units]
  );
  const committed = view.capacity.filter(
    (row) => row.commitment === "ASSIGNED" || row.commitment === "COMMITTED"
  ).length;

  return (
    <div
      ref={ref}
      data-testid="console-surface"
      /* The camera is published so a test — and a recording check — can assert
         that the framing followed the mission, without reaching into React. */
      data-extent-m={solved.extentM.toFixed(1)}
      className="relative h-screen w-screen overflow-hidden bg-[#050605]"
    >
      <MapCanvas tiles={tiles} status={imagery}>
        {projection ? (
          <MapOverlay
            projection={projection}
            objectives={view.objectives}
            capacity={view.capacity}
            focusKey={focusKey}
            selectedExecutor={selectedExecutor}
            channels={channels}
            onSelectObjective={setHeldFocus}
            onSelectExecutor={setSelectedExecutor}
          />
        ) : null}
      </MapCanvas>

      <NavigationRail active="map" />

      {focused?.detection ? (
        <div
          className="pointer-events-none absolute z-30"
          style={{ left: RAIL_WIDTH + 16, top: STATUS_HEIGHT + 12 }}
        >
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
        className="pointer-events-none absolute z-30"
        style={{ right: 20, top: STATUS_HEIGHT + 12 }}
      >
        <MissionAuthorityPanel
          objectives={view.objectives}
          focused={focused}
          capacity={view.capacity}
          channels={channels}
          onSelectObjective={setHeldFocus}
        />
      </div>

      <div
        className="pointer-events-none absolute z-30"
        style={{ left: RAIL_WIDTH + 16, bottom: 20 }}
      >
        <PhysicalCapacityPanel
          capacity={view.capacity}
          selected={selectedExecutor}
          objectives={view.objectives}
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
          <MissionTrace
            stages={focused?.trace ?? []}
            objectiveLabel={focused?.label ?? null}
          />
        </div>
      </div>
    </div>
  );
}
