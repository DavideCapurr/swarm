"use client";

/**
 * AnomalySummary — the focus anomaly read in confidence-bound language.
 *
 * Reads the head pending/verified anomaly from `useSwarm()`. Never invents
 * absolute claims ("intrusion confirmed"); always confidence-bound.
 */

import Link from "next/link";

import { useFocusAnomaly, useSwarm } from "@/lib/state";
import { describeAnomalyKind, describeBand } from "@/lib/derive";
import { findActiveAutonomyCommand } from "@/lib/autonomy";
import { ANOMALY_STATE_COPY, UNIT_LABEL } from "@/lib/copy";
import { IconAnomaly } from "@/icons";
import { Eyebrow } from "./Eyebrow";
import { StatusPill } from "./StatusPill";

export function AnomalySummary() {
  const anomaly = useFocusAnomaly();
  const { verifier, anomalies, commands } = useSwarm();
  const autonomyCommand = anomaly
    ? findActiveAutonomyCommand(commands, anomaly.id)
    : null;

  if (!anomaly) {
    const dismissed = anomalies.filter((a) => a.state === "dismissed").length;
    return (
      <div className="card p-4 flex flex-col gap-2">
        <Eyebrow mono>Anomaly</Eyebrow>
        <div className="flex items-center gap-3">
          <span className="text-muted-silver">
            <IconAnomaly size={24} />
          </span>
          <div className="flex flex-col">
            <span className="font-display text-platinum text-ui">no anomaly detected.</span>
            <span className="eyebrow-mono">
              {dismissed > 0
                ? `${String(dismissed).padStart(3, "0")} resolved this watch`
                : "all sectors monitored."}
            </span>
          </div>
        </div>
      </div>
    );
  }

  const pct = Math.round(anomaly.confidence * 100);
  const pillState = anomaly.band === "verified" ? "operational" : "attention";

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Anomaly · {anomaly.id.slice(0, 4)}</Eyebrow>
        <span className="flex items-center gap-2">
          {autonomyCommand && (
            <span
              className="eyebrow-mono text-orbital-blue"
              data-testid="anomaly-auto-chip"
            >
              AUTO · {autonomyCommand.action.replace("_", " ")}
            </span>
          )}
          <StatusPill state={pillState}>{describeBand(anomaly.band)}</StatusPill>
        </span>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">type</span>
        <span className="text-right eyebrow-mono text-platinum">
          {describeAnomalyKind(anomaly.kind)}
        </span>

        <span className="eyebrow-mono">confidence</span>
        <span className="text-right mono-num text-platinum">
          {String(pct).padStart(3, "0")} %
        </span>

        <span className="eyebrow-mono">sector</span>
        <span className="text-right mono-num text-platinum">
          {anomaly.sector_id ?? "—"}
        </span>

        <span className="eyebrow-mono">state</span>
        <span className="text-right eyebrow-mono text-launch-amber">
          {ANOMALY_STATE_COPY[anomaly.state]}
        </span>

        {verifier && (
          <>
            <span className="eyebrow-mono">verifier</span>
            <span className="text-right eyebrow-mono text-orbital-blue">
              {UNIT_LABEL(verifier.agent_id)}
            </span>
          </>
        )}
      </div>

      <Link
        href={`/verify/${anomaly.id}`}
        className="self-start eyebrow-mono text-platinum hover:text-orbital-blue transition-colors duration-press ease-swarm"
      >
        — open verification
      </Link>
    </div>
  );
}
