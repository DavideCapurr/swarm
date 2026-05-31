/**
 * WS2 (Phase 7) — honest autonomy metrics, computed client-side.
 *
 * This is a pure TypeScript mirror of `scripts/scenario_metrics.py` (the
 * Phase 7.E baseline collector). The Console renders the *same* numbers the
 * bench artifact records — every value traces to a real audit record in
 * `useSwarm()` (commands / anomalies / events). No new backend endpoint, no
 * DERIVED fabrication.
 *
 * Two latencies, matching the collector's `_latency_samples`:
 *   - anomaly → decision  (collector: `anomaly_to_autonomy_decision`)
 *   - decision → dispatch (collector: `autonomy_decision_to_mission_dispatch`)
 *
 * Percentiles are nearest-rank with **banker's rounding (half-to-even)** so
 * the rank matches Python's built-in `round()` exactly — see
 * `roundHalfToEven` below. Using `Math.round` (half-up) would diverge on the
 * n=5 / p50 case and the Console number would no longer equal the artifact.
 */

import type { AnomalyView, OperatorCommand, TimelineEvent } from "@/lib/api";

export type LatencyStat = {
  p50_ms: number | null;
  p95_ms: number | null;
  n: number;
};

export type AutonomyMetrics = {
  commands_total: number;
  auto_commands_total: number;
  operator_commands_total: number;
  // R1 / R2 / R3 / unspecified — keyed by `OperatorCommand.rule`.
  by_rule: Record<string, number>;
  by_status: Record<string, number>;
  // ← collector "anomaly_to_autonomy_decision"
  anomaly_to_decision: LatencyStat;
  // ← collector "autonomy_decision_to_mission_dispatch"
  decision_to_dispatch: LatencyStat;
};

/**
 * Round half to even (banker's rounding), matching Python's built-in
 * `round(x)` with no `ndigits`. The collector ranks percentiles with
 * `round(p / 100.0 * n)`, so the Console must round the same way or the
 * selected sample diverges (e.g. n=5/p50: `2.5` → `2`, not `3`).
 *
 * Exact halves (`k.5`) are exactly representable as IEEE-754 doubles for the
 * small magnitudes we deal with, so the `=== 0.5` comparison is sound and
 * computes the identical result Python would on the identical double.
 */
export function roundHalfToEven(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  // Exactly halfway: pick the even neighbour.
  return floor % 2 === 0 ? floor : floor + 1;
}

/**
 * Nearest-rank percentile over millisecond samples, returning the **raw**
 * selected sample (callers round to 1 decimal at display, matching the
 * collector's `round(_, 1)`). Empty → `null`.
 *
 * Mirrors `scenario_metrics.py:_percentiles._pct`:
 *   n === 0 → null; n === 1 → the single sample;
 *   otherwise rank = clamp(roundHalfToEven(p/100 * n), 1, n), return ordered[rank-1].
 */
export function percentile(samplesMs: number[], p: number): number | null {
  const n = samplesMs.length;
  if (n === 0) return null;
  const ordered = [...samplesMs].sort((a, b) => a - b);
  if (n === 1) return ordered[0];
  const rank = Math.max(1, Math.min(n, roundHalfToEven((p / 100) * n)));
  return ordered[rank - 1];
}

function parseMs(value: string | null | undefined): number | null {
  if (!value) return null;
  const ms = Date.parse(value);
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Compute the autonomy metrics block from the audit frames already in
 * `useSwarm()`. Pure — no I/O, no clock read.
 *
 * Parity with `scenario_metrics.py:collect` + `_latency_samples`:
 *   - autonomy commands are those with `source === "autonomy"`.
 *   - by_rule groups on `rule` (falsy → "unspecified"); by_status on `status`.
 *   - anomaly→decision: `submitted_at − earliestAnomalyTs[id]`, dropping `< 0`.
 *     `earliestAnomalyTs` is the min ts over `events` with
 *     `kind === "anomaly"` and an `anomaly_id`; when no such event is retained
 *     (the events deque can evict old frames on a long run), fall back to the
 *     anomaly's canonical `detected_at`. For a demo window the two agree.
 *   - decision→dispatch: `in_flight_at − submitted_at`, dropping `< 0`.
 */
export function computeAutonomyMetrics(
  commands: OperatorCommand[],
  anomalies: AnomalyView[],
  events: TimelineEvent[],
): AutonomyMetrics {
  const autoCommands = commands.filter((c) => c.source === "autonomy");
  const operatorCommands = commands.filter((c) => c.source !== "autonomy");

  const byRule: Record<string, number> = {};
  const byStatus: Record<string, number> = {};
  for (const c of autoCommands) {
    const rule = c.rule || "unspecified";
    byRule[rule] = (byRule[rule] ?? 0) + 1;
    const status = c.status || "unknown";
    byStatus[status] = (byStatus[status] ?? 0) + 1;
  }

  // Earliest "anomaly" event ts per anomaly id (matches the collector).
  const earliestAnomalyTs: Record<string, number> = {};
  for (const ev of events) {
    if (ev.kind !== "anomaly") continue;
    const aid = ev.anomaly_id;
    const ts = parseMs(ev.ts);
    if (!aid || ts === null) continue;
    const prev = earliestAnomalyTs[aid];
    if (prev === undefined || ts < prev) earliestAnomalyTs[aid] = ts;
  }
  // Fallback: the AnomalyView birth ts, retained in state regardless of the
  // events deque, so a long run can't silently shrink n below the artifact's.
  const detectedAtTs: Record<string, number> = {};
  for (const a of anomalies) {
    const ts = parseMs(a.detected_at);
    if (ts !== null) detectedAtTs[a.id] = ts;
  }

  const anomalyToDecision: number[] = [];
  const decisionToDispatch: number[] = [];
  for (const c of autoCommands) {
    const submitted = parseMs(c.submitted_at);
    if (submitted === null) continue;

    const target = c.target || "";
    if (target.startsWith("anomaly:")) {
      const aid = target.slice("anomaly:".length);
      const anomalyTs =
        aid in earliestAnomalyTs ? earliestAnomalyTs[aid] : detectedAtTs[aid];
      if (anomalyTs !== undefined) {
        const delta = submitted - anomalyTs;
        if (delta >= 0) anomalyToDecision.push(delta);
      }
    }

    const inFlight = parseMs(c.in_flight_at);
    if (inFlight !== null) {
      const delta = inFlight - submitted;
      if (delta >= 0) decisionToDispatch.push(delta);
    }
  }

  return {
    commands_total: commands.length,
    auto_commands_total: autoCommands.length,
    operator_commands_total: operatorCommands.length,
    by_rule: byRule,
    by_status: byStatus,
    anomaly_to_decision: {
      p50_ms: percentile(anomalyToDecision, 50),
      p95_ms: percentile(anomalyToDecision, 95),
      n: anomalyToDecision.length,
    },
    decision_to_dispatch: {
      p50_ms: percentile(decisionToDispatch, 50),
      p95_ms: percentile(decisionToDispatch, 95),
      n: decisionToDispatch.length,
    },
  };
}
