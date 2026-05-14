/**
 * UnitDetail — operator-grade view of a single unit.
 *
 * Functional additions beyond the static design-system mockup:
 *   - Live mission phase + progress.
 *   - Live GPS, altitude, velocity, link health.
 *   - Two operator actions: "Force RTL" and "Cancel mission" (sentence case,
 *     platinum-on-black primary; tertiary ghost). Wiring lands in the next
 *     commit — buttons currently emit `onAction` for the parent to handle.
 *
 * Voice respects the canon: sentence case, mono numerals, no exclamation,
 * em-dash cadence for pivots.
 */
import type { EventLog, FleetMember, Telemetry } from "@/lib/api";
import { agentStateToSwarm, type SwarmState } from "@/lib/tokens";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

type Props = {
  unit: FleetMember;
  telemetry?: Telemetry;
  events: EventLog[];
  onClose: () => void;
  onAction?: (action: "rtl" | "cancel") => void;
};

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return `${n} · ring-a`;
}

function fmtDeg(n: number, axis: "lat" | "lon"): string {
  const hemi = axis === "lat" ? (n >= 0 ? "N" : "S") : n >= 0 ? "E" : "W";
  return `${Math.abs(n).toFixed(3)}°${hemi}`;
}

function latestMissionProgress(
  agentId: string,
  events: EventLog[]
): { phase: string; progress: number; missionId: string } | null {
  // Scan from newest backwards for a progress event whose mission's award
  // we can match to this agent. Best-effort: backend doesn't carry agent_id
  // on `MissionProgress` yet — we infer by recency.
  void agentId;
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i];
    if (e.kind === "progress") {
      return {
        phase: ((e.phase as string) ?? "—").toLowerCase(),
        progress: (e.progress_pct as number) ?? 0,
        missionId: (e.mission_id as string) ?? "—",
      };
    }
  }
  return null;
}

export function UnitDetail({ unit, telemetry, events, onClose, onAction }: Props) {
  const state: SwarmState = agentStateToSwarm(unit.fsm_state);
  const tele = telemetry;
  const geo = tele?.geo ?? unit.geo;
  const link = ((tele?.link_quality ?? unit.link_quality ?? 1.0) * 100).toFixed(1);
  const mission = latestMissionProgress(unit.agent_id, events);

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

      {/* Identity row */}
      <div className="card p-3">
        <div className="flex items-baseline justify-between">
          <div className="flex flex-col">
            <span className="font-mono text-ui text-muted-silver tracking-eyebrow-mono uppercase">
              {unitLabel(unit.agent_id)}
            </span>
            <span className="eyebrow-mono mt-1">
              {unit.vendor} · {unit.model}
            </span>
          </div>
          <StatusPill state={state}>{unit.fsm_state}</StatusPill>
        </div>
      </div>

      {/* Telemetry stats */}
      <div className="card p-3">
        <Eyebrow mono>Telemetry</Eyebrow>
        <div className="mt-2 grid grid-cols-2 gap-y-2 font-mono text-ui">
          <span className="eyebrow-mono">Coordinates</span>
          <span className="text-platinum text-right mono-num">
            {fmtDeg(geo.lat, "lat")} · {fmtDeg(geo.lon, "lon")}
          </span>

          <span className="eyebrow-mono">Altitude</span>
          <span className="text-platinum text-right mono-num">
            {geo.alt_m.toFixed(0)} m
          </span>

          <span className="eyebrow-mono">Velocity</span>
          <span className="text-platinum text-right mono-num">
            {(tele?.velocity_mps ?? 0).toFixed(1)} m/s
          </span>

          <span className="eyebrow-mono">Battery</span>
          <span className="text-platinum text-right mono-num">
            {unit.battery_pct.toFixed(0)} %
          </span>

          <span className="eyebrow-mono">Link health</span>
          <span className="text-platinum text-right mono-num">{link} %</span>
        </div>
      </div>

      {/* Current mission */}
      <div className="card p-3">
        <Eyebrow mono>Current mission</Eyebrow>
        {mission ? (
          <div className="mt-2 flex flex-col gap-2">
            <div className="flex items-baseline justify-between">
              <span className="eyebrow-mono">id</span>
              <span className="mono-num text-platinum text-ui">
                {mission.missionId.slice(0, 8)}
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
                style={{ width: `${mission.progress}%` }}
              />
            </div>
            <span className="mono-num text-ash text-eyebrow text-right">
              {mission.progress.toFixed(0)} %
            </span>
          </div>
        ) : (
          <div className="mt-2 font-mono text-ui text-muted-silver">no mission. unit at rest.</div>
        )}
      </div>

      {/* Actions */}
      <div className="card p-3">
        <Eyebrow mono>Actions</Eyebrow>
        <div className="mt-2 flex flex-col gap-2">
          <button
            onClick={() => onAction?.("rtl")}
            className="bg-platinum text-absolute-black font-display font-medium text-ui px-3 py-2 rounded-input transition-all duration-press ease-swarm hover:brightness-110 active:scale-[0.98]"
            title="Force return to dock"
          >
            Force RTL
          </button>
          <button
            onClick={() => onAction?.("cancel")}
            className="bg-transparent text-platinum border border-graphite font-display font-medium text-ui px-3 py-2 rounded-input transition-all duration-press ease-swarm hover:brightness-110 active:scale-[0.98]"
            title="Cancel the unit's current mission"
          >
            Cancel mission
          </button>
          <span className="eyebrow-mono text-ash mt-1">
            actions are advisory in this session.
          </span>
        </div>
      </div>
    </div>
  );
}
