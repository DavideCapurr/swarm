"use client";

/**
 * RiskState — the awareness risk posture as a rail card.
 *
 * Reads `AwarenessBreakdown.risk_state` server-side (rest / aware /
 * elevated). No red — elevated stays amber per PDF §5.2.
 */

import { useSwarm } from "@/lib/state";
import { IconRisk } from "@/icons";
import { Eyebrow } from "./Eyebrow";

const COPY: Record<"rest" | "aware" | "elevated", { label: string; text: string; copy: string }> = {
  rest: { label: "rest", text: "text-muted-silver", copy: "territory at rest · awareness nominal" },
  aware: { label: "aware", text: "text-orbital-blue", copy: "active patrol · awareness refreshing" },
  elevated: {
    label: "elevated",
    text: "text-launch-amber",
    copy: "sector requires verification · escalation possible",
  },
};

export function RiskState() {
  const { awareness } = useSwarm();
  const meta = COPY[awareness.risk_state];
  const blind = awareness.blind_spot_sectors.length;
  const stale = awareness.stale_sectors.length;
  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Risk state</Eyebrow>
        <span className={`eyebrow-mono ${meta.text}`}>{meta.label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className={meta.text}>
          <IconRisk size={28} />
        </span>
        <div className="flex flex-col">
          <span className="mono-num text-platinum text-lede">
            {String(Math.round(awareness.score)).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">awareness · %</span>
        </div>
      </div>
      <span className="eyebrow-mono text-ash">{meta.copy}</span>
      {(blind > 0 || stale > 0) && (
        <div className="grid grid-cols-2 gap-y-1 text-ui">
          <span className="eyebrow-mono">blind</span>
          <span className="text-right mono-num text-platinum">
            {String(blind).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">stale</span>
          <span className="text-right mono-num text-platinum">
            {String(stale).padStart(3, "0")}
          </span>
        </div>
      )}
    </div>
  );
}
