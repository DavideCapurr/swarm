"use client";

/**
 * EvidenceBlock — the *why* behind an anomaly.
 *
 * Renders provenance (source + sensor), the triggering measurement
 * (value vs baseline → Δ, or label + score), and detection metadata. The
 * one-line reason is the server-authored `evidence.headline` — the Console
 * renders operational truth, it never composes it. Every contributing signal
 * is sim-modelled, flagged with the `SIMULATED` eyebrow.
 *
 * Shared by the desktop verify detail and the Control rail summary.
 */

import type { AnomalyView } from "@/lib/api";
import { describeSource, formatEvidence } from "@/lib/derive";
import { UNIT_LABEL } from "@/lib/copy";
import {
  IconAnomaly,
  IconDroneCv,
  IconFireDetector,
  IconThermalSat,
  type IconProps,
} from "@/icons";
import { Eyebrow } from "./Eyebrow";

const SOURCE_ICON: Record<string, (p: IconProps) => React.ReactElement> = {
  thermal_sat: IconThermalSat,
  fire_detector: IconFireDetector,
  drone_cv: IconDroneCv,
  unknown: IconAnomaly,
};

export function EvidenceBlock({ anomaly }: { anomaly: AnomalyView }) {
  const ev = anomaly.evidence;
  if (!ev) return null;

  const Icon = SOURCE_ICON[ev.source] ?? IconAnomaly;
  const measurement = formatEvidence(ev);
  const hasReading =
    ev.metric === "temperature_c" && ev.value != null && ev.baseline != null;
  const unit = ev.unit ?? "°C";

  return (
    <div className="card p-4 flex flex-col gap-3" data-testid="evidence-block">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Evidence</Eyebrow>
        {ev.simulated && (
          <span className="eyebrow-mono text-ash" data-testid="evidence-simulated">
            simulated
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <span className="text-launch-amber">
          <Icon size={24} />
        </span>
        <div className="flex flex-col">
          <span className="font-display text-platinum text-ui" data-testid="evidence-headline">
            {ev.headline}
          </span>
          <span className="eyebrow-mono">
            {describeSource(ev.source)} · {ev.sensor.toLowerCase()}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-y-1 text-ui">
        <span className="eyebrow-mono">source</span>
        <span className="text-right eyebrow-mono text-platinum">
          {describeSource(ev.source)}
        </span>

        <span className="eyebrow-mono">sensor</span>
        <span className="text-right eyebrow-mono text-platinum">
          {ev.sensor.toLowerCase()}
        </span>

        {measurement && (
          <>
            <span className="eyebrow-mono">measurement</span>
            <span className="text-right mono-num text-launch-amber">
              {measurement}
            </span>
          </>
        )}

        {hasReading && (
          <>
            <span className="eyebrow-mono">reading</span>
            <span className="text-right mono-num text-platinum">
              {ev.value}
              {unit} vs {ev.baseline}
              {unit}
            </span>
          </>
        )}

        {ev.label && (
          <>
            <span className="eyebrow-mono">label</span>
            <span className="text-right eyebrow-mono text-platinum">{ev.label}</span>
          </>
        )}

        {anomaly.detected_by && (
          <>
            <span className="eyebrow-mono">detected by</span>
            <span className="text-right eyebrow-mono text-platinum">
              {UNIT_LABEL(anomaly.detected_by)}
            </span>
          </>
        )}

        <span className="eyebrow-mono">detected at</span>
        <span className="text-right mono-num text-platinum">
          {formatTs(anomaly.detected_at)}
        </span>
      </div>
    </div>
  );
}

function formatTs(ts: string): string {
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}
