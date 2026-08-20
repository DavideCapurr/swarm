"use client";

/**
 * MissionTrace — the lifecycle of the focused objective, as a causal sequence.
 *
 * Not a log. A YC viewer should not have to read a developer console to follow
 * what happened, so five stages carry the whole story and each one is either
 * reached or not:
 *
 *   OBJECTIVE → COMPOSED → EXECUTING → ADAPTED → VERIFIED
 *
 * ADAPTED reads NOT REQUIRED, not a dim pending dot, on a mission that never
 * needed adapting — it is a conditional stage, not a queued one, and the
 * distinction matters on screen: a viewer who has never seen this product
 * should not read a clean mission as one with an unfinished step. That is
 * also what makes the failure demo land. When an executor drops out and
 * SwarmOS puts spare capacity into the vacated role, NOT REQUIRED becomes
 * ADAPTING becomes ADAPTED, live — a capability the mission did not need
 * until suddenly it did.
 */

import type { TraceStage } from "@/lib/authority";

import { HAIRLINE, Mono, Surface } from "./Surface";

export const TRACE_WIDTH = 468;

function stampOf(at: string | null): string {
  if (!at) return "";
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(11, 19);
}

export function MissionTrace({
  stages,
  objectiveLabel,
}: {
  stages: TraceStage[];
  objectiveLabel: string | null;
}) {
  return (
    <Surface
      data-testid="mission-trace"
      className="pointer-events-auto"
      style={{ width: TRACE_WIDTH }}
    >
      <div
        className="flex items-center justify-between px-3 py-[7px]"
        style={{ borderBottom: `1px solid ${HAIRLINE}` }}
      >
        <span className="font-grotesk text-[9.5px] font-medium leading-none tracking-[0.03em] text-ash">
          mission trace
        </span>
        <Mono size={9.5} tone="ash">
          {objectiveLabel ?? "—"}
        </Mono>
      </div>

      <div className="flex items-start px-3 pb-[11px] pt-[12px]">
        {stages.map((stage, i) => (
          <div key={stage.name} className="flex min-w-0 flex-1 flex-col">
            {/* Track and node share one row so the connector meets the node
                centre exactly at every width. */}
            <div className="flex items-center">
              <span
                aria-hidden="true"
                className="h-px flex-1"
                style={{
                  background:
                    i === 0
                      ? "transparent"
                      : stage.state === "pending" || stage.state === "not_required"
                        ? "#2A3138"
                        : "#7BE7FF",
                  opacity: stage.state === "pending" || stage.state === "not_required" ? 1 : 0.45,
                }}
              />
              <Node state={stage.state} />
              <span
                aria-hidden="true"
                className="h-px flex-1"
                style={{
                  background:
                    i === stages.length - 1
                      ? "transparent"
                      : stages[i + 1].state === "pending" || stages[i + 1].state === "not_required"
                        ? "#2A3138"
                        : "#7BE7FF",
                  opacity:
                    i === stages.length - 1 ||
                    stages[i + 1].state === "pending" ||
                    stages[i + 1].state === "not_required"
                      ? 1
                      : 0.45,
                }}
              />
            </div>

            <span
              className={`mt-[9px] text-center font-grotesk text-[10px] font-medium uppercase leading-none tracking-[0.06em] ${
                stage.state === "not_required"
                  ? "text-ash/35"
                  : stage.state === "pending"
                    ? "text-ash/55"
                    : stage.state === "active"
                      ? "text-orbital-blue"
                      : "text-platinum"
              }`}
            >
              {stage.name}
            </span>

            <span className="mt-[6px] text-center font-console-mono text-[9px] tabular-nums leading-none tracking-[0.06em] text-ash/70">
              {stage.state === "not_required" ? "NOT REQUIRED" : stampOf(stage.at)}
            </span>
          </div>
        ))}
      </div>
    </Surface>
  );
}

function Node({ state }: { state: TraceStage["state"] }) {
  if (state === "not_required") {
    // A dash, not a ring: the hollow pending circle reads as "not reached
    // yet", which is wrong for a stage nothing was ever owed. This is a
    // closed question, held open only by the live possibility of failure.
    return (
      <span
        aria-hidden="true"
        className="mx-[3px] block h-[1.5px] w-[9px] shrink-0 rounded-full bg-graphite"
      />
    );
  }
  if (state === "done") {
    return (
      <span
        aria-hidden="true"
        className="mx-[3px] block h-[7px] w-[7px] shrink-0 rounded-full bg-orbital-blue"
      />
    );
  }
  if (state === "active") {
    return (
      <span
        aria-hidden="true"
        className="mx-[3px] block h-[7px] w-[7px] shrink-0 rounded-full border border-orbital-blue bg-absolute-black"
        style={{ boxShadow: "0 0 0 3px rgba(123, 231, 255, 0.16)" }}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className="mx-[3px] block h-[7px] w-[7px] shrink-0 rounded-full border border-graphite"
    />
  );
}
