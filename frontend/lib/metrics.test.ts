/**
 * WS2 (Phase 7) — parity unit tests for the client-side autonomy metrics.
 *
 * These prove `lib/metrics.ts` reproduces the `scripts/scenario_metrics.py`
 * algorithm on shared synthetic input, including the half-to-even percentile
 * gotcha (Python `round()` vs JS `Math.round`). The hand-computed expectations
 * below mirror the Python collector exactly so the Console number equals the
 * bench artifact.
 */

import { describe, expect, it } from "vitest";

import { computeAutonomyMetrics, percentile, roundHalfToEven } from "./metrics";
import {
  makeAnomaly,
  makeCommand,
  makeEvent,
} from "@/components/__tests__/_swarmState";

describe("roundHalfToEven", () => {
  it("rounds exact halves to the even neighbour (banker's rounding)", () => {
    expect(roundHalfToEven(0.5)).toBe(0);
    expect(roundHalfToEven(1.5)).toBe(2);
    expect(roundHalfToEven(2.5)).toBe(2);
    expect(roundHalfToEven(3.5)).toBe(4);
    expect(roundHalfToEven(4.5)).toBe(4);
  });

  it("rounds non-halves to the nearest integer", () => {
    expect(roundHalfToEven(2.0)).toBe(2);
    expect(roundHalfToEven(1.9)).toBe(2);
    expect(roundHalfToEven(2.4)).toBe(2);
    expect(roundHalfToEven(3.8)).toBe(4);
    expect(roundHalfToEven(4.75)).toBe(5);
  });

  it("diverges from Math.round on 2.5 — the parity gotcha", () => {
    // Python round(2.5) == 2; Math.round(2.5) == 3. The rank MUST use the
    // former or the Console number stops matching the bench artifact.
    expect(roundHalfToEven(2.5)).toBe(2);
    expect(Math.round(2.5)).toBe(3);
    expect(roundHalfToEven(2.5)).not.toBe(Math.round(2.5));
  });
});

describe("percentile (nearest-rank, half-to-even)", () => {
  it("returns null for an empty sample", () => {
    expect(percentile([], 50)).toBeNull();
    expect(percentile([], 95)).toBeNull();
  });

  it("returns the single sample for n=1", () => {
    expect(percentile([42], 50)).toBe(42);
    expect(percentile([42], 95)).toBe(42);
  });

  it("nearest-rank for n=2", () => {
    // p50 rank = roundHalfToEven(0.5*2=1.0) = 1 → ordered[0]
    // p95 rank = roundHalfToEven(0.95*2=1.9) = 2 → ordered[1]
    expect(percentile([10, 20], 50)).toBe(10);
    expect(percentile([10, 20], 95)).toBe(20);
  });

  it("n=5 / p50 picks ordered[1] via half-to-even (NOT ordered[2])", () => {
    const samples = [10, 20, 30, 40, 50];
    // rank = roundHalfToEven(0.5*5=2.5) = 2 → ordered[1] = 20
    expect(percentile(samples, 50)).toBe(20);
    // The Math.round path would pick ordered[2] = 30 — the divergent answer.
    expect(samples[Math.round(0.5 * 5) - 1]).toBe(30);
    expect(percentile(samples, 50)).not.toBe(30);
  });

  it("n=5 / p95 selects the top sample", () => {
    // rank = roundHalfToEven(0.95*5=4.75) = 5 → ordered[4] = 50
    expect(percentile([10, 20, 30, 40, 50], 95)).toBe(50);
  });

  it("even-n (n=4) nearest-rank", () => {
    // p50 rank = roundHalfToEven(2.0) = 2 → ordered[1] = 20
    // p95 rank = roundHalfToEven(3.8) = 4 → ordered[3] = 40
    expect(percentile([10, 20, 30, 40], 50)).toBe(20);
    expect(percentile([10, 20, 30, 40], 95)).toBe(40);
  });

  it("sorts before selecting (unordered input)", () => {
    expect(percentile([50, 10, 40, 20, 30], 50)).toBe(20);
  });
});

