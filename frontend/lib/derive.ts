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

import type { AnomalyView, AwarenessBreakdown, OperatingMode, RiskState } from "./api";
import { MODE_COPY } from "./copy";

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
