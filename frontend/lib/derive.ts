/**
 * Phase 2 derivation helpers.
 *
 * SwarmOS is the source of truth. Anything still computed on the client lives
 * here, flagged `derived: true`, and renders with the `DERIVED` eyebrow so the
 * operator never confuses a UI fallback with verified state. Each helper has
 * a paired roadmap entry: Phase 3 strips this file down to UI-only formatting.
 */

import type {
  AnomalyView,
  AwarenessBreakdown,
  DockState,
  OperatingMode,
  UnitState,
} from "./api";

export type Derived<T> = { value: T; derived: true; reason: string };
export type Truth<T> = { value: T; derived: false };
export type MaybeDerived<T> = Derived<T> | Truth<T>;

export const truth = <T>(value: T): Truth<T> => ({ value, derived: false });
export const derived = <T>(value: T, reason: string): Derived<T> => ({
  value,
  derived: true,
  reason,
});

// ── Operating mode ─────────────────────────────────────────────────────────────
// `SWARM_STATE.mode` is computed server-side but not yet projected on the WS
// bus as its own frame; the snapshot only carries it indirectly via Session
// payloads. Until Phase 3 emits an `operating_mode` frame, we mirror the
// server's `compute_mode` rule client-side from units + anomalies.

export function deriveOperatingMode(
  units: UnitState[],
  anomalies: AnomalyView[]
): Derived<OperatingMode> {
  const attention = units.some((u) => u.fsm_state === "ERROR" || u.fsm_state === "OFFLINE");
  const verified = anomalies.find((a) => a.state === "verified" || a.state === "escalated");
  const pending = anomalies.find((a) => a.state === "pending" || a.state === "verifying");
  const airborne = units.some(
    (u) =>
      u.fsm_state === "TAKEOFF" ||
      u.fsm_state === "EN_ROUTE" ||
      u.fsm_state === "ON_STATION" ||
      u.fsm_state === "RTL" ||
      u.fsm_state === "LANDING" ||
      u.fsm_state === "DOCKING"
  );
  const mode: OperatingMode = attention
    ? "maintenance"
    : verified
      ? "escalation"
      : pending
        ? "verification"
        : airborne
          ? "patrol"
          : "rest";
  return derived(mode, "mode mirrors server compute_mode until Phase 3 frame");
}

// ── Verifier ───────────────────────────────────────────────────────────────────
// The server picks the verifier inside the lock but only persists it through
// `AnomalyView.verifying_agent`. When that is missing we fall back to nearest
// airborne unit by haversine-lite. Phase 3 will surface a stable verifier id
// on every awareness frame.

export function deriveVerifier(
  units: UnitState[],
  focusAnomaly: AnomalyView | null
): MaybeDerived<UnitState | null> {
  if (!focusAnomaly) return truth<UnitState | null>(null);
  if (focusAnomaly.verifying_agent) {
    const u = units.find((x) => x.agent_id === focusAnomaly.verifying_agent);
    if (u) return truth<UnitState | null>(u);
  }
  const airborne = units.filter(
    (u) => u.fsm_state !== "DOCKED" && u.fsm_state !== "OFFLINE" && u.fsm_state !== "ERROR"
  );
  const candidates = airborne.length ? airborne : units;
  if (!candidates.length) return truth<UnitState | null>(null);
  const sorted = [...candidates].sort((a, b) => {
    const da = Math.hypot(a.geo.lat - focusAnomaly.geo.lat, a.geo.lon - focusAnomaly.geo.lon);
    const db = Math.hypot(b.geo.lat - focusAnomaly.geo.lat, b.geo.lon - focusAnomaly.geo.lon);
    return da - db;
  });
  return derived(sorted[0], "verifier inferred by proximity — Phase 3 emits it server-side");
}

// ── Awareness fallback ─────────────────────────────────────────────────────────
// `AwarenessBreakdown` is server-issued, but until the first WS frame lands we
// keep a quiet zero-value placeholder so the rail does not appear empty. The
// fallback never overwrites a real reading.

export function fallbackAwareness(now: Date): AwarenessBreakdown {
  return {
    score: 0,
    factors: {},
    blind_spot_sectors: [],
    stale_sectors: [],
    risk_state: "rest",
    ts: now.toISOString(),
  };
}

// ── Dock summary ───────────────────────────────────────────────────────────────
// Phase 1 emits one `DockState` per dock. The Console shows a primary dock in
// the right rail; this helper picks it and exposes a derived flag when the
// pick is heuristic (first non-offline).

export function pickPrimaryDock(docks: DockState[]): MaybeDerived<DockState | null> {
  if (docks.length === 0) return truth<DockState | null>(null);
  if (docks.length === 1) return truth<DockState | null>(docks[0]);
  const primary = docks.find((d) => d.status === "online") ?? docks[0];
  return derived(primary, "primary dock picked client-side — Phase 3 marks it server-side");
}

// ── Time / clock ───────────────────────────────────────────────────────────────
// The clock is purely presentational. We expose hh:mm UTC + dd · mm · yy.

export function formatClock(d: Date): { time: string; date: string } {
  const pad = (n: number) => String(n).padStart(2, "0");
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
  const dd = pad(d.getUTCDate());
  const mm = pad(d.getUTCMonth() + 1);
  const yy = String(d.getUTCFullYear()).slice(2);
  return { time, date: `${dd} · ${mm} · ${yy}` };
}

// ── Mode copy ──────────────────────────────────────────────────────────────────
// Mirrors `core.swarm_core.voice.describe_mode` so the bottom-left mode line
// reads exactly like a backend-emitted Event body would.

export function describeMode(mode: OperatingMode): string {
  switch (mode) {
    case "rest":
      return "territory under awareness · system at rest";
    case "patrol":
      return "patrol in progress · coverage refreshing";
    case "verification":
      return "anomaly verifying · awaiting confidence";
    case "escalation":
      return "event verified · operator decision required";
    case "maintenance":
      return "unit attention required · routing adjusted";
  }
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
