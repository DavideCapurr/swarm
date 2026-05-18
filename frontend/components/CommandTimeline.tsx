"use client";

/**
 * CommandTimeline — recent operator intents with lifecycle status.
 *
 * Phase 3 surfaces the full `submitted → accepted → in_flight → completed`
 * progression for every operator command. Reads `commands` from `useSwarm()`;
 * never invents lifecycle state. Numerals padded per design system spread 14
 * (telemetry). Status uses the eyebrow tier (spread 13) and maps to the
 * activation accents from spread 09: orbital blue for focus, signal green
 * for operational/confirmed, launch amber for attention.
 */

import { useSwarm } from "@/lib/state";
import type { CommandStatus, OperatorCommand } from "@/lib/api";
import { Eyebrow } from "./Eyebrow";

const STATUS_CLASS: Record<CommandStatus, string> = {
  submitted: "text-ash",
  accepted: "text-orbital-blue",
  in_flight: "text-signal-green",
  completed: "text-signal-green",
  rejected: "text-launch-amber",
  timed_out: "text-launch-amber",
};

const ACTION_LABEL: Record<OperatorCommand["action"], string> = {
  verify: "Verify",
  hold_patrol: "Hold patrol",
  dismiss: "Dismiss",
  return: "Return unit",
  increase_scan_freq: "Increase scan",
  mark_known: "Mark known",
  escalate: "Escalate",
  export_report: "Export report",
  emergency_rtl_all: "Return all units",
};

export function CommandTimeline({ limit = 5 }: { limit?: number }) {
  const { commands } = useSwarm();
  const recent = [...commands]
    .sort((a, b) => (a.submitted_at < b.submitted_at ? 1 : -1))
    .slice(0, limit);

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Operator timeline</Eyebrow>
        <span className="eyebrow-mono">
          <span className="mono-num">{String(commands.length).padStart(3, "0")}</span>
          {" · session"}
        </span>
      </div>
      {recent.length === 0 ? (
        <span className="eyebrow-mono text-ash">territory under awareness · no operator intent yet</span>
      ) : (
        <ul className="flex flex-col gap-2">
          {recent.map((c) => (
            <li
              key={c.id}
              className="grid grid-cols-[120px_1fr_92px] items-baseline gap-3 text-ui"
            >
              <span className="font-display text-platinum truncate">
                {ACTION_LABEL[c.action]}
              </span>
              <span className="eyebrow-mono truncate">{c.target}</span>
              <span
                className={`text-right font-mono uppercase tracking-eyebrow text-eyebrow ${STATUS_CLASS[c.status]}`}
              >
                {c.status.replace("_", " ")}
                {c.rejected_reason ? ` · ${c.rejected_reason}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
