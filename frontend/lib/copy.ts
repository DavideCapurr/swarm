/**
 * copy.ts — central voice layer for the Console.
 *
 * Plain Voice Rule v1: sentence case, ≤7-word sentences, period-bound, numbers
 * with units, state-as-verb. Backend types stay untouched; this file maps
 * enum values to operator-facing display strings.
 *
 * Companion test `lib/__tests__/copy.test.ts` greps every exported string
 * for FORBIDDEN_WORDS and fails CI on drift.
 */

import type {
  AgentState,
  AnomalyState,
  OperatingMode,
  OperatorAction,
  RiskState,
  SectorState,
} from "./api";
import type { SwarmState } from "./tokens";

// ── Unit label ────────────────────────────────────────────────────────────────
// "sim-1" → "unit 001". Replaces four duplicated implementations across
// Map.tsx, FleetGrid.tsx, AnomalySummary.tsx, LinkHealth.tsx.

export function UNIT_LABEL(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toLowerCase();
  return `unit ${n}`;
}

export function UNIT_LABEL_RING(agentId: string): string {
  return `${UNIT_LABEL(agentId)} · ring a`;
}

// ── Sector state ──────────────────────────────────────────────────────────────

export const SECTOR_STATE_COPY: Record<SectorState, string> = {
  idle: "idle",
  covered: "covered",
  stale: "needs refresh",
  blind: "uncovered",
  anomaly: "verifying",
};

// ── Agent state ───────────────────────────────────────────────────────────────
// Maps backend FSM to operator verbs + the SWARM accent state.

export const AGENT_STATE_COPY: Record<AgentState, { verb: string; swarm: SwarmState }> = {
  DOCKED: { verb: "docked", swarm: "rest" },
  TAKEOFF: { verb: "patrolling", swarm: "connected" },
  EN_ROUTE: { verb: "patrolling", swarm: "operational" },
  ON_STATION: { verb: "patrolling", swarm: "operational" },
  RTL: { verb: "returning", swarm: "operational" },
  LANDING: { verb: "returning", swarm: "operational" },
  DOCKING: { verb: "returning", swarm: "operational" },
  ERROR: { verb: "attention", swarm: "attention" },
  OFFLINE: { verb: "offline", swarm: "rest" },
};

// ── Anomaly state ─────────────────────────────────────────────────────────────

export const ANOMALY_STATE_COPY: Record<AnomalyState, string> = {
  pending: "detected",
  verifying: "verifying",
  verified: "verified",
  dismissed: "dismissed",
  escalated: "operator action",
  marked_known: "known",
};

// ── Operating mode ────────────────────────────────────────────────────────────

export const MODE_COPY: Record<
  OperatingMode,
  { label: string; narrative_en: string; narrative_it: string }
> = {
  rest: {
    label: "standby",
    narrative_en: "standby. territory under watch.",
    narrative_it: "in attesa. territorio sotto controllo.",
  },
  patrol: {
    label: "patrolling",
    narrative_en: "patrol in flight. coverage refreshing.",
    narrative_it: "pattuglia in volo. copertura in aggiornamento.",
  },
  verification: {
    label: "verifying",
    narrative_en: "unit verifying. checking signal.",
    narrative_it: "unità in verifica. controllo segnale.",
  },
  escalation: {
    label: "attention",
    narrative_en: "anomaly verified. operator decision required.",
    narrative_it: "anomalia verificata. richiesta decisione operatore.",
  },
  maintenance: {
    label: "attention",
    narrative_en: "attention required. routing adjusted.",
    narrative_it: "attenzione richiesta. percorso aggiornato.",
  },
};

// ── Risk state ────────────────────────────────────────────────────────────────

export const RISK_STATE_COPY: Record<
  RiskState,
  { label: string; accent: "ash" | "orbital-blue" | "launch-amber" }
> = {
  rest: { label: "at rest", accent: "ash" },
  aware: { label: "patrolling", accent: "orbital-blue" },
  elevated: { label: "attention", accent: "launch-amber" },
};

// ── Scene header (YC pitch surface) ──────────────────────────────────────────
// Bilingual editorial claim above the viewport. Justified by YC playbook
// §5.4 (one-line answer), §12.1 (demo open-on-territory), §15 (claim
// discipline + sim-vs-real boundary).

export const SCENE_HEADER = {
  en: { title: "Wildfire patrol.", italic: "Autonomous, on private land." },
  it: { title: "Pattuglia incendi.", italic: "Autonoma, su terreno privato." },
  sim_badge: "simulation · wildfire scenario",
} as const;

// ── Footer ────────────────────────────────────────────────────────────────────

export const FOOTER_COPY = {
  en: "One map. One intention.",
  it: "Una mappa. Una sola intenzione.",
} as const;

// ── Operator action labels ────────────────────────────────────────────────────

export const ACTION_LABELS: Record<
  OperatorAction,
  { label: string; hint: string }
> = {
  verify: { label: "Verify", hint: "dispatch nearest unit" },
  hold_patrol: { label: "Hold patrol", hint: "pause all patrols" },
  dismiss: { label: "Dismiss", hint: "mark anomaly resolved" },
  return: { label: "Return unit", hint: "send unit to dock" },
  increase_scan_freq: { label: "Increase scan", hint: "raise patrol cadence" },
  mark_known: { label: "Mark known", hint: "log as recognised signal" },
  escalate: { label: "Escalate", hint: "raise to operator attention" },
  export_report: { label: "Export report", hint: "save session audit" },
  emergency_rtl_all: { label: "Return all units", hint: "commander only" },
};

// ── Autonomy observatory (Phase 8.A) ─────────────────────────────────────────
// The Console default inversion: SwarmOS decides, the operator supervises.
// The rail surfaces *what SwarmOS decided* first; the four intents become
// override controls. These are display-only strings — no operational truth
// invented client-side (CLAUDE.md hard rule). Confidence-bound voice.

// The autonomy verdict, as a past/present-tense headline keyed by the
// command's action. Only the three actionable verdicts (R1/R2/R3) appear;
// WAIT never becomes a command, so it has no headline here.
export const AUTONOMY_VERB: Record<"verify" | "escalate" | "dismiss", string> = {
  verify: "verifying sector",
  escalate: "escalated to operator",
  dismiss: "dismissed signal",
};

// The stance when no command is bound to the focus anomaly. `holding`
// mirrors the engine's WAIT verdict (no autonomy command observed yet);
// `clear` is the no-anomaly observatory rest state. Each is a description
// of what the Console observes, never a fabricated number.
export const AUTONOMY_STANCE_COPY = {
  holding: { head: "holding", sub: "assessing signal" },
  clear: { head: "watching", sub: "territory clear" },
} as const;

// Status-aware sub-line for a bound autonomy decision.
export const AUTONOMY_STATUS_COPY: Record<
  "in_flight" | "logged" | "held" | "timed_out",
  string
> = {
  in_flight: "decision in flight",
  logged: "decision logged",
  held: "held by safety shield",
  timed_out: "decision timed out",
};

// The label that frames the operator's intents as overrides of the
// autonomy decision (the eyebrow above the demoted buttons).
export const OVERRIDE_LABEL = "override";

// ── Forbidden words (guard test) ──────────────────────────────────────────────
// Every string exported from this module must avoid these. Catches drift
// before it reaches the operator surface. Display-only — backend types
// (e.g. AgentState "DOCKED") remain untouched.

export const FORBIDDEN_WORDS: readonly string[] = [
  "drone",
  "AI",
  "smart",
  "next-gen",
  "platform",
  "solution",
  "robust",
  "scalable",
  "intruder",
  "alarm",
];
