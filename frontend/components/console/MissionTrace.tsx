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
 * ADAPTED stays inactive on a mission that never needed adapting. That is the
 * point of it being there: when an executor drops out and SwarmOS puts spare
 * capacity into the vacated role, this is where the recording shows that the
 * system did something a fleet without central authority could not.
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
        <span className="font-grotesk text-[9.5px] font-medium uppercase leading-none tracking-[0.22em] text-ash">
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
                  background: i === 0 ? "transparent" : stage.state === "pending" ? "#2A3138" : "#7BE7FF",
                  opacity: stage.state === "pending" ? 1 : 0.45,
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
                      : stages[i + 1].state === "pending"
                        ? "#2A3138"
                        : "#7BE7FF",
                  opacity: i === stages.length - 1 || stages[i + 1].state === "pending" ? 1 : 0.45,
                }}
              />
            </div>

            <span
              className={`mt-[9px] text-center font-grotesk text-[8.5px] font-medium uppercase leading-none tracking-[0.12em] ${
                stage.state === "pending"
                  ? "text-ash/55"
                  : stage.state === "active"
                    ? "text-orbital-blue"
                    : "text-platinum"
              }`}
            >
              {stage.name}
            </span>

            <span className="mt-[6px] text-center font-mono text-[8.5px] tabular-nums leading-none tracking-[0.06em] text-ash/70">
              {stampOf(stage.at)}
            </span>
          </div>
        ))}
      </div>
    </Surface>
  );
}

function Node({ state }: { state: TraceStage["state"] }) {
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
