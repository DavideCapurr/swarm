"use client";

/**
 * ActionRail — operator intents (PDF §5.7).
 *
 * Phase 2 wires four: verify, hold-patrol, dismiss, return. The four advisory
 * intents (increase scan freq, mark known, escalate, export report) are
 * rendered as disabled buttons with an advisory eyebrow until later phases.
 *
 * No manual drone commands. These are intents; SwarmOS decides.
 */

import { useEffect, useState } from "react";

import { useFocusAnomaly, useSwarm } from "@/lib/state";
import {
  IconDismiss,
  IconHold,
  IconReturn,
  IconVerify,
  type IconProps,
} from "@/icons";
import { Eyebrow } from "./Eyebrow";

type WiredIntent = "verify" | "hold_patrol" | "dismiss" | "return";

type Phase = "idle" | "sending" | "accepted" | "rejected";

type Outcome = { phase: Phase; detail?: string };

export function ActionRail({ selectedAgentId }: { selectedAgentId?: string | null }) {
  const { dispatch, mode, units } = useSwarm();
  const focus = useFocusAnomaly();
  const [state, setState] = useState<Record<WiredIntent, Outcome>>({
    verify: { phase: "idle" },
    hold_patrol: { phase: "idle" },
    dismiss: { phase: "idle" },
    return: { phase: "idle" },
  });

  // Reset transient outcome after 3 s so the rail breathes.
  useEffect(() => {
    const dirty = (Object.keys(state) as WiredIntent[]).filter((k) => state[k].phase !== "idle");
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

  const focusedUnit =
    selectedAgentId && units.find((u) => u.agent_id === selectedAgentId)
      ? selectedAgentId
      : null;

  const targets: Record<WiredIntent, string | null> = {
    verify: focus ? `anomaly:${focus.id}` : null,
    hold_patrol: "fleet:all",
    dismiss: focus ? `anomaly:${focus.id}` : null,
    return: focusedUnit ? `unit:${focusedUnit}` : null,
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
          : { phase: "rejected", detail: res.body.rejected_reason ?? `code ${res.status}` },
      }));
    } catch (e) {
      setState((prev) => ({
        ...prev,
        [intent]: { phase: "rejected", detail: e instanceof Error ? e.message : "error" },
      }));
    }
  }

  return (
    <div className="card p-4 flex flex-col gap-3">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Action rail</Eyebrow>
        <span className="eyebrow-mono">mode · {mode.value}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <IntentButton
          icon={IconVerify}
          label="Verify"
          hint="dispatch nearest unit"
          enabled={!!targets.verify}
          outcome={state.verify}
          accent="text-orbital-blue"
          onPress={() => send("verify")}
        />
        <IntentButton
          icon={IconHold}
          label="Hold patrol"
          hint="pause coverage routine"
          enabled={!!targets.hold_patrol}
          outcome={state.hold_patrol}
          accent="text-platinum"
          onPress={() => send("hold_patrol")}
        />
        <IntentButton
          icon={IconDismiss}
          label="Dismiss"
          hint="mark anomaly resolved"
          enabled={!!targets.dismiss}
          outcome={state.dismiss}
          accent="text-muted-silver"
          onPress={() => send("dismiss")}
        />
        <IntentButton
          icon={IconReturn}
          label="Return unit"
          hint={focusedUnit ? "send unit to dock" : "select a unit first"}
          enabled={!!targets.return}
          outcome={state.return}
          accent="text-platinum"
          onPress={() => send("return")}
        />
      </div>
      <div className="h-px bg-gunmetal" />
      <span className="eyebrow-mono text-ash">
        intents only · swarmos decides — increase scan · mark known · escalate · export report arrive in later phases
      </span>
    </div>
  );
}

function IntentButton({
  icon: Icon,
  label,
  hint,
  enabled,
  outcome,
  accent,
  onPress,
}: {
  icon: (p: IconProps) => React.ReactElement;
  label: string;
  hint: string;
  enabled: boolean;
  outcome: Outcome;
  accent: string;
  onPress: () => void;
}) {
  const tone =
    outcome.phase === "accepted"
      ? "border-signal-green text-signal-green"
      : outcome.phase === "rejected"
        ? "border-launch-amber text-launch-amber"
        : outcome.phase === "sending"
          ? "border-orbital-blue text-orbital-blue"
          : `border-graphite ${accent}`;
  const phaseLabel =
    outcome.phase === "accepted"
      ? "accepted"
      : outcome.phase === "rejected"
        ? outcome.detail ?? "rejected"
        : outcome.phase === "sending"
          ? "sending"
          : enabled
            ? hint
            : hint;

  return (
    <button
      type="button"
      onClick={onPress}
      disabled={!enabled || outcome.phase === "sending"}
      className={`flex flex-col items-start gap-2 border ${tone} rounded-input p-3 transition-all duration-press ease-swarm bg-absolute-black hover:brightness-110 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed text-left`}
    >
      <span className="flex items-center gap-2">
        <Icon size={20} />
        <span className="font-display text-ui text-platinum">{label}</span>
      </span>
      <span className="eyebrow-mono text-ash">{phaseLabel}</span>
    </button>
  );
}
