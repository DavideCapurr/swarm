"use client";

/**
 * ActionRail — verify + hold patrol, as an inline row of two buttons.
 *
 * Slimmed from the original card surface: dismiss and return live in
 * the verify/[id] route and the UnitDetail swap respectively. Voice
 * pulled from `lib/copy.ts`.
 */

import { useEffect, useState } from "react";

import { useFocusAnomaly, useSwarm } from "@/lib/state";
import { ACTION_LABELS, OVERRIDE_LABEL } from "@/lib/copy";

type WiredIntent = "verify" | "hold_patrol";

type Phase = "idle" | "sending" | "accepted" | "rejected";

type Outcome = { phase: Phase; detail?: string };

export function ActionRail() {
  const { dispatch, autonomyEnabled } = useSwarm();
  const focus = useFocusAnomaly();
  const [state, setState] = useState<Record<WiredIntent, Outcome>>({
    verify: { phase: "idle" },
    hold_patrol: { phase: "idle" },
  });

  useEffect(() => {
    const dirty = (Object.keys(state) as WiredIntent[]).filter(
      (k) => state[k].phase !== "idle"
    );
    if (dirty.length === 0) return;
    const id = setTimeout(() => {
      setState((prev) => {
        const next = { ...prev };
        for (const k of dirty) next[k] = { phase: "idle" };
        return next;
      });
    }, 3_500);
    return () => clearTimeout(id);
  }, [state]);

  const targets: Record<WiredIntent, string | null> = {
    verify: focus ? `anomaly:${focus.id}` : null,
    hold_patrol: "session:current",
  };

  async function send(intent: WiredIntent) {
    const target = targets[intent];
    if (!target) return;
    setState((prev) => ({ ...prev, [intent]: { phase: "sending" } }));
    try {
      const res = await dispatch(intent, target);
      setState((prev) => ({
        ...prev,
        [intent]: res.ok
          ? { phase: "accepted", detail: res.body.status }
          : {
              phase: "rejected",
              detail: res.body.rejected_reason ?? `code ${res.status}`,
            },
      }));
    } catch (e) {
      setState((prev) => ({
        ...prev,
        [intent]: {
          phase: "rejected",
          detail: e instanceof Error ? e.message : "error",
        },
      }));
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Phase 8.A — on autonomy-enabled sites these intents override the
          SwarmOS decision; frame them as such. Autonomy-off sites keep the
          bare row. */}
      {autonomyEnabled && (
        <span className="eyebrow-mono text-ash" data-testid="override-label">
          <span className="mr-2">—</span>
          {OVERRIDE_LABEL}
        </span>
      )}
      <div className="flex gap-2">
      <IntentButton
        label={ACTION_LABELS.verify.label}
        hint={ACTION_LABELS.verify.hint}
        enabled={!!targets.verify}
        outcome={state.verify}
        variant="primary"
        onPress={() => send("verify")}
      />
      <IntentButton
        label={ACTION_LABELS.hold_patrol.label}
        hint={ACTION_LABELS.hold_patrol.hint}
        enabled={!!targets.hold_patrol}
        outcome={state.hold_patrol}
        variant="secondary"
        onPress={() => send("hold_patrol")}
      />
      </div>
    </div>
  );
}

function IntentButton({
  label,
  hint,
  enabled,
  outcome,
  variant,
  onPress,
}: {
  label: string;
  hint: string;
  enabled: boolean;
  outcome: Outcome;
  variant: "primary" | "secondary";
  onPress: () => void;
}) {
  const base =
    variant === "primary"
      ? "bg-platinum text-absolute-black"
      : "bg-absolute-black border border-graphite text-platinum hover:bg-graphite/40";
  const phaseClass =
    outcome.phase === "accepted"
      ? "border border-signal-green text-signal-green bg-absolute-black"
      : outcome.phase === "rejected"
        ? "border border-launch-amber text-launch-amber bg-absolute-black"
        : outcome.phase === "sending"
          ? "border border-orbital-blue text-orbital-blue bg-absolute-black"
          : base;
  const text =
    outcome.phase === "accepted"
      ? "accepted"
      : outcome.phase === "rejected"
        ? outcome.detail ?? "rejected"
        : outcome.phase === "sending"
          ? "sending"
          : label;
  return (
    <button
      type="button"
      onClick={onPress}
      disabled={!enabled || outcome.phase === "sending"}
      title={hint}
      className={`flex-1 font-display text-ui rounded-input px-3 py-2 transition-all duration-press ease-swarm hover:brightness-105 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed ${phaseClass}`}
    >
      {text}
    </button>
  );
}
