"use client";

/**
 * The live wiring root for `/demo/intrusion`.
 *
 * It reads `useSwarm()` and hands the frames to `OperationalConsole`. It makes
 * no operational decision and holds no operational state: allocation,
 * ownership, runtime phase, evidence and payload results all arrive from
 * SwarmOS. The Console renders them.
 */

import { useMemo } from "react";

import { OperationalConsole, type ConsoleFrame } from "@/components/ops/OperationalConsole";
import { useSwarm } from "@/lib/state";

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
    session,
  } = useSwarm();

  const frame = useMemo<ConsoleFrame>(
    () => ({
      link,
      sessionLabel: session?.label ?? "session",
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
      session,
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
