"use client";

/**
 * UnitReadiness — system page row: one unit's readiness.
 *
 * Reads UnitState fields only. Confidence-bound copy; no panic language.
 * Shows fsm state, battery, link health, current sector, mission id.
 */

import type { UnitState } from "@/lib/api";
import { IconUnit } from "@/icons";
import { agentStateToSwarm } from "@/lib/tokens";
import { StatusPill } from "./StatusPill";

export function UnitReadiness({ unit }: { unit: UnitState }) {
  const state = agentStateToSwarm(unit.fsm_state);
  const ll = `${unit.geo.lat.toFixed(3)}°n · ${unit.geo.lon.toFixed(3)}°e`;
  return (
    <div className="card p-4 flex flex-col gap-2">
      <div className="flex items-baseline justify-between">
        <div className="flex items-center gap-3">
          <span className="text-platinum">
            <IconUnit size={20} />
          </span>
          <span className="font-mono text-ui text-platinum tracking-eyebrow-mono uppercase">
            unit {unitLabel(unit.agent_id)}
          </span>
        </div>
        <StatusPill state={state}>{unit.fsm_state}</StatusPill>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">vendor · model</span>
        <span className="text-right eyebrow-mono text-platinum">
          {unit.vendor} · {unit.model}
        </span>

        <span className="eyebrow-mono">battery</span>
        <span className="text-right mono-num text-platinum">
          {unit.battery_pct.toFixed(0)} %
        </span>

        <span className="eyebrow-mono">link · q</span>
        <span className="text-right mono-num text-platinum">
          {(unit.link_quality * 100).toFixed(0)} %
        </span>

        <span className="eyebrow-mono">altitude</span>
        <span className="text-right mono-num text-platinum">
          {unit.altitude_agl_m.toFixed(0)} m
        </span>

        <span className="eyebrow-mono">heading</span>
        <span className="text-right mono-num text-platinum">
          {unit.heading_deg.toFixed(0).padStart(3, "0")}°
        </span>

        <span className="eyebrow-mono">sector</span>
        <span className="text-right mono-num text-platinum">
          {unit.current_sector_id ?? "—"}
        </span>

        <span className="eyebrow-mono">mission</span>
        <span className="text-right mono-num text-platinum">
          {unit.current_mission_id ? unit.current_mission_id.slice(0, 8) : "—"}
        </span>

        <span className="eyebrow-mono">position</span>
        <span className="text-right mono-num text-platinum">{ll}</span>
      </div>
    </div>
  );
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  return m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
}
