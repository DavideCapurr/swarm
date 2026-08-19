"use client";

import { useMemo } from "react";

import type { DispositionDecision } from "@/lib/api";
import type { ScreenPoint } from "@/lib/opsmap";

import type { ConsoleProjection } from "./projection";

/**
 * Decision overlay, not telemetry.
 *
 * Every target in this component arrived in `DispositionDecision.assignments`.
 * The only calculation performed client-side is converting those geodetic
 * points into screen pixels. Radius/revision/reason are rendered verbatim from
 * the same SwarmOS frame; no formation geometry is reconstructed here.
 */
export function DispositionOverlay({
  projection,
  decision,
}: {
  projection: ConsoleProjection;
  decision: DispositionDecision | null;
}) {
  const projected = useMemo(() => {
    if (!decision) return null;
    const center = projection.project(decision.center);
    const assignments = decision.assignments.map((assignment) => ({
      assignment,
      point: projection.project(assignment.geo),
    }));
    return { center, assignments };
  }, [decision, projection]);

  if (!decision || !projected || projected.assignments.length === 0) return null;

  const screenRadius = Math.max(
    1,
    ...projected.assignments.map(({ point }) =>
      Math.hypot(point.x - projected.center.x, point.y - projected.center.y)
    )
  );
  const labelAt: ScreenPoint = {
    x: projected.center.x + screenRadius + 10,
    y: projected.center.y - screenRadius - 9,
  };

  return (
    <>
      <svg
        className="pointer-events-none absolute inset-0 z-[11] h-full w-full"
        aria-hidden="true"
        data-testid="disposition-overlay"
        data-disposition-revision={decision.revision}
        data-disposition-radius-m={decision.radius_m}
      >
        <circle
          cx={projected.center.x}
          cy={projected.center.y}
          r={screenRadius}
          fill="none"
          stroke="#7BE7FF"
          strokeWidth={1}
          strokeDasharray="2 6"
          opacity={0.24}
        />

        {projected.assignments.map(({ assignment, point }) => (
          <g
            key={`${decision.revision}:${assignment.group_id}:${assignment.role}:${assignment.agent_id}`}
            data-testid={`disposition-slot-${assignment.agent_id}`}
            data-role={assignment.role}
            data-mission-id={assignment.mission_id}
          >
            <line
              x1={projected.center.x}
              y1={projected.center.y}
              x2={point.x}
              y2={point.y}
              stroke="#7BE7FF"
              strokeWidth={0.8}
              strokeDasharray="1 7"
              opacity={0.18}
            />
            <circle
              cx={point.x}
              cy={point.y}
              r={5}
              fill="none"
              stroke="#7BE7FF"
              strokeWidth={1}
              opacity={0.7}
            />
            <path
              d={`M${point.x - 3} ${point.y} H${point.x + 3} M${point.x} ${point.y - 3} V${point.y + 3}`}
              stroke="#7BE7FF"
              strokeWidth={1}
              opacity={0.8}
            />
          </g>
        ))}
      </svg>

      <div
        className="pointer-events-none absolute z-20 font-mono text-[9px] uppercase tracking-[0.16em] text-orbital-blue/70"
        style={{ left: labelAt.x, top: labelAt.y, whiteSpace: "nowrap" }}
        data-testid="disposition-label"
      >
        SWARMOS DISP R{decision.revision} · {decision.reason.replaceAll("_", " ")} · R{" "}
        {decision.radius_m.toFixed(0)} M
      </div>
    </>
  );
}
