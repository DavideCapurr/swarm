"use client";

/**
 * LinkHealth — fleet aggregate link quality and the weakest unit.
 *
 * Quality comes from `UnitState.link_quality` (0..1). The card never invents
 * a percentage when there are no units online.
 */

import { useSwarm } from "@/lib/state";
import { IconLink } from "@/icons";
import { Eyebrow } from "./Eyebrow";

export function LinkHealth() {
  const { units, link } = useSwarm();
  const online = units.filter((u) => u.fsm_state !== "OFFLINE");
  const avgPct = online.length
    ? (online.reduce((s, u) => s + u.link_quality, 0) / online.length) * 100
    : 0;
  const weakest = online.length
    ? [...online].sort((a, b) => a.link_quality - b.link_quality)[0]
    : null;
  const state = avgPct >= 80
    ? "text-signal-green"
    : avgPct >= 60
      ? "text-orbital-blue"
      : "text-launch-amber";
  const linkText =
    link === "connected" ? "live" : link === "connecting" ? "linking" : "offline";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Link health</Eyebrow>
        <span className="eyebrow-mono text-platinum">{linkText}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className={state}>
          <IconLink size={28} />
        </span>
        <div className="flex flex-col">
          <span className={`mono-num text-lede ${state}`}>
            {online.length ? `${avgPct.toFixed(1)} %` : "—"}
          </span>
          <span className="eyebrow-mono">fleet · mean</span>
        </div>
      </div>
      {weakest && (
        <div className="grid grid-cols-2 gap-y-1 text-ui">
          <span className="eyebrow-mono">weakest unit</span>
          <span className="text-right mono-num text-platinum">
            {unitLabel(weakest.agent_id)}
          </span>
          <span className="eyebrow-mono">weakest · q</span>
          <span className="text-right mono-num text-platinum">
            {(weakest.link_quality * 100).toFixed(0)} %
          </span>
        </div>
      )}
    </div>
  );
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return `${n}`;
}
