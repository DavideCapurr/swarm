# WS2 — Demo breadth: 3 legible scenario arcs + honest autonomy metrics

> **ARCHIVED 2026-06-26.** Executed; its substance is folded into the shipped
> Phase 7/8 work. Child of `pre-yc-build-plan.md` (also archived here). Kept for
> history. Current status: [`../../STATUS.md`](../../STATUS.md). Internal links
> below are relative to the original `docs/plan/` location.

> Status: **approved, pending execution** (execute in a dedicated session).
> Parent plan: [`pre-yc-build-plan.md`](pre-yc-build-plan.md) (Workstream 2).
> Commit convention: `phase-7: <subject>` (CLAUDE.md). At the end of each
> shippable unit run `make lint && make test`, `pnpm test` (in `frontend/`),
> `make audit`, and the forbidden-words + brand-audit greps; then update
> [`docs/STATUS.md`](../STATUS.md).
>
> **Entry point:** start with Part 2b (fully buildable + verifiable in-container
> via unit tests). Part 2a's tool change is in-container; its live capture is a
> manual step on the founder's machine (headed browser + Docker stack), same
> constraint as WS1's `.mov`.

## Context

WS1 (the verify-loop fix) is merged: executed VERIFY missions now promote an
anomaly `VERIFYING → VERIFIED`, so R2 auto-ESCALATE finally fires live and the
AUTO chip persists past command completion. That unblocks **Workstream 2** of
[`pre-yc-build-plan.md`](pre-yc-build-plan.md), which has two halves:

- **2a — three legible arcs.** All 3 demo scenarios are now narratable end-to-end,
  but only **wildfire** has committed screenshots/metrics. Intrusion and search
  need their arcs audited and captured. Their story is *deliberately different
  and good*: they stay under the R2 floor, so they stop at VERIFIED and **the
  operator owns escalation** — the human-on-the-loop pitch beat.
- **2b — honest in-Console metrics.** The backend collector
  `scripts/scenario_metrics.py` already computes autonomy latencies offline into
  bench artifacts. Surface the *same numbers* live in the Console, computed
  client-side from data already in `useSwarm()`, CSS/SVG-only, every readout
  labeled `(sim)`. No new backend endpoint, no fabricated values.

Outcome: a generalist watching any of the 3 demos sees the autonomous loop *and*
an honest, real-time readout of how fast SwarmOS decided — every number traceable
to a real audit record.

**Explicitly NOT in WS2** (deferred to Phase 8.B per the roadmap): per-scenario
autonomy thresholds, any change to R1/R2/R3 floors, any new autonomy rule.

---

## Part 2b — Honest autonomy metrics (the codeable core; do first)

This half is fully buildable + verifiable in-container via unit tests; no live
stack required.

### New file: `frontend/lib/metrics.ts` (pure, unit-tested)

Mirror `scripts/scenario_metrics.py` exactly. Signatures:

```ts
import type { OperatorCommand, AnomalyView, TimelineEvent } from "@/lib/api";

export type LatencyStat = { p50_ms: number | null; p95_ms: number | null; n: number };
export type AutonomyMetrics = {
  commands_total: number; auto_commands_total: number; operator_commands_total: number;
  by_rule: Record<string, number>;      // R1 / R2 / R3 / unspecified
  by_status: Record<string, number>;
  anomaly_to_decision: LatencyStat;      // ← scenario_metrics "anomaly_to_autonomy_decision"
  decision_to_dispatch: LatencyStat;     // ← "autonomy_decision_to_mission_dispatch"
};

export function percentile(samplesMs: number[], p: number): number | null;
export function computeAutonomyMetrics(
  commands: OperatorCommand[], anomalies: AnomalyView[], events: TimelineEvent[],
): AutonomyMetrics;
```

Algorithm parity with `scripts/scenario_metrics.py:107-234` (read firsthand):

- **anomaly→decision:** build `earliestAnomalyTs` = min `Date.parse(ev.ts)` over
  `events` where `ev.kind === "anomaly"` (confirmed valid `EventKind`,
  `frontend/lib/api.ts:91`) and `ev.anomaly_id` set. For each autonomy command
  (`source === "autonomy"`) whose `target` is `anomaly:<id>`,
  `delta = submitted_at − earliestAnomalyTs[id]`. **Drop `delta < 0`** (collector
  does). Fallback when no anomaly event is retained: `AnomalyView.detected_at`
  (the canonical birth, immune to event-deque eviction — see fidelity note).
- **decision→dispatch:** for each autonomy command with `in_flight_at != null`,
  `delta = in_flight_at − submitted_at`. Drop `delta < 0`.
