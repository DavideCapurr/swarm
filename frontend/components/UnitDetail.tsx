/**
 * UnitDetail — operator-grade view of a single unit.
 *
 * Functional reads from `UnitState` + the latest `MissionView` for the agent.
 * No manual drone commands — actions are intents only ("Return unit" routes
 * through `dispatch("return", ...)`).
 */
"use client";

import type { MissionView, UnitState } from "@/lib/api";
import { useSwarm } from "@/lib/state";
import { agentStateToSwarm, type SwarmState } from "@/lib/tokens";
import { AGENT_STATE_COPY, UNIT_LABEL_RING } from "@/lib/copy";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

type Props = {
  unit: UnitState;
  onClose: () => void;
};

function fmtDeg(n: number, axis: "lat" | "lon"): string {
  const hemi = axis === "lat" ? (n >= 0 ? "N" : "S") : n >= 0 ? "E" : "W";
  return `${Math.abs(n).toFixed(3)}°${hemi}`;
}

function missionFor(missions: MissionView[], agent: string): MissionView | null {
  return missions.find((m) => m.assigned_agent === agent) ?? null;
}

export function UnitDetail({ unit, onClose }: Props) {
  const state: SwarmState = agentStateToSwarm(unit.fsm_state);
  const { missions, dispatch } = useSwarm();
  const mission = missionFor(missions, unit.agent_id);

  const onReturn = () => {
    void dispatch("return", `unit:${unit.agent_id}`);
  };

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-baseline justify-between">
        <Eyebrow>Unit · selected</Eyebrow>
        <button
          onClick={onClose}
          className="eyebrow text-muted-silver hover:text-platinum transition-colors duration-press ease-swarm"
        >
          back to fleet
        </button>
      </div>

      <div className="card p-3">
        <div className="flex items-baseline justify-between">
          <div className="flex flex-col">
            <span className="font-mono text-ui text-muted-silver tracking-eyebrow-mono">
              {UNIT_LABEL_RING(unit.agent_id)}
            </span>
            <span className="eyebrow-mono mt-1">
              {AGENT_STATE_COPY[unit.fsm_state].verb}
            </span>
          </div>
          <StatusPill state={state}>
            {AGENT_STATE_COPY[unit.fsm_state].verb}
          </StatusPill>
        </div>
      </div>

      <div className="card p-3">
        <Eyebrow mono>Telemetry</Eyebrow>
        <div className="mt-2 grid grid-cols-2 gap-y-2 font-mono text-ui">
          <span className="eyebrow-mono">Coordinates</span>
          <span className="text-platinum text-right mono-num">
            {fmtDeg(unit.geo.lat, "lat")} · {fmtDeg(unit.geo.lon, "lon")}
          </span>

          <span className="eyebrow-mono">Altitude</span>
          <span className="text-platinum text-right mono-num">
            {unit.altitude_agl_m.toFixed(0)} m
          </span>

          <span className="eyebrow-mono">Heading</span>
          <span className="text-platinum text-right mono-num">
            {unit.heading_deg.toFixed(0).padStart(3, "0")}°
          </span>

          <span className="eyebrow-mono">Battery</span>
          <span className="text-platinum text-right mono-num">
            {unit.battery_pct.toFixed(0)} %
          </span>

          <span className="eyebrow-mono">Link health</span>
          <span className="text-platinum text-right mono-num">
            {(unit.link_quality * 100).toFixed(1)} %
          </span>
        </div>
      </div>

      <div className="card p-3">
        <Eyebrow mono>Current mission</Eyebrow>
        {mission ? (
          <div className="mt-2 flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <span className="eyebrow-mono">id</span>
              <span className="mono-num text-platinum text-ui">
                {mission.id.slice(0, 8)}
              </span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="eyebrow-mono">phase</span>
              <span className="font-mono uppercase tracking-eyebrow text-eyebrow text-signal-green">
                {mission.phase}
              </span>
            </div>
            <div className="relative h-1 bg-gunmetal overflow-hidden rounded-chip mt-1">
              <div
                className="absolute inset-y-0 left-0 bg-signal-green transition-all duration-connect ease-swarm"
                style={{ width: `${mission.progress_pct}%` }}
              />
            </div>
            <span className="mono-num text-ash text-eyebrow text-right">
              {mission.progress_pct.toFixed(0)} %
            </span>
          </div>
        ) : (
          <div className="mt-2 font-mono text-ui text-muted-silver">
            no mission. unit at rest.
          </div>
        )}
      </div>

      <div className="card p-3">
        <Eyebrow mono>Intents</Eyebrow>
        <div className="mt-2 flex flex-col gap-2">
          <button
            onClick={onReturn}
            className="bg-platinum text-absolute-black font-display font-medium text-ui px-3 py-2 rounded-input transition-all duration-press ease-swarm hover:brightness-110 active:scale-[0.98]"
            title="Return this unit to its dock"
          >
            Return unit
          </button>
          <span className="eyebrow-mono text-ash mt-1">
            intent only — swarmos confirms via the operator command bus.
          </span>
        </div>
      </div>
    </div>
  );
}
