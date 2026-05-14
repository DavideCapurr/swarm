/**
 * DockCard — the dock as infrastructural node. Spec §3.3.
 *
 * Power, charging slots, units ready/charging, weather lock.
 * Quiet: no decorative color, accents only when something activates.
 */
import type { FleetMember } from "@/lib/api";
import { Eyebrow } from "./Eyebrow";

type Props = {
  fleet: FleetMember[];
};

function nextPatrolWindow(): string {
  // The orchestrator doesn't yet emit a patrol schedule; derive a quiet
  // placeholder anchored to the next quarter-hour. Mono, fixed columns.
  const d = new Date();
  d.setMinutes(Math.ceil((d.getMinutes() + 1) / 15) * 15, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function DockCard({ fleet }: Props) {
  const total = fleet.length;
  const docked = fleet.filter((f) => f.fsm_state === "DOCKED").length;
  const ready = fleet.filter((f) => f.fsm_state === "DOCKED" && f.battery_pct >= 80).length;
  const charging = fleet.filter(
    (f) => f.fsm_state === "DOCKED" && f.battery_pct < 80
  ).length;
  const avgBattery = total
    ? fleet.reduce((s, f) => s + f.battery_pct, 0) / total
    : 0;

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Dock · 001</Eyebrow>
        <span className="eyebrow-mono text-signal-green">power stable</span>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">units ready</span>
        <span className="text-right mono-num text-platinum">
          {String(ready).padStart(3, "0")} / {String(total).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">charging</span>
        <span className="text-right mono-num text-platinum">
          {String(charging).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">battery pool</span>
        <span className="text-right mono-num text-platinum">
          {avgBattery.toFixed(0)} %
        </span>

        <span className="eyebrow-mono">weather lock</span>
        <span className="text-right eyebrow-mono text-signal-green">clear</span>

        <span className="eyebrow-mono">next patrol</span>
        <span className="text-right mono-num text-platinum">{nextPatrolWindow()}</span>
      </div>

      <div className="h-px bg-gunmetal" />

      <span className="eyebrow-mono text-ash">
        {String(docked).padStart(3, "0")} on pad · local compute nominal
      </span>
    </div>
  );
}
