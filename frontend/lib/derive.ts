/**
 * UI formatting helpers.
 *
 * Phase 3 truth-layer rule: nothing in this file invents operational state.
 * Every value the operator sees comes from SwarmOS via WS/REST; this file
 * only formats already-truthful data (clock, mode copy, anomaly copy) for
 * the Console's typographic conventions.
 *
 * The `Derived<T>` / `MaybeDerived<T>` machinery from Phase 2 is gone —
 * `state.tsx` exposes plain values now.
 */

import type {
  AnomalyEvidence,
  AnomalySource,
  AnomalyView,
  AwarenessBreakdown,
  OperatingMode,
  OperatorCommand,
  RiskState,
} from "./api";
import { ANOMALY_STATE_COPY, MODE_COPY, UNIT_LABEL } from "./copy";

// ── Clock ──────────────────────────────────────────────────────────────────────

export function formatClock(d: Date): { time: string; date: string } {
  const pad = (n: number) => String(n).padStart(2, "0");
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  const dd = pad(d.getUTCDate());
  const mm = pad(d.getUTCMonth() + 1);
  const yy = String(d.getUTCFullYear()).slice(2);
  return { time, date: `${dd} · ${mm} · ${yy}` };
}

// ── Awareness placeholder ──────────────────────────────────────────────────────
// Used only before the first REST/WS frame lands so the rail does not appear
// empty. Renders with score 0 and `rest` posture — never overwritten by a real
// frame.

export function fallbackAwareness(now: Date): AwarenessBreakdown {
  return {
    score: 0,
    factors: {},
    blind_spot_sectors: [],
    stale_sectors: [],
    risk_state: "rest" as RiskState,
    mode: "rest" as OperatingMode,
    verifying_agent: null,
    ts: now.toISOString(),
  };
}

// ── Mode copy ──────────────────────────────────────────────────────────────────
// Mirrors `core.swarm_core.voice.describe_mode` so the bottom-left mode line
// reads exactly like a backend-emitted Event body would.

export function describeMode(mode: OperatingMode): string {
  return MODE_COPY[mode].narrative_en;
}

// ── Anomaly copy ───────────────────────────────────────────────────────────────
// Confidence-bound only. Mirrors `voice.describe_anomaly`. Never emits any
// FORBIDDEN_WORDS token.

export function describeAnomalyKind(kind: AnomalyView["kind"]): string {
  switch (kind) {
    case "SMOKE":
      return "thermal irregularity";
    case "FIRE":
      return "elevated thermal signature";
    case "HEAT_SPOT":
      return "heat-spot signature";
    case "INTRUSION":
      return "movement pattern";
    case "UNKNOWN":
    default:
      return "unresolved pattern";
  }
}

export function describeBand(band: AnomalyView["band"]): string {
  switch (band) {
    case "verified":
      return "verified hotspot";
    case "elevated":
      return "elevated anomaly";
    case "low-confidence":
      return "low-confidence anomaly";
  }
}

// ── Evidence layer ─────────────────────────────────────────────────────────────
// Display-only formatters for the *why* behind an anomaly. The values
// (source, label, value, baseline, …) all come from SwarmOS / the honest
// simulator; these helpers format units + labels only. The server-authored
// `evidence.headline` remains the canonical one-liner in the contract.

export function describeSource(source: AnomalySource): string {
  switch (source) {
    case "thermal_sat":
      return "thermal sat";
    case "fire_detector":
      return "fire detector";
    case "drone_cv":
      return "onboard cv";
    case "unknown":
    default:
      return "signal";
  }
}

/**
 * Format the triggering measurement for display — units/labels only.
 *   temperature_c  → "+29°C over baseline" (Δ = value − baseline)
 *   object_score   → "fire · 088%"         (label + score)
 *   fire detector  → "heat trip"
 * Falls back to the server headline when the shape is unrecognised.
 */
export function formatEvidence(ev: AnomalyEvidence): string {
  if (ev.metric === "temperature_c" && ev.value != null && ev.baseline != null) {
    const delta = ev.value - ev.baseline;
    const unit = ev.unit ?? "°C";
    const sign = delta >= 0 ? "+" : "-";
    return `${sign}${Math.abs(Math.round(delta))}${unit} over baseline`;
  }
  if (ev.metric === "object_score" && ev.value != null) {
    const pct = String(Math.round(ev.value * 100)).padStart(3, "0");
    return ev.label ? `${ev.label} · ${pct}%` : `${pct}%`;
  }
  if (ev.source === "fire_detector") {
    return "heat trip";
  }
  return ev.headline ?? "";
}

/**
 * Build the amber anomaly callout shown on the map. When evidence is present
 * it leads with provenance + the triggering signal, e.g.
 * "thermal sat · +29°C over baseline · verified" (the CSS uppercases it).
 * Falls back to the state/confidence callout for evidence-less anomalies.
 * `auto` (the in-flight autonomy command) prepends an `auto · <rule>` eyebrow.
 */
export function anomalyCallout(
  a: AnomalyView,
  auto: OperatorCommand | null
): string {
  const pct = Math.round(a.confidence * 100);
  const state = ANOMALY_STATE_COPY[a.state];
  let prefix = "";
  if (auto) {
    prefix = auto.rule ? `auto · ${auto.rule.toLowerCase()} · ` : "auto · ";
  }
  if (a.evidence) {
    const lead = `${describeSource(a.evidence.source)} · ${formatEvidence(a.evidence)}`;
    if (a.state === "verifying" && a.verifying_agent) {
      return `${prefix}${lead} · ${UNIT_LABEL(a.verifying_agent)} ${state}`;
    }
    return `${prefix}${lead} · ${state}`;
  }
  if (a.state === "verifying" && a.verifying_agent) {
    return `${prefix}${UNIT_LABEL(a.verifying_agent)} · ${state}`;
  }
  if (a.state === "verified" || a.state === "escalated") {
    return `${prefix}anomaly ${state}`;
  }
  return `${prefix}anomaly ${state} · confidence ${String(pct).padStart(3, "0")} %`;
}
