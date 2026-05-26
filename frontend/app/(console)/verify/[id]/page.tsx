"use client";

/**
 * /verify/[id] — anomaly focus view. Honest LiveFeedFrame placeholder per PDF
 * §5.2 + ActionRail wired to verify/dismiss/hold/return. No stock video.
 */

import { use } from "react";
import Link from "next/link";

import { useSwarm } from "@/lib/state";
import { describeAnomalyKind, describeBand } from "@/lib/derive";
import { findActiveAutonomyCommand } from "@/lib/autonomy";
import { ActionRail } from "@/components/ActionRail";
import { Eyebrow } from "@/components/Eyebrow";
import { IconBack } from "@/icons";
import { LiveFeedFrame } from "@/components/LiveFeedFrame";
import { StatusPill } from "@/components/StatusPill";

export default function VerifyDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { anomalies, verifier, link, streams, commands } = useSwarm();
  const anomaly = anomalies.find((a) => a.id === id);
  const stream = verifier ? streams[verifier.agent_id] ?? null : null;
  const streamAvailable = !!(stream && stream.available && stream.url);
  const autonomyCommand = anomaly
    ? findActiveAutonomyCommand(commands, anomaly.id)
    : null;

  return (
    <main className="flex-1 px-6 py-6 flex flex-col gap-6 overflow-y-auto">
      <header className="flex items-baseline justify-between">
        <Link
          href="/verify"
          className="flex items-center gap-2 eyebrow-mono text-platinum focus:outline-none focus-visible:outline-1 focus-visible:outline-orbital-blue"
        >
          <IconBack size={16} /> verification
        </Link>
        <span className="eyebrow-mono text-ash">link · {link}</span>
      </header>

      {!anomaly ? (
        <div className="card p-4">
          <Eyebrow mono>Anomaly · {id.slice(0, 4)}</Eyebrow>
          <p className="font-display text-platinum text-ui mt-2">
            anomaly not present in current session — it may have been resolved.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-[1fr_380px] gap-6 min-h-0">
          <div className="flex flex-col gap-3">
            <Eyebrow mono>Live feed</Eyebrow>
            <LiveFeedFrame
              unit={verifier}
              linkOk={link === "connected"}
              stream={stream}
            />
            <span className="eyebrow-mono text-ash">
              {streamAvailable
                ? "live · stream advertised by the adapter"
                : "feed pending — adapter has not advertised a stream url"}
            </span>
          </div>

          <div className="flex flex-col gap-3">
            <div className="card p-4 flex flex-col gap-3">
              <div className="flex items-baseline justify-between">
                <Eyebrow mono>Anomaly · {anomaly.id.slice(0, 4)}</Eyebrow>
                <span className="flex items-center gap-2">
                  {autonomyCommand && (
                    <span
                      className="eyebrow-mono text-orbital-blue"
                      data-testid="verify-auto-chip"
                    >
                      AUTO · {autonomyCommand.action.replace("_", " ")}
                    </span>
                  )}
                  <StatusPill
                    state={anomaly.band === "verified" ? "operational" : "attention"}
                  >
                    {describeBand(anomaly.band)}
                  </StatusPill>
                </span>
              </div>

              <div className="grid grid-cols-2 gap-y-1 text-ui">
                <span className="eyebrow-mono">type</span>
                <span className="text-right eyebrow-mono text-platinum">
                  {describeAnomalyKind(anomaly.kind)}
                </span>

                <span className="eyebrow-mono">confidence</span>
                <span className="text-right mono-num text-platinum">
                  {String(Math.round(anomaly.confidence * 100)).padStart(3, "0")} %
                </span>

                <span className="eyebrow-mono">state</span>
                <span className="text-right eyebrow-mono text-launch-amber">
                  {anomaly.state}
                </span>

                <span className="eyebrow-mono">sector</span>
                <span className="text-right mono-num text-platinum">
                  {anomaly.sector_id ?? "—"}
                </span>

                <span className="eyebrow-mono">position</span>
                <span className="text-right mono-num text-platinum">
                  {anomaly.geo.lat.toFixed(3)}°n · {anomaly.geo.lon.toFixed(3)}°e
                </span>

                <span className="eyebrow-mono">verifier</span>
                <span className="text-right eyebrow-mono text-orbital-blue">
                  {verifier ? `unit ${unitLabel(verifier.agent_id)}` : "—"}
                </span>
              </div>
            </div>

            <ActionRail />
          </div>
        </div>
      )}
    </main>
  );
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  return m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
}
