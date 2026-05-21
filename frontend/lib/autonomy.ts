/**
 * Phase 7.C — shared autonomy selector for the Console.
 *
 * Mirrors the kernel's `_NON_TERMINAL_STATUSES` predicate in
 * `swarm_os/autonomy.py:62-64` so the AUTO eyebrow only renders while a
 * decision is still in flight. Used by AnomalySummary, the verify panel
 * header, and the mobile alert surface.
 */

import type { OperatorCommand } from "./api";

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
