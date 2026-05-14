/**
 * FleetGrid — the units panel from spread 24.
 *
 * Top: three mono stat rows (units online · link health · t-minus).
 * Then: per-unit list with state dot + label.
 * SWARM voice rules: sentence case in copy, mono in numbers, no exclamation.
 */
import type { Anomaly, FleetMember } from "@/lib/api";
import { agentStateToSwarm } from "@/lib/tokens";
import { Eyebrow } from "./Eyebrow";

type Props = {
  fleet: FleetMember[];
  anomalies: Anomaly[];
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

function avgLink(fleet: FleetMember[]): number {
  if (!fleet.length) return 0;
  const sum = fleet.reduce((s, f) => s + (f.link_quality ?? 1), 0);
  return Math.round((sum / fleet.length) * 1000) / 10; // one decimal
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return `${n} · ring-a`;
}

export function FleetGrid({ fleet, anomalies, onSelect }: Props) {
  const onlineCount = fleet.filter((f) => f.fsm_state !== "OFFLINE").length;
  const totalCount = fleet.length;
  const link = avgLink(fleet);
  const attentionUnit = fleet.find((f) => agentStateToSwarm(f.fsm_state) === "attention");
  const unverifiedAnomaly = anomalies.find((a) => !a.verified);

  return (
    <div className="flex flex-col gap-3">
      <Eyebrow>Fleet</Eyebrow>

      {/* ── Stat rows (mono, padded) ─────────────────────────────────────── */}
      <div className="flex flex-col">
        <StatRow
          value={`${String(onlineCount).padStart(3, "0")} / ${String(totalCount).padStart(3, "0")}`}
          label="online"
        />
        <StatRow value={`${link.toFixed(1)} %`} label="link health" />
        <StatRow
          value={attentionUnit ? `unit ${unitLabel(attentionUnit.agent_id).split(" ·")[0]}` : "—"}
          label="attention"
        />
        <StatRow
          value={unverifiedAnomaly ? `c ${unverifiedAnomaly.confidence.toFixed(2)}` : "—"}
          label="anomaly · pending"
        />
      </div>

      {/* ── Anomalies ────────────────────────────────────────────────────── */}
      {anomalies.length > 0 && (
        <>
          <Eyebrow className="mt-2">Anomalies</Eyebrow>
          <div className="flex flex-col">
            {anomalies.slice(0, 4).map((a) => (
              <div
                key={a.id}
                className="flex items-center justify-between py-2 border-b border-gunmetal"
              >
                <span className="font-mono text-ui text-muted-silver tracking-eyebrow-mono uppercase">
                  {(a.kind ?? "smoke").toString().toLowerCase()} · c {a.confidence.toFixed(2)}
                </span>
                <span
                  className={`flex items-center gap-2 font-mono text-eyebrow tracking-eyebrow uppercase ${
                    a.verified ? "text-signal-green" : "text-launch-amber"
                  }`}
                >
                  <span
                    className={a.verified ? "dot dot-operational" : "dot dot-attention"}
                  />
                  {a.verified ? "verified" : "pending"}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── Units list ───────────────────────────────────────────────────── */}
      <Eyebrow className="mt-2">Units</Eyebrow>
      <div className="flex flex-col">
        {fleet.length === 0 && (
          <div className="text-mutedSilver text-ui font-mono py-6 text-center">
            no units online.
          </div>
        )}
        {fleet.map((m) => {
          const state = agentStateToSwarm(m.fsm_state);
          return (
            <button
              key={m.agent_id}
              onClick={() => onSelect?.(m.agent_id)}
              className="flex items-center justify-between py-2 border-b border-gunmetal text-left transition-all duration-press ease-swarm hover:brightness-125 active:scale-[0.99] focus:outline-none focus-visible:bg-graphite/40"
            >
              <span className="font-mono text-ui text-muted-silver tracking-eyebrow-mono uppercase">
                {unitLabel(m.agent_id)}
              </span>
              <span
                className={`flex items-center gap-2 font-mono text-eyebrow tracking-eyebrow uppercase ${STATE_TEXT_CLASS[state]}`}
              >
                <span className={STATE_DOT_CLASS[state]} />
                {STATE_LABEL[state]}
                <span className="text-ash mono-num ml-1">{m.battery_pct.toFixed(0)}%</span>
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
      <span className="mono-num text-platinum" style={{ fontSize: 17 }}>
        {value}
      </span>
      <span className="eyebrow-mono">{label}</span>
    </div>
  );
}
