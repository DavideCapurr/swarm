"use client";

/**
 * The live wiring root for `/demo/intrusion`.
 *
 * It reads `useSwarm()` and hands the frames to `ConsoleSurface`. It makes no
 * operational decision and holds no operational state: allocation, ownership,
 * execution-group composition, role assignment, replacement, runtime phase,
 * evidence and payload results all arrive from SwarmOS. The Console renders
 * them.
 *
 * The operating scenario is simulated for the recording. The surface preserves
 * the runtime-truth boundary on its own terms: the telemetry source is read off
 * the units' own vendor/model rather than asserted, PX4 output confirmation is
 * distinguished from simulated payload response, and no camera feed is drawn
 * because the MAVLink path publishes none.
 */

import { useMemo } from "react";

import { ConsoleSurface, type SurfaceFrame } from "@/components/console/ConsoleSurface";
import { useSwarm } from "@/lib/state";

export function IntrusionResponseDemo() {
  const {
    allocations,
    anomalies,
    executionGroups,
    missionDecisions,
    missionDecisionReviews,
    objectiveStates,
    missionRuntime,
    missionRuntimeLog,
    missions,
    payloadEvents,
    units,
    link,
    clock,
    role,
    reviewDecision,
  } = useSwarm();

  const frame = useMemo<SurfaceFrame>(
    () => ({
      link,
      clockText: `${clock.time} UTC`,
      units,
      anomalies,
      allocations,
      executionGroups,
      missionDecisions,
      missionDecisionReviews,
      objectiveStates,
      canReviewDecision: role === "operator" || role === "commander",
      onReviewDecision: async (decisionId, action) => {
        await reviewDecision(decisionId, action);
      },
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
      missionDecisions,
      missionDecisionReviews,
      objectiveStates,
      missions,
      missionRuntime,
      missionRuntimeLog,
      payloadEvents,
      role,
      reviewDecision,
    ]
  );

  return <ConsoleSurface frame={frame} />;
}
