"use client";

/**
 * AutonomyDecision — the Console default inversion (Phase 8.A).
 *
 * "SwarmOS decides. Console supervises." This block leads the viewport's
 * right rail when the autonomy baseline is on: it surfaces *what SwarmOS
 * decided* about the focus anomaly first, then demotes the operator's
 * intents to override controls beneath an `— override` eyebrow.
 *
 * Every value is observed, never invented: the verdict + rule come from a
 * real `source="autonomy"` audit command (`autonomyStance`), and the
 * `holding` / `clear` stances describe the *absence* of a command rather
 * than fabricating a number (CLAUDE.md truth-layer rule). No red — the
 * decision accent is Orbital Blue; attention stays amber elsewhere.
 */

import { autonomyStance } from "@/lib/autonomy";
import {
  ACTION_LABELS,
  AUTONOMY_STANCE_COPY,
  AUTONOMY_STATUS_COPY,
  AUTONOMY_VERB,
  OVERRIDE_LABEL,
} from "@/lib/copy";
import { useFocusAnomaly, useSwarm } from "@/lib/state";
import type { CommandStatus, OperatorAction } from "@/lib/api";
import { SectionLabel } from "./QuietPanel";

function verdictVerb(action: OperatorAction): string {
  if (action === "verify" || action === "escalate" || action === "dismiss") {
    return AUTONOMY_VERB[action];
  }
  return action.replace(/_/g, " ");
}

function statusSub(status: CommandStatus): string {
  switch (status) {
    case "completed":
      return AUTONOMY_STATUS_COPY.logged;
    case "rejected":
      return AUTONOMY_STATUS_COPY.held;
    case "timed_out":
      return AUTONOMY_STATUS_COPY.timed_out;
    default:
      return AUTONOMY_STATUS_COPY.in_flight;
  }
}

export function AutonomyDecision() {
  const { commands, autonomyEnabled, dispatch } = useSwarm();
  const focus = useFocusAnomaly();
  const stance = autonomyStance(autonomyEnabled, focus, commands);

  // Autonomy baseline off: no inversion — the legacy operator-led
  // InlineActions in QuietPanel stands. Render nothing here.
  if (stance.kind === "manual") return null;

  let head: string;
  let sub: string;
  let rule: string | null = null;
  if (stance.kind === "decided") {
    head = verdictVerb(stance.command.action);
    sub = statusSub(stance.command.status);
    rule = stance.command.rule ?? null;
  } else if (stance.kind === "holding") {
    head = AUTONOMY_STANCE_COPY.holding.head;
    const pct = Math.round(stance.anomaly.confidence * 100);
    sub = `${AUTONOMY_STANCE_COPY.holding.sub} · confidence ${String(pct).padStart(3, "0")} %`;
  } else {
    head = AUTONOMY_STANCE_COPY.clear.head;
    sub = AUTONOMY_STANCE_COPY.clear.sub;
  }

  return (
    <section className="flex flex-col gap-3" data-testid="autonomy-decision">
      <SectionLabel>SwarmOS</SectionLabel>

      <div className="flex items-baseline justify-between gap-2">
        <span
          className="font-display text-platinum"
          style={{ fontSize: 22, lineHeight: 1.1 }}
          data-testid="autonomy-verdict"
        >
          {head}
        </span>
        {rule && (
          <span
            className="eyebrow-mono text-orbital-blue whitespace-nowrap"
            data-testid="autonomy-rule-chip"
          >
            AUTO · {rule.toLowerCase()}
          </span>
        )}
      </div>

      <span className="eyebrow-mono text-ash">{sub}</span>

      <OverrideRow
        verifyTarget={focus ? `anomaly:${focus.id}` : null}
        dispatch={dispatch}
      />
    </section>
  );
}

function OverrideRow({
  verifyTarget,
  dispatch,
}: {
  verifyTarget: string | null;
  dispatch: ReturnType<typeof useSwarm>["dispatch"];
}) {
  const verifyEnabled = !!verifyTarget;
  // Override buttons are deliberately secondary (ghost) — the autonomy
  // verdict above carries the visual weight. Verify is the only intent
  // that targets the focus anomaly; hold-patrol is always available.
  const ghost =
    "flex-1 border border-graphite text-platinum font-display text-ui rounded-input px-3 py-2 transition-all duration-press ease-swarm hover:bg-graphite/40 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed";
  return (
    <div className="flex flex-col gap-2">
      <SectionLabel>{OVERRIDE_LABEL}</SectionLabel>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!verifyEnabled}
          onClick={() => {
            if (verifyTarget) void dispatch("verify", verifyTarget);
          }}
          className={ghost}
          title={ACTION_LABELS.verify.hint}
        >
          {ACTION_LABELS.verify.label}
        </button>
        <button
          type="button"
          onClick={() => void dispatch("hold_patrol", "session:current")}
          className={ghost}
          title={ACTION_LABELS.hold_patrol.hint}
        >
          {ACTION_LABELS.hold_patrol.label}
        </button>
      </div>
    </div>
  );
}
