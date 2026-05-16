"use client";

/**
 * NextPatrol — next dispatch window from the primary dock.
 *
 * Phase 3: `DockState.primary` and `DockState.next_patrol_at` are server-issued
 * truth fields. When `next_patrol_at` is null the rail shows a quiet
 * placeholder — never invented numerals.
 */

import { useSwarm } from "@/lib/state";
import { IconPatrol } from "@/icons";
import { Eyebrow } from "./Eyebrow";

export function NextPatrol() {
  const { primaryDock } = useSwarm();
  const dock = primaryDock;
  const next = dock?.next_patrol_at ? new Date(dock.next_patrol_at) : null;

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Next patrol</Eyebrow>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-platinum">
          <IconPatrol size={28} />
        </span>
        <div className="flex flex-col">
          <span className="mono-num text-platinum text-lede">
            {next ? formatTime(next) : "—"}
          </span>
          <span className="eyebrow-mono">
            {next ? "scheduled · utc" : "no patrol scheduled"}
          </span>
        </div>
      </div>
      {dock && (
        <div className="grid grid-cols-2 gap-y-1 text-ui">
          <span className="eyebrow-mono">slots ready</span>
          <span className="text-right mono-num text-platinum">
            {String(dock.slots_available).padStart(3, "0")} /{" "}
            {String(dock.units_total).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">charging</span>
          <span className="text-right mono-num text-platinum">
            {String(dock.slots_charging).padStart(3, "0")}
          </span>
        </div>
      )}
    </div>
  );
}

function formatTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
