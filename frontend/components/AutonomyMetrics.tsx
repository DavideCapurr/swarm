"use client";

/**
 * AutonomyMetrics — WS2 (Phase 7) honest, in-Console autonomy readout.
 *
 * Surfaces the *same* numbers the Phase 7.E bench collector
 * (`scripts/scenario_metrics.py`) records, computed client-side via
 * `lib/metrics.ts` from the audit frames already in `useSwarm()`
 * (commands / anomalies / events). Every value traces to a real audit
 * record — no DERIVED fabrication, no new backend endpoint.
 *
 * Self-gates on `autonomyEnabled`: non-autonomy sites render nothing.
 * Every readout is labeled `(sim)` so the operator never mistakes a
 * simulation latency for a flown-hardware one. CSS/SVG-only (CLAUDE.md
 * §5.2 — no chart lib). Accents limited to orbital-blue / ash / platinum.
 * No red. Honest empty state — `— awaiting autonomy`, never `0 ms`.
 */

import { useSwarm } from "@/lib/state";
import { computeAutonomyMetrics, type LatencyStat } from "@/lib/metrics";
import { SectionLabel } from "./QuietPanel";

// The deterministic baseline rules, in escalation order (swarm_os/autonomy.py).
const RULES = ["R1", "R2", "R3"] as const;

// SVG bar geometry — orbital-blue value over a gunmetal track, mirroring the
// LiveFeedFrame.tsx raw-hex SVG idiom. No shadow / no gradient.
const TRACK = "#1A2026"; // gunmetal
const VALUE = "#7BE7FF"; // orbital-blue

export function AutonomyMetrics() {
  const { commands, anomalies, events, autonomyEnabled } = useSwarm();
  if (!autonomyEnabled) return null;

  const m = computeAutonomyMetrics(commands, anomalies, events);

  return (
    <section className="flex flex-col gap-3" data-testid="autonomy-metrics">
      <SectionLabel>Autonomy (sim)</SectionLabel>
      <ByRuleRow byRule={m.by_rule} />
      <LatencyRow label="anomaly → decision (sim)" stat={m.anomaly_to_decision} />
      <LatencyRow label="decision → dispatch (sim)" stat={m.decision_to_dispatch} />
    </section>
  );
}

function ByRuleRow({ byRule }: { byRule: Record<string, number> }) {
  return (
    <div className="flex items-center gap-4" data-testid="autonomy-by-rule">
      {RULES.map((rule) => {
        const n = byRule[rule] ?? 0;
        return (
          <span key={rule} className="flex items-baseline gap-1">
            <span className="eyebrow-mono text-ash">{rule.toLowerCase()}</span>
            <span
              className={`mono-num ${n > 0 ? "text-orbital-blue" : "text-platinum"}`}
            >
              {String(n).padStart(2, "0")}
            </span>
          </span>
        );
      })}
    </div>
  );
}

function LatencyRow({ label, stat }: { label: string; stat: LatencyStat }) {
  const hasData = stat.n > 0;
  return (
    <div className="flex flex-col gap-1" data-testid="autonomy-latency-row">
      <div className="flex items-baseline justify-between">
        <span className="eyebrow-mono text-ash">{label}</span>
        {hasData && (
          <span className="eyebrow-mono text-ash">
            n={String(stat.n).padStart(2, "0")}
          </span>
        )}
      </div>
      {hasData ? (
        <>
          <span
            className="mono-num text-platinum"
            style={{ fontSize: 22, lineHeight: 1.1 }}
          >
            {fmtMs(stat.p50_ms)}/{fmtMs(stat.p95_ms)} ms
          </span>
          <LatencyBars p50={stat.p50_ms ?? 0} p95={stat.p95_ms ?? 0} />
        </>
      ) : (
        <span className="eyebrow-mono text-ash">— awaiting autonomy</span>
      )}
    </div>
  );
}

// Round to 1 decimal only at display, matching the collector's `round(_, 1)`.
function fmtMs(value: number | null): string {
  return value == null ? "—" : value.toFixed(1);
}

function LatencyBars({ p50, p95 }: { p50: number; p95: number }) {
  // p95 ≥ p50 by nearest-rank ordering, so the two bars share a max within
  // this row (the longer bar reaches full width).
  const max = Math.max(p50, p95, 1);
  const W = 200;
  const H = 6;
  const GAP = 4;
  const widthOf = (v: number) => (v / max) * W;
  return (
    <svg
      className="w-full"
      viewBox={`0 0 ${W} ${H * 2 + GAP}`}
      preserveAspectRatio="none"
      role="presentation"
      aria-hidden="true"
    >
      <rect x="0" y="0" width={W} height={H} fill={TRACK} />
      <rect x="0" y="0" width={widthOf(p50)} height={H} fill={VALUE} />
      <rect x="0" y={H + GAP} width={W} height={H} fill={TRACK} />
      <rect x="0" y={H + GAP} width={widthOf(p95)} height={H} fill={VALUE} />
    </svg>
  );
}