describe("computeAutonomyMetrics", () => {
  it("returns zero totals and {null,null,0} latencies for empty input", () => {
    const m = computeAutonomyMetrics([], [], []);
    expect(m.commands_total).toBe(0);
    expect(m.auto_commands_total).toBe(0);
    expect(m.operator_commands_total).toBe(0);
    expect(m.by_rule).toEqual({});
    expect(m.by_status).toEqual({});
    expect(m.anomaly_to_decision).toEqual({ p50_ms: null, p95_ms: null, n: 0 });
    expect(m.decision_to_dispatch).toEqual({ p50_ms: null, p95_ms: null, n: 0 });
  });

  it("groups autonomy commands by_rule (null → unspecified) + by_status; counts totals", () => {
    const commands = [
      makeCommand({ id: "c1", source: "autonomy", rule: "R1", status: "completed", target: "anomaly:a-1" }),
      makeCommand({ id: "c2", source: "autonomy", rule: "R2", status: "completed", target: "anomaly:a-1" }),
      makeCommand({ id: "c3", source: "autonomy", rule: null, status: "rejected", target: "session:current" }),
      makeCommand({ id: "c4", source: "operator", rule: null, status: "accepted", target: "anomaly:a-1" }),
    ];
    const m = computeAutonomyMetrics(commands, [], []);
    expect(m.commands_total).toBe(4);
    expect(m.auto_commands_total).toBe(3);
    expect(m.operator_commands_total).toBe(1);
    // null rule → "unspecified"; operator command excluded from both maps.
    expect(m.by_rule).toEqual({ R1: 1, R2: 1, unspecified: 1 });
    expect(m.by_status).toEqual({ completed: 2, rejected: 1 });
  });

  it("computes anomaly→decision + decision→dispatch deltas from the earliest anomaly event", () => {
    const t0 = "2026-05-26T18:00:00.000Z";
    const submitted = "2026-05-26T18:00:02.000Z"; // +2000 ms
    const inFlight = "2026-05-26T18:00:02.150Z"; // +150 ms after submit
    const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
    const event = makeEvent({ id: "e1", kind: "anomaly", anomaly_id: "a-1", ts: t0 });
    const cmd = makeCommand({
      id: "c1",
      source: "autonomy",
      rule: "R1",
      action: "verify",
      target: "anomaly:a-1",
      submitted_at: submitted,
      in_flight_at: inFlight,
      status: "in_flight",
    });
    const m = computeAutonomyMetrics([cmd], [anomaly], [event]);
    expect(m.anomaly_to_decision).toEqual({ p50_ms: 2000, p95_ms: 2000, n: 1 });
    expect(m.decision_to_dispatch).toEqual({ p50_ms: 150, p95_ms: 150, n: 1 });
  });

  it("falls back to AnomalyView.detected_at when no anomaly event is retained — and agrees with the event ts", () => {
    const t0 = "2026-05-26T18:00:00.000Z";
    const submitted = "2026-05-26T18:00:03.000Z"; // +3000 ms
    const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
    const cmd = makeCommand({ id: "c1", source: "autonomy", target: "anomaly:a-1", submitted_at: submitted });

    // No anomaly event in the deque → fallback to detected_at.
    const viaFallback = computeAutonomyMetrics([cmd], [anomaly], []);
    // With the matching anomaly event present → identical result (agreement).
    const event = makeEvent({ kind: "anomaly", anomaly_id: "a-1", ts: t0 });
    const viaEvent = computeAutonomyMetrics([cmd], [anomaly], [event]);

    expect(viaFallback.anomaly_to_decision).toEqual({ p50_ms: 3000, p95_ms: 3000, n: 1 });
    expect(viaEvent.anomaly_to_decision).toEqual(viaFallback.anomaly_to_decision);
  });

  it("prefers the EARLIEST anomaly event ts over both later events and detected_at", () => {
    const early = "2026-05-26T18:00:00.000Z";
    const late = "2026-05-26T18:00:01.000Z";
    const submitted = "2026-05-26T18:00:02.000Z";
    const anomaly = makeAnomaly({ id: "a-1", detected_at: late });
    const evLate = makeEvent({ id: "eL", kind: "anomaly", anomaly_id: "a-1", ts: late });
    const evEarly = makeEvent({ id: "eE", kind: "anomaly", anomaly_id: "a-1", ts: early });
    const cmd = makeCommand({ id: "c1", source: "autonomy", target: "anomaly:a-1", submitted_at: submitted });
    const m = computeAutonomyMetrics([cmd], [anomaly], [evLate, evEarly]);
    // earliest event wins → 2000 ms, not 1000 ms.
    expect(m.anomaly_to_decision.p50_ms).toBe(2000);
  });

  it("ignores non-anomaly events when building the earliest anomaly ts", () => {
    const t0 = "2026-05-26T18:00:00.000Z";
    const submitted = "2026-05-26T18:00:02.000Z";
    const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
    // An 'operator' event sharing the anomaly id with an EARLIER ts must not count.
    const opEvent = makeEvent({ kind: "operator", anomaly_id: "a-1", ts: "2026-05-26T17:00:00.000Z" });
    const anomEvent = makeEvent({ kind: "anomaly", anomaly_id: "a-1", ts: t0 });
    const cmd = makeCommand({ id: "c1", source: "autonomy", target: "anomaly:a-1", submitted_at: submitted });
    const m = computeAutonomyMetrics([cmd], [anomaly], [opEvent, anomEvent]);
    expect(m.anomaly_to_decision.p50_ms).toBe(2000);
  });

  it("drops negative deltas (clock skew / late frame)", () => {
    const t0 = "2026-05-26T18:00:05.000Z";
    const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
    const event = makeEvent({ kind: "anomaly", anomaly_id: "a-1", ts: t0 });
    const cmd = makeCommand({
      id: "c1",
      source: "autonomy",
      target: "anomaly:a-1",
      submitted_at: "2026-05-26T18:00:00.000Z", // BEFORE the anomaly ts → negative
      in_flight_at: "2026-05-26T17:59:59.000Z", // BEFORE submit → negative
    });
    const m = computeAutonomyMetrics([cmd], [anomaly], [event]);
    expect(m.anomaly_to_decision).toEqual({ p50_ms: null, p95_ms: null, n: 0 });
    expect(m.decision_to_dispatch).toEqual({ p50_ms: null, p95_ms: null, n: 0 });
  });

  it("excludes operator commands and counts no dispatch when in_flight_at is null (DISMISS)", () => {
    const t0 = "2026-05-26T18:00:00.000Z";
    const anomaly = makeAnomaly({ id: "a-1", detected_at: t0 });
    const event = makeEvent({ kind: "anomaly", anomaly_id: "a-1", ts: t0 });
    const operatorCmd = makeCommand({
      id: "op",
      source: "operator",
      target: "anomaly:a-1",
      submitted_at: "2026-05-26T18:00:02.000Z",
      in_flight_at: "2026-05-26T18:00:02.100Z",
    });
    const autoDismiss = makeCommand({
      id: "auto",
      source: "autonomy",
      rule: "R3",
      action: "dismiss",
      target: "anomaly:a-1",
      submitted_at: "2026-05-26T18:00:02.000Z",
      in_flight_at: null, // DISMISS never dispatches a mission
    });
    const m = computeAutonomyMetrics([operatorCmd, autoDismiss], [anomaly], [event]);
    // Only the autonomy command counts toward anomaly→decision.
    expect(m.anomaly_to_decision.n).toBe(1);
    // No autonomy command has in_flight_at → dispatch n=0.
    expect(m.decision_to_dispatch.n).toBe(0);
  });

  it("aggregates multiple dispatch latencies via nearest-rank p50/p95", () => {
    const commands = [10, 20, 30, 40, 50].map((d, i) => {
      const submitted = `2026-05-26T18:00:0${i}.000Z`;
      const inFlight = new Date(Date.parse(submitted) + d).toISOString();
      return makeCommand({
        id: `c${i}`,
        source: "autonomy",
        rule: "R1",
        target: "session:current", // no anomaly delta, only dispatch delta
        submitted_at: submitted,
        in_flight_at: inFlight,
      });
    });
    const m = computeAutonomyMetrics(commands, [], []);
    // deltas [10,20,30,40,50] → p50 = ordered[1] = 20, p95 = ordered[4] = 50.
    expect(m.decision_to_dispatch).toEqual({ p50_ms: 20, p95_ms: 50, n: 5 });
    expect(m.anomaly_to_decision.n).toBe(0);
  });

  // TODO(2a): once the manual wildfire run commits a non-empty
  // docs/bench/artifacts/phase-7e-wildfire_owner_land-*.json, assert
  // computeAutonomyMetrics reproduces its `latencies_ms` block byte-for-byte
  // (display-rounded to 1 decimal) for the same audit frames.
  it.todo("matches a committed phase-7e-*.json artifact once 2a's manual run produces one");
});
