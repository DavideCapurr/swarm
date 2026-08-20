"use client";

/**
 * The live wiring root for `/demo/intrusion`.
 *
 * It reads `useSwarm()` and hands the frames to `ConsoleSurface`. It makes no
 * operational decision and holds no operational state: allocation, ownership,
 * execution-group composition, role assignment, disposition, replacement,
 * runtime phase, evidence and payload results all arrive from SwarmOS. The
 * Console renders them.
 */

import { useMemo } from "react";

import { ConsoleSurface, type SurfaceFrame } from "@/components/console/ConsoleSurface";
import { useSwarm } from "@/lib/state";

export function IntrusionResponseDemo() {
  const {
    allocations,
    anomalies,
    executionGroups,
    dispositions,
    missionRuntime,
    missionRuntimeLog,
    missions,
    payloadEvents,
    units,
    link,
    clock,
  } = useSwarm();

  const frame = useMemo<SurfaceFrame>(
    () => ({
      link,
      clockText: `${clock.time} UTC`,
      units,
      anomalies,
      allocations,
      executionGroups,
      dispositions,
      missions,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
    }),
    [
      link,
      clock.time,
      units,
      anomalies,
      allocations,
      executionGroups,
      dispositions,
      missions,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
    ]
  );

  return <ConsoleSurface frame={frame} />;
}
