/**
 * AnomalyCard — confidence-language anomaly readout. Spec §3.5.
 *
 * Voice: never absolute ("intruder detected"). Always confidence-bounded
 * ("low-confidence thermal change · unit dispatched · sector verifying").
 */
import type { Anomaly, FleetMember } from "@/lib/api";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

type Props = {
  anomaly: Anomaly;
  verifier?: FleetMember;
};

function confidenceLabel(c: number): string {
  if (c >= 0.85) return "verified hotspot";
  if (c >= 0.65) return "medium-confidence anomaly";
  if (c >= 0.4) return "low-confidence anomaly";
  return "unresolved pattern";
}

function kindCopy(kind: string): string {
  switch ((kind ?? "").toLowerCase()) {
    case "smoke":
      return "thermal irregularity";
    case "intruder":
      return "movement pattern";
    case "vehicle":
      return "unscheduled vehicle";
    default:
      return kind.toLowerCase() || "unknown signal";
  }
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return n;
}

export function AnomalyCard({ anomaly, verifier }: Props) {
  const conf = anomaly.confidence;
  const state = anomaly.verified ? "operational" : "attention";
  const action = anomaly.verified
    ? "verified · awaiting acknowledgement"
    : verifier
      ? `unit ${unitLabel(verifier.agent_id)} verifying`
      : "verification pending";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Anomaly · {anomaly.id.slice(0, 4)}</Eyebrow>
        <StatusPill state={state}>{anomaly.verified ? "verified" : "verifying"}</StatusPill>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">type</span>
        <span className="text-right eyebrow-mono text-platinum">{kindCopy(anomaly.kind)}</span>

        <span className="eyebrow-mono">confidence</span>
        <span className="text-right mono-num text-platinum">
          {String(Math.round(conf * 100)).padStart(3, "0")} %
        </span>

        <span className="eyebrow-mono">read</span>
        <span className="text-right eyebrow-mono text-launch-amber">
          {confidenceLabel(conf)}
        </span>

        <span className="eyebrow-mono">sector</span>
        <span className="text-right mono-num text-platinum">
          {anomaly.geo.lat.toFixed(3)}°n · {anomaly.geo.lon.toFixed(3)}°e
        </span>

        <span className="eyebrow-mono">action</span>
        <span className="text-right eyebrow-mono text-orbital-blue">{action}</span>
      </div>
    </div>
  );
}
