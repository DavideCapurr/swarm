"use client";

/**
 * RiskState — the awareness risk posture as a rail card.
 *
 * Reads `AwarenessBreakdown.risk_state` server-side (rest / aware /
 * elevated). No red — elevated stays amber per PDF §5.2.
 */

import { useSwarm } from "@/lib/state";
import { RISK_STATE_COPY } from "@/lib/copy";
import { IconRisk } from "@/icons";
import { Eyebrow } from "./Eyebrow";

const ACCENT_CLASS: Record<"ash" | "orbital-blue" | "launch-amber", string> = {
  ash: "text-muted-silver",
  "orbital-blue": "text-orbital-blue",
  "launch-amber": "text-launch-amber",
};

const NARRATIVE: Record<"rest" | "aware" | "elevated", string> = {
  rest: "territory at rest. coverage steady.",
  aware: "patrol in flight. coverage refreshing.",
  elevated: "sector needs verification. operator decision possible.",
};

export function RiskState() {
  const { awareness } = useSwarm();
  const meta = RISK_STATE_COPY[awareness.risk_state];
  const accent = ACCENT_CLASS[meta.accent];
  const narrative = NARRATIVE[awareness.risk_state];
  const uncovered = awareness.blind_spot_sectors.length;
  const needsRefresh = awareness.stale_sectors.length;
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Risk state</Eyebrow>
        <span className={`eyebrow-mono ${accent}`}>{meta.label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className={accent}>
          <IconRisk size={28} />
        </span>
        <div className="flex flex-col">
          <span className="mono-num text-platinum text-lede">
            {String(Math.round(awareness.score)).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">coverage · %</span>
        </div>
      </div>
      <span className="eyebrow-mono text-ash">{narrative}</span>
      {(uncovered > 0 || needsRefresh > 0) && (
        <div className="grid grid-cols-2 gap-y-1 text-ui">
          <span className="eyebrow-mono">uncovered</span>
          <span className="text-right mono-num text-platinum">
            {String(uncovered).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">needs refresh</span>
          <span className="text-right mono-num text-platinum">
            {String(needsRefresh).padStart(3, "0")}
          </span>
        </div>
      )}
    </div>
  );
}