- **by_rule / by_status / totals:** group autonomy commands by `rule`
  (null → `unspecified`) and `status`; counts of total / auto / operator.

**Percentile = nearest-rank, with a parity gotcha to get right:**

```
n = samples.length; if n === 0 → null
ordered = [...samples].sort((a,b) => a-b)
if n === 1 → ordered[0]
rank = max(1, min(n, roundHalfToEven(p/100 * n)))   // NOT Math.round
return ordered[rank-1]
```

The collector uses Python `round()`, which is **banker's rounding (half-to-even)**.
`Math.round` rounds half-up and **diverges** (e.g. n=5, p50: `2.5` → Python picks
`ordered[1]`, `Math.round` would pick `ordered[2]`). Implement a tiny
`roundHalfToEven(x)` so the Console number equals the bench artifact. Store the
raw selected sample; round to 1 decimal only at display (matching the collector's
`round(_, 1)`).

### New file: `frontend/components/AutonomyMetrics.tsx` (presentational)

Self-contained section reading `useSwarm()` directly (same pattern as
`AnomalySummary.tsx`). Returns `null` when `!autonomyEnabled`.

```tsx
const { commands, anomalies, events, autonomyEnabled } = useSwarm();
if (!autonomyEnabled) return null;
const m = computeAutonomyMetrics(commands, anomalies, events);
```

Render (reuse `QuietPanel`'s `SectionLabel` + `Row` idiom, `eyebrow-mono`,
`mono-num`, tokens from `frontend/lib/tokens.ts`):

- `SectionLabel` → `Autonomy (sim)`.
- A by-rule line: `r1 <n>  r2 <n>  r3 <n>` (`mono-num`, `text-platinum`; the
  active accent is `text-orbital-blue` — the existing AUTO color).
- Two `LatencyRow`s — `anomaly → decision (sim)` and `decision → dispatch (sim)`:
  hero value `{p50}/{p95} ms` in `mono-num`, plus `n=<count>` in `text-ash`.
- **Minimal CSS/SVG-only viz** (no chart lib — CLAUDE.md §5.2): a tiny inline
  `<svg>` per latency with two horizontal bars (p50, p95) scaled to a shared max,
  `fill` gunmetal track + `orbital-blue` value, following the
  `LiveFeedFrame.tsx` SVG idiom. No `box-shadow`/`drop-shadow`/`linear-gradient`.
- **Honest empty state:** when `n === 0`, render `— awaiting autonomy` in
  `text-ash`. **Never** print `0 ms` as if a measurement happened.
- **No red.** Accents limited to orbital-blue/ash/platinum.

### Mount: `frontend/components/QuietPanel.tsx`

Add a `<Hairline />` + `<AutonomyMetrics />` right after `PerformanceSection` in
QuietPanel's main return (`QuietPanel.tsx:108-115`). QuietPanel renders in the
right rail via `TerritoryControl` → `app/(console)/page.tsx`, so it shows on the
primary demo screen. (The component self-gates on `autonomyEnabled`, so
non-autonomy sites render nothing — zero diff for them.) `Hairline`,
`SectionLabel`, and `Row` already exist in `QuietPanel.tsx` — reuse, do not
re-create.

### Tests (vitest; `pnpm test` from `frontend/`)

- **`frontend/lib/metrics.test.ts`** (new): percentile nearest-rank for n=1, 2,
  5 (the half-to-even case), and an even-n case; assert half-to-even ≠ Math.round
  on n=5/p50; `by_rule` counts incl. null→`unspecified`; both latency deltas;
  negative-delta drop; empty → `{null,null,0}`. Add a synthetic fixture whose
  hand-computed expectations match the Python algorithm; leave a TODO to assert
  byte-parity against a real non-empty `docs/bench/artifacts/phase-7e-*.json`
  once the manual wildfire run (2a) produces one.
- **`frontend/components/__tests__/AutonomyMetrics.test.tsx`** (new): use
  `makeSwarmState`/`makeCommand`/`makeAnomaly`/`makeEvent` from
  `__tests__/_swarmState.ts` (all exist); assert computed values render, the
  `(sim)` labels are present, the empty state shows `awaiting`, returns null when
  `autonomyEnabled === false`, and the rendered markup contains no red token
  (`className` never matches `/red/`). Mock `useSwarm` exactly as
  `AnomalySummary.test.tsx` does.
- Add `lib/metrics.ts` to the `coverage.include` list in
  `frontend/vitest.config.ts` (sits beside `lib/autonomy.ts`).

### Fidelity note

Prefer the earliest `kind === "anomaly"` event ts to match the collector
exactly; fall back to `AnomalyView.detected_at` (retained in state regardless of
the events deque) so a long run can't silently shrink `n` below the artifact's.
For a 60s demo window the two agree. The test asserts the agreement on demo-shaped
input.

