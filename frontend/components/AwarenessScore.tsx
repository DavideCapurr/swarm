/**
 * AwarenessScore — the synthetic indicator of how up-to-date and trustworthy
 * SWARM's model of the territory is. Derived from coverage freshness, sensor
 * confidence, unit readiness, open anomalies and link health. Spec §3.4.
 */
import { Eyebrow } from "./Eyebrow";

type Props = {
  awareness: number;          // 0..100
  units: { online: number; total: number };
  pendingAnomalies: number;
  linkHealth: number;         // 0..100
};

function bucket(score: number): "operational" | "connected" | "attention" {
  if (score >= 80) return "operational";
  if (score >= 60) return "connected";
  return "attention";
}

const TEXT_CLASS: Record<string, string> = {
  operational: "text-signal-green",
  connected: "text-orbital-blue",
  attention: "text-launch-amber",
};

export function AwarenessScore({ awareness, units, pendingAnomalies, linkHealth }: Props) {
  const state = bucket(awareness);
  const label =
    state === "operational"
      ? "model coherent"
      : state === "connected"
        ? "model stale in zones"
        : "verification required";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <Eyebrow mono>Territory awareness</Eyebrow>

      <div className="flex items-baseline gap-3">
        <span className={`mono-num font-medium ${TEXT_CLASS[state]}`} style={{ fontSize: 44, lineHeight: 1 }}>
          {String(Math.round(awareness)).padStart(3, "0")}
        </span>
        <span className="eyebrow-mono">%</span>
      </div>

      <div className="h-px bg-gunmetal" />

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">model state</span>
        <span className={`text-right eyebrow-mono ${TEXT_CLASS[state]}`}>{label}</span>

        <span className="eyebrow-mono">units ready</span>
        <span className="text-right mono-num text-platinum">
          {String(units.online).padStart(3, "0")} / {String(units.total).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">open anomalies</span>
        <span className="text-right mono-num text-platinum">
          {String(pendingAnomalies).padStart(3, "0")}
        </span>

        <span className="eyebrow-mono">link health</span>
        <span className="text-right mono-num text-platinum">{linkHealth.toFixed(1)} %</span>
      </div>
    </div>
  );
}
