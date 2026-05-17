"use client";

/**
 * DockDetail — the system page's dock readout.
 *
 * Operator-grade view of one DockState: status, slots, power, weather, next
 * patrol. No invented numerals — fields render "—" until the server emits
 * them.
 */

import type { DockState } from "@/lib/api";
import { IconDock } from "@/icons";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

const STATUS_STATE: Record<
  DockState["status"],
  "rest" | "connected" | "operational" | "attention"
> = {
  online: "operational",
  degraded: "attention",
  offline: "attention",
  maintenance: "attention",
};

const POWER_STATE: Record<
  DockState["power_status"],
  "rest" | "connected" | "operational" | "attention"
> = {
  online: "operational",
  degraded: "attention",
  offline: "attention",
};

export function DockDetail({ dock }: { dock: DockState }) {
  const next = dock.next_patrol_at ? new Date(dock.next_patrol_at) : null;
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Dock · {dock.dock_id}</Eyebrow>
        <StatusPill state={STATUS_STATE[dock.status]}>{dock.status}</StatusPill>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-platinum">
          <IconDock size={28} />
        </span>
        <div className="flex flex-col">
          <span className="mono-num text-platinum text-lede">
            {String(dock.slots_available).padStart(3, "0")} /{" "}
            {String(dock.units_total).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">slots ready · total</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">docked</span>
        <span className="text-right mono-num text-platinum">
          {String(dock.units_docked).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">charging</span>
        <span className="text-right mono-num text-platinum">
          {String(dock.slots_charging).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">power</span>
        <span className="text-right">
          <StatusPill state={POWER_STATE[dock.power_status]}>
            {dock.power_status}
          </StatusPill>
        </span>

        <span className="eyebrow-mono">weather</span>
        <span
          className={`text-right eyebrow-mono ${
            dock.weather_lock ? "text-launch-amber" : "text-signal-green"
          }`}
        >
          {dock.weather_lock ? "hold" : "clear"}
        </span>

        <span className="eyebrow-mono">wind</span>
        <span className="text-right mono-num text-platinum">
          {dock.wind_mps != null ? `${dock.wind_mps.toFixed(1)} m/s` : "—"}
        </span>

        <span className="eyebrow-mono">visibility</span>
        <span className="text-right mono-num text-platinum">
          {dock.visibility_km != null ? `${dock.visibility_km.toFixed(1)} km` : "—"}
        </span>

        <span className="eyebrow-mono">temp</span>
        <span className="text-right mono-num text-platinum">
          {dock.temp_c != null ? `${dock.temp_c.toFixed(0)} °C` : "—"}
        </span>

        <span className="eyebrow-mono">next patrol</span>
        <span className="text-right mono-num text-platinum">
          {next ? formatTime(next) : "—"}
        </span>
      </div>
    </div>
  );
}

function formatTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}