---

## Part 2a — Three legible arcs + screenshots

### Confirmed scenario truth (no code change to scenarios)

| Scenario | Anomaly | conf | after_s | Arc |
|---|---|---|---|---|
| wildfire | SMOKE→FIRE | 0.62→0.88 | 10/25 | R1 verify → VERIFIED → **R2 auto-escalate** |
| intrusion | INTRUSION | 0.71 | 15 | R1 verify → VERIFIED → **operator owns escalation** |
| search | HEAT_SPOT | 0.55 | 20 | R1 verify → VERIFIED → **operator owns escalation** |

R1 floor 0.50, R2 floor **0.80**, idle 10s (`swarm_os/autonomy.py:48-58`). Intrusion
& search staying under 0.80 is intentional and is the human-on-the-loop story —
**do not tune thresholds.**

### Code: parametrize the screenshot tool — `scripts/m1_capture_screenshots.py`

Today it is hardcoded to wildfire (scenario path at line 178; `wildfire-0X`
beat filenames at lines 175-251). Generalize:

- Accept a `--scenario {wildfire,intrusion,search}` arg → selects the YAML and a
  per-scenario **beat list**. Wildfire keeps its 5 beats (standby / SMOKE+R1 /
  FIRE / R2). Intrusion & search get 3 beats: `01-standby`, `02-<kind>+r1-verify`
  (poll for the R1 autonomy command, as lines 221-226 already do), `03-verified`
  (poll for the anomaly reaching `verified` — operator-owns climax). No R2 wait.
- Reuse the existing `wait_until` poll helpers and login/map-ready scaffolding
  unchanged; only the scenario path, beat filenames, and which predicates fire
  per scenario become data-driven.
- Output into `docs/yc/screenshots/` as `intrusion-0X-*.png` / `search-0X-*.png`.

### Manual local step (cannot run in this container — flag honestly)

The capture needs a **headed** browser for real WebGL (`headless=False`,
`scripts/m1_capture_screenshots.py:163-166`) and the full Docker stack — same
constraint as WS1's `.mov`. On the founder's machine:

1. `make demo-intrusion-sim` then run the capture tool `--scenario intrusion`;
   repeat for `search`. `--metrics` already auto-writes
   `docs/bench/artifacts/phase-7e-{intrusion,search}-*.json` (via
   `scripts/demo_scenario.sh:44-58`).
2. Commit the new screenshots + the two metrics artifacts.
3. Cross-check the live `Autonomy (sim)` panel against the matching artifact's
   `latencies_ms` (they must agree — the 2b parity test made this true).

### Docs

- Update `docs/STATUS.md` Phase 7 line: WS2 done, with the per-scenario arcs and
  cited artifact `by_rule` (`intrusion/search` → `{R1:1}`, no R2; wildfire →
  `{R1:1,R2:1}`).
- Resolve the `docs/yc/m1-a11y-report.md:84-89` mobile AUTO-chip note if the new
  captures show it surfacing post-WS1 (else leave it tracked for Phase 8.A).

---

## Anti-overreach / guardrails

- No new backend endpoint, no new dependency, no scenario/threshold edits.
- CSS/SVG only; no external chart/modal/toast lib. No red. No decorative shadow.
- Voice: copy is `auto decisions`, `anomaly → decision`, `decision → dispatch`,
  `(sim)`, `awaiting autonomy` — run the forbidden-words grep on touched files.
- Every Console number derives from a real audit record (no DERIVED).

## Verification

1. **Automatable (this environment):** `pnpm test` green incl. the new
   `metrics.test.ts` + `AutonomyMetrics.test.tsx`; `make lint` (ruff + mypy +
   tsc) green; `make test` + `make audit` green; forbidden-words + brand-audit
   greps clean on changed files.
2. **Parity:** a unit test proves `computeAutonomyMetrics` reproduces the
   `scenario_metrics.py` algorithm on shared synthetic input (incl. the n=5/p50
   half-to-even case).
3. **Manual local (founder machine):** the 3 demos boot; intrusion/search show
   `R1 → VERIFIED → operator owns next`, wildfire shows `R2 auto-escalate`; the
   `Autonomy (sim)` panel renders non-zero p50/p95 and matches the committed
   artifact; screenshots for all three scenarios committed.

## Sequence & effort

1. **2b code + tests** (in-container, fully verifiable) — effort **M**.
2. **2a tool parametrization + docs scaffolding** (in-container) — effort **S**.
3. **2a manual capture + artifacts + STATUS evidence** (founder machine) — effort **S** manual.
