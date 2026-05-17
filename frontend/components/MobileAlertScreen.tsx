"use client";

/**
 * MobileAlertScreen — the operator's pocket view (PDF §5.10 mobile).
 *
 * Single column, 360×640 baseline, no horizontal overflow. Identical awareness
 * truth to desktop — same `useSwarm()` source. Mode pill, awareness number,
 * pending anomaly count, link badge.
 */

import Link from "next/link";

import { useSwarm } from "@/lib/state";
import { describeMode } from "@/lib/derive";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

const MODE_STATE: Record<
  "rest" | "patrol" | "verification" | "escalation" | "maintenance",
  "rest" | "connected" | "operational" | "attention"
> = {
  rest: "rest",
  patrol: "operational",
  verification: "attention",
  escalation: "attention",
  maintenance: "attention",
};

export function MobileAlertScreen() {
  const { awareness, anomalies, mode, units, link, session } = useSwarm();
  const pending = anomalies.filter(
    (a) => a.state === "pending" || a.state === "verifying"
  );
  const online = units.filter((u) => u.fsm_state !== "OFFLINE").length;
  const total = units.length;

  return (
    <main className="min-h-screen flex flex-col bg-absolute-black px-4 py-6 gap-4">
      <header className="flex items-baseline justify-between">
        <span className="swarm-wordmark text-platinum" style={{ fontSize: 13 }}>
          SWARM
        </span>
        <span className="eyebrow-mono">{session?.label ?? "session 0001"}</span>
      </header>

      <div className="card p-4 flex flex-col gap-3">
        <Eyebrow mono>Awareness</Eyebrow>
        <span className="mono-num text-platinum" style={{ fontSize: 64, lineHeight: 1 }}>
          {String(Math.round(awareness.score)).padStart(3, "0")}
        </span>
        <span className="eyebrow-mono">% · {awareness.risk_state}</span>
        <span className="eyebrow-mono text-ash">{describeMode(mode)}</span>
      </div>

      <div className="card p-4 flex flex-col gap-3">
        <div className="flex items-baseline justify-between">
          <Eyebrow mono>Mode</Eyebrow>
          <StatusPill state={MODE_STATE[mode]}>{mode}</StatusPill>
        </div>
        <div className="grid grid-cols-2 gap-y-1 text-ui">
          <span className="eyebrow-mono">units</span>
          <span className="text-right mono-num text-platinum">
            {String(online).padStart(3, "0")} / {String(total).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">pending</span>
          <span className="text-right mono-num text-platinum">
            {String(pending.length).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">link</span>
          <span className="text-right eyebrow-mono text-platinum">{link}</span>
        </div>
      </div>

      <Eyebrow mono>Anomalies</Eyebrow>
      <div className="flex flex-col gap-2">
        {pending.length === 0 && (
          <span className="eyebrow-mono text-ash">territory quiet · no pending anomaly</span>
        )}
        {pending.slice(0, 5).map((a) => (
          <Link
            key={a.id}
            href={`/m/${a.id}`}
            className="card p-3 flex items-baseline justify-between focus:outline-none focus-visible:outline-1 focus-visible:outline-orbital-blue"
          >
            <span className="flex flex-col">
              <span className="font-mono text-ui text-platinum tracking-eyebrow-mono uppercase">
                {a.id.slice(0, 4)} · {a.kind.toLowerCase()}
              </span>
              <span className="eyebrow-mono">{a.band} · sector {a.sector_id ?? "—"}</span>
            </span>
            <span className="mono-num text-platinum">
              {String(Math.round(a.confidence * 100)).padStart(3, "0")} %
            </span>
          </Link>
        ))}
      </div>
    </main>
  );
}
