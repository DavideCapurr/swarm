/**
 * FleetGrid — the units panel from spread 24.
 *
 * Top: three mono stat rows (units online · link health · attention).
 * Then: per-unit list with state dot + label.
 * Reads from Phase 1 `UnitState[]` + `AnomalyView[]`.
 */
import type { AnomalyView, UnitState } from "@/lib/api";
import { agentStateToSwarm } from "@/lib/tokens";
import { Eyebrow } from "./Eyebrow";

type Props = {
  units: UnitState[];
  anomalies: AnomalyView[];
  onSelect?: (agentId: string) => void;
};

const STATE_DOT_CLASS: Record<string, string> = {
  rest: "dot dot-rest",
  connected: "dot dot-connected",
  operational: "dot dot-operational",
  attention: "dot dot-attention",
};

const STATE_LABEL: Record<string, string> = {
  rest: "REST",
  connected: "LNK",
  operational: "OP",
  attention: "ATT",
};

const STATE_TEXT_CLASS: Record<string, string> = {
  rest: "text-muted-silver",
  connected: "text-orbital-blue",
  operational: "text-signal-green",
  attention: "text-launch-amber",
};

function avgLink(units: UnitState[]): number {
  if (!units.length) return 0;
  const sum = units.reduce((s, u) => s + (u.link_quality ?? 1), 0);
  return Math.round((sum / units.length) * 1000) / 10;
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return `${n} · ring-a`;
}

export function FleetGrid({ units, anomalies, onSelect }: Props) {
  const onlineCount = units.filter((u) => u.fsm_state !== "OFFLINE").length;
  const totalCount = units.length;
  const link = avgLink(units);
  const attentionUnit = units.find((u) => agentStateToSwarm(u.fsm_state) === "attention");
  const unverifiedAnomaly = anomalies.find(
    (a) => a.state === "pending" || a.state === "verifying"
  );

  return (
    <div className="flex flex-col gap-3">
      <Eyebrow mono>Fleet</Eyebrow>

      <div className="flex flex-col">
        <StatRow
          value={`${String(onlineCount).padStart(3, "0")} / ${String(totalCount).padStart(3, "0")}`}
          label="online"
        />
        <StatRow value={`${link.toFixed(1)} %`} label="link health" />
        {attentionUnit && (
          <StatRow
            value={`unit ${unitLabel(attentionUnit.agent_id).split(" ·")[0]}`}
            label="attention"
          />
        )}
        {unverifiedAnomaly && (
          <StatRow
            value={`c ${unverifiedAnomaly.confidence.toFixed(2)}`}
            label="anomaly · pending"
          />
        )}
      </div>

      <Eyebrow mono className="mt-2">
        Units
      </Eyebrow>
      <div className="flex flex-col">
        {units.length === 0 && (
          <div className="text-muted-silver text-ui font-mono py-6 text-center">
            no units online.
          </div>
        )}
        {units.map((u) => {
          const state = agentStateToSwarm(u.fsm_state);
          return (
            <button
              key={u.agent_id}
              onClick={() => onSelect?.(u.agent_id)}
              className="flex items-center justify-between py-2 border-b border-gunmetal text-left transition-all duration-press ease-swarm hover:brightness-125 active:scale-[0.99] focus:outline-none focus-visible:bg-graphite/40"
            >
              <span className="font-mono text-ui text-muted-silver tracking-eyebrow-mono uppercase">
                {unitLabel(u.agent_id)}
              </span>
              <span
                className={`flex items-center gap-2 font-mono text-eyebrow tracking-eyebrow uppercase ${STATE_TEXT_CLASS[state]}`}
              >
                <span className={STATE_DOT_CLASS[state]} />
                {STATE_LABEL[state]}
                <span className="text-ash mono-num ml-1">{u.battery_pct.toFixed(0)}%</span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function StatRow({ value, label }: { value: string; label: string }) {
  return (
    <div className="flex items-end justify-between py-2 border-b border-gunmetal">
      <span className="mono-num text-platinum text-lede">{value}</span>
      <span className="eyebrow-mono">{label}</span>
    </div>
  );
}
