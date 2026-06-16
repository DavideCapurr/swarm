/**
 * Phase 7.C — shared autonomy selector for the Console.
 *
 * Mirrors the kernel's `_NON_TERMINAL_STATUSES` predicate in
 * `swarm_os/autonomy.py:62-64` so the AUTO eyebrow only renders while a
 * decision is still in flight. Used by AnomalySummary, the verify panel
 * header, and the mobile alert surface.
 */

import type { AnomalyView, OperatorCommand } from "./api";

const NON_TERMINAL_STATUSES = new Set<OperatorCommand["status"]>([
  "submitted",
  "accepted",
  "in_flight",
]);

/**
 * Return the most recent non-terminal autonomy-issued command that
 * targets the given anomaly id, or null when none exists. Sorts by
 * `submitted_at` descending so the latest decision wins when more than
 * one is in flight on the same target.
 */
export function findActiveAutonomyCommand(
  commands: OperatorCommand[],
  anomalyId: string
): OperatorCommand | null {
  const target = `anomaly:${anomalyId}`;
  const candidates = commands.filter(
    (c) =>
      c.source === "autonomy" &&
      c.target === target &&
      NON_TERMINAL_STATUSES.has(c.status)
  );
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => (a.submitted_at < b.submitted_at ? 1 : -1));
  return candidates[0];
}

/**
 * Return the most recent autonomy-issued command targeting the given anomaly
 * id, or null when none exists — *regardless of terminal status*.
 *
 * Phase 7 (WS1d): the AUTO eyebrow must persist after the VERIFY / ESCALATE
 * command COMPLETES, because "SwarmOS decided this" is exactly the moment that
 * matters for attribution — a terminal ESCALATED callout reading
 * `auto · r2 · anomaly escalated` is the money shot the VO points at. This
 * reads a real audit record (the Console retains terminal commands via
 * `state.tsx` `upsertById`), so it is truthful, not DERIVED fabrication.
 * Identical to `findActiveAutonomyCommand` minus the terminal-status filter.
 */
export function findLatestAutonomyCommand(
  commands: OperatorCommand[],
  anomalyId: string
): OperatorCommand | null {
  const target = `anomaly:${anomalyId}`;
  const candidates = commands.filter(
    (c) => c.source === "autonomy" && c.target === target
  );
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => (a.submitted_at < b.submitted_at ? 1 : -1));
  return candidates[0];
}

/**
 * Phase 8.A — the observatory stance for the Console default inversion.
 *
 * "SwarmOS decides. Console supervises." Instead of leading with the
 * operator's intents, the rail leads with *what SwarmOS decided*. This
 * pure selector collapses the focus anomaly + autonomy commands into one
 * of four stances the rail renders:
 *
 *   - `decided` — an autonomy command (R1/R2/R3) is bound to the focus
 *     anomaly. The rail surfaces the verdict + rule; operator intents
 *     become overrides.
 *   - `holding` — autonomy is on and a focus anomaly exists, but no
 *     autonomy command targets it yet. Mirrors the engine's WAIT verdict
 *     (the Console observes no command — it never fabricates one).
 *   - `clear` — autonomy is on with no focus anomaly: observatory rest.
 *   - `manual` — autonomy baseline off: no inversion, the legacy
 *     operator-led flow stands.
 *
 * Side-effect-free so it is trivially unit-tested without the provider.
 */
export type AutonomyStance =
  | { kind: "decided"; command: OperatorCommand }
  | { kind: "holding"; anomaly: AnomalyView }
  | { kind: "clear" }
  | { kind: "manual" };

export function autonomyStance(
  autonomyEnabled: boolean,
  focus: AnomalyView | null,
  commands: OperatorCommand[]
): AutonomyStance {
  if (!autonomyEnabled) return { kind: "manual" };
  if (focus) {
    const command = findLatestAutonomyCommand(commands, focus.id);
    if (command) return { kind: "decided", command };
    return { kind: "holding", anomaly: focus };
  }
  return { kind: "clear" };
}
