"use client";

/**
 * MobileAnomalyScreen — focused anomaly view for the operator on mobile.
 *
 * 360×640 baseline, single column. Confidence-bound copy only. Action rail is
 * disabled here — the operator confirms intents on desktop. Mobile is a heads-
 * up; never a kill switch.
 */

import Link from "next/link";

import { useSwarm } from "@/lib/state";
import { describeAnomalyKind, describeBand, describeSource } from "@/lib/derive";
import { findLatestAutonomyCommand } from "@/lib/autonomy";
import { ANOMALY_STATE_COPY, UNIT_LABEL } from "@/lib/copy";
import { IconBack } from "@/icons";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

export function MobileAnomalyScreen({ anomalyId }: { anomalyId: string }) {
  const { anomalies, verifier, commands } = useSwarm();
  const anomaly = anomalies.find((a) => a.id === anomalyId);
  const autonomyCommand = anomaly
    ? findLatestAutonomyCommand(commands, anomaly.id)
    : null;

  return (
    <main className="min-h-screen flex flex-col bg-absolute-black px-4 py-6 gap-4">
      <header className="flex items-baseline justify-between">
        <Link
          href="/m"
          className="flex items-center gap-2 eyebrow-mono text-platinum focus:outline-none focus-visible:outline-1 focus-visible:outline-orbital-blue"
        >
          <IconBack size={16} /> alerts
        </Link>
        <span className="eyebrow-mono text-ash">read only · desktop confirms</span>
      </header>

      {!anomaly ? (
        <div className="card p-4">
          <Eyebrow mono>Anomaly · {anomalyId.slice(0, 4)}</Eyebrow>
          <p className="font-display text-platinum text-ui mt-2">
            anomaly not found in current session — return to alerts.
          </p>
        </div>
      ) : (
        <div className="card p-4 flex flex-col gap-3">
          <div className="flex items-baseline justify-between">
            <Eyebrow mono>Anomaly · {anomaly.id.slice(0, 4)}</Eyebrow>
            <span className="flex items-center gap-2">
              {autonomyCommand && (
                <span
                  className="eyebrow-mono text-orbital-blue"
                  data-testid="mobile-auto-chip"
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

          <span className="mono-num text-platinum" style={{ fontSize: 56, lineHeight: 1 }}>
            {String(Math.round(anomaly.confidence * 100)).padStart(3, "0")}
          </span>
          <span className="eyebrow-mono">
            confidence {String(Math.round(anomaly.confidence * 100)).padStart(3, "0")} %
          </span>

          {anomaly.evidence && (
            <span
              className="text-platinum text-ui"
              data-testid="mobile-evidence-reason"
            >
              {describeSource(anomaly.evidence.source)}: {anomaly.evidence.headline}
            </span>
          )}

          <div className="grid grid-cols-2 gap-y-1 text-ui">
            <span className="eyebrow-mono">type</span>
            <span className="text-right eyebrow-mono text-platinum">
              {describeAnomalyKind(anomaly.kind)}
            </span>

            <span className="eyebrow-mono">state</span>
            <span className="text-right eyebrow-mono text-launch-amber">
              {ANOMALY_STATE_COPY[anomaly.state]}
            </span>

            <span className="eyebrow-mono">sector</span>
            <span className="text-right mono-num text-platinum">
              {anomaly.sector_id ?? "—"}
            </span>

            <span className="eyebrow-mono">verifier</span>
            <span className="text-right eyebrow-mono text-orbital-blue">
              {verifier ? UNIT_LABEL(verifier.agent_id) : "—"}
            </span>

            <span className="eyebrow-mono">position</span>
            <span className="text-right mono-num text-platinum">
              {anomaly.geo.lat.toFixed(3)}°n · {anomaly.geo.lon.toFixed(3)}°e
            </span>

            <span className="eyebrow-mono">detected at</span>
            <span className="text-right mono-num text-platinum">
              {formatTs(anomaly.detected_at)}
            </span>
          </div>

          <span className="eyebrow-mono text-ash">
            confirm intent from console. mobile heads-up only.
          </span>
        </div>
      )}
    </main>
  );
}

function formatTs(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}
