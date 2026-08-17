"use client";

/**
 * The live wiring root for `/demo/intrusion`.
 *
 * It reads `useSwarm()` and hands the frames to `OperationalConsole`. It makes
 * no operational decision and holds no operational state: allocation,
 * ownership, runtime phase, evidence and payload results all arrive from
 * SwarmOS. The Console renders them.
 *
 * The operating scenario itself is simulated for the recording. The standing
 * CommandBar separately preserves the PX4 SITL runtime-truth boundary, while
 * the imagery panel remains explicitly marked as simulated and not evidence.
 */

import { useMemo } from "react";

import { OperationalConsole, type ConsoleFrame } from "@/components/ops/OperationalConsole";
import { useSwarm } from "@/lib/state";

const RECORDING_SCENARIO_LABEL = "SIMULATED OPERATING SCENARIO";

export function IntrusionResponseDemo() {
  const {
    allocations,
    anomalies,
    executionGroups,
    missionRuntime,
    missionRuntimeLog,
    missions,
    payloadEvents,
    units,
    link,
    clock,
    operatorId,
    role,
  } = useSwarm();

  const frame = useMemo<ConsoleFrame>(
    () => ({
      link,
      sessionLabel: RECORDING_SCENARIO_LABEL,
      operatorId,
      role,
      clockText: `${clock.time} UTC`,
      units,
      anomalies,
      allocations,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
      executionGroups,
      missions,
    }),
    [
      link,
      operatorId,
      role,
      clock.time,
      units,
      anomalies,
      allocations,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
      executionGroups,
      missions,
    ]
  );

  return <OperationalConsole frame={frame} />;
}
