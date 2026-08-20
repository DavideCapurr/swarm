"use client";

/**
 * DetectionPanel — why a fleet is flying at this.
 *
 * The first question a viewer has is not what SwarmOS decided, it is what
 * happened. This answers it in the order it happened: a sensor reported
 * something, SwarmOS accepted responsibility for it, and a mission now exists.
 *
 * The panel is built for a three-second read, because that is what it gets:
 * kind + confidence, the sentence SwarmOS composed, one compressed technical
 * line for provenance, then the ownership hand-off. Everything else the server
 * sent — the sensor, the raw classifier label and score — stays on the panel,
 * demoted rather than dropped, one size and one tone quieter.
 *
 * There is no camera view here and there will not be one until the runtime
 * produces one. The MAVLink path publishes no video, so a viewport would be
 * decoration at best and a false claim at worst.
 *
 * The simulated/real boundary is on the face of the panel, not in a footnote.
 */

import type { ObjectiveAuthority } from "@/lib/authority";

import { Divider, Dot, Label, Mono, Surface, SurfaceHeader } from "./Surface";

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

  const sourceLabel = SOURCE_LABEL[detection.source] ?? detection.source.toUpperCase();
  // The one line that has to survive a three-second read: who saw it, who's
  // reporting, when. Sensor and the raw classifier label/score are real server
  // fields and stay on the panel — just not on this line.
  const provenance = [sourceLabel, detection.reportedBy, `${clockOf(detection.at)} UTC`]
    .filter(Boolean)
    .join(" · ");
  const classification =
    detection.label != null
      ? detection.value != null
        ? `${detection.sensor.toUpperCase()} · ${detection.label.toUpperCase()} ${detection.value.toFixed(2)}`
        : `${detection.sensor.toUpperCase()} · ${detection.label.toUpperCase()}`
      : detection.sensor.toUpperCase();

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

      {/* 1 — what it is. Kind and confidence on one line: this is the fact a
          viewer has to register first. */}
      <div className="flex items-baseline justify-between gap-3 px-3 pb-[8px] pt-[11px]">
        <span className="font-grotesk text-[15px] font-medium uppercase leading-none tracking-[0.06em] text-platinum">
          {objective.kind}
        </span>
        {objective.confidence != null ? (
          <Mono size={13} tone="silver">
            {(objective.confidence * 100).toFixed(0).padStart(3, "0")}%
          </Mono>
        ) : null}
      </div>

      {/* 2 — the sentence SwarmOS composed. Quoted, never rewritten. */}
      {detection.headline ? (
        <div className="px-3 pb-[11px]">
          <span className="text-[11.5px] leading-[1.45] text-muted-silver">
            {detection.headline}
          </span>
        </div>
      ) : null}

      {/* 3 — one compressed provenance line: who saw it, who's reporting, when. */}
      <div className="px-3 pb-[3px]">
        <Mono size={11} tone="platinum">
          {provenance}
        </Mono>
      </div>

      {/* Demoted, not dropped: the sensor and the raw classifier reading stay
          on the panel a size and a tone quieter than the line above. */}
      <div className="px-3 pb-[10px]">
        <Mono size={9} tone="ash">
          {classification}
        </Mono>
      </div>

      <Divider />

      {/* 4 — the hand-off. SwarmOS accepted this, and here is what it became. */}
      <div className="flex items-center justify-between gap-3 px-3 py-[10px]">
        <div className="flex items-center gap-2">
          <Dot tone="orbital" />
          <Label tone="orbital">swarmos accepted</Label>
        </div>
        <Mono size={11} tone="orbital">
          → {objective.label}
        </Mono>
      </div>
    </Surface>
  );
}
