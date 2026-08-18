"use client";

/**
 * DetectionPanel — why a fleet is flying at this.
 *
 * The first question a viewer has is not what SwarmOS decided, it is what
 * happened. This answers it in the order it happened: a sensor reported
 * something, SwarmOS accepted responsibility for it, and a mission now exists.
 *
 * There is no camera view here and there will not be one until the runtime
 * produces one. The MAVLink path publishes no video, so a viewport would be
 * decoration at best and a false claim at worst. What it publishes is the
 * detection itself — source, sensor, label, score, time, reporter, and a
 * confidence-bound headline SwarmOS composed — and that is what is drawn.
 *
 * The simulated/real boundary is on the face of the panel, not in a footnote.
 */

import type { ObjectiveAuthority } from "@/lib/authority";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";

export const DETECTION_WIDTH = 278;

/** Server source ids, said the way an operator reads them. */
const SOURCE_LABEL: Record<string, string> = {
  drone_cv: "ONBOARD CV",
  thermal_sat: "THERMAL SATELLITE",
  fire_detector: "FIRE DETECTOR",
  unknown: "UNATTRIBUTED",
};

function clockOf(at: string | null): string {
  if (!at) return "—";
  const date = new Date(at);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toISOString().slice(11, 19);
}

export function DetectionPanel({ objective }: { objective: ObjectiveAuthority }) {
  const detection = objective.detection;
  if (!detection) return null;

  return (
    <Surface
      data-testid="detection-panel"
      className="pointer-events-auto flex flex-col"
      style={{ width: DETECTION_WIDTH }}
    >
      <SurfaceHeader
        title="detection"
        right={
          <Mono size={9.5} tone={detection.simulated ? "amber" : "green"}>
            {detection.simulated ? "SIMULATED SIGNAL" : "SENSOR"}
          </Mono>
        }
      />

      <div className="flex items-baseline justify-between gap-3 px-3 pb-[9px] pt-[10px]">
        <span className="font-grotesk text-[13px] font-medium uppercase leading-none tracking-[0.14em] text-platinum">
          {objective.kind}
        </span>
        {objective.confidence != null ? (
          <Mono size={11} tone="silver">
            {(objective.confidence * 100).toFixed(0).padStart(3, "0")}%
          </Mono>
        ) : null}
      </div>

      {detection.headline ? (
        <div className="px-3 pb-[10px]">
          {/* SwarmOS composed this sentence. The Console quotes it. */}
          <span className="text-[11.5px] leading-[1.45] text-muted-silver">
            {detection.headline}
          </span>
        </div>
      ) : null}

      <Divider />

      <Row label="source" value={SOURCE_LABEL[detection.source] ?? detection.source.toUpperCase()} />
      <Row label="sensor" value={detection.sensor.toUpperCase()} border />
      {detection.label ? (
        <Row
          label="classified"
          value={
            detection.value != null
              ? `${detection.label} · ${detection.value.toFixed(2)}`
              : detection.label
          }
          border
        />
      ) : null}
      <Row label="reported by" value={detection.reportedBy ?? "—"} border />
      <Row label="at" value={`${clockOf(detection.at)} UTC`} border />

      <Divider />

      {/* Ownership is the beat that turns a detection into a mission, so it
          gets the accent and the last word on this panel. */}
      <div className="flex items-center justify-between gap-3 px-3 py-[10px]">
        <div className="flex items-center gap-2">
          <Dot tone="orbital" />
          <Label tone="orbital">swarmos accepted</Label>
        </div>
        <Mono size={11} tone="platinum">
          {objective.label}
        </Mono>
      </div>
    </Surface>
  );
}

function Row({
  label,
  value,
  border = false,
}: {
  label: string;
  value: string;
  border?: boolean;
}) {
  return (
    <div
      className="flex items-baseline justify-between gap-3 px-3 py-[8px]"
      style={{ borderTop: border ? `1px solid ${HAIRLINE}` : undefined }}
    >
      <Label>{label}</Label>
      <Mono size={11} tone="silver" className="truncate">
        {value}
      </Mono>
    </div>
  );
}
