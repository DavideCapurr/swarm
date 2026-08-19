"use client";

/**
 * NarrationStrip — one line saying what just happened.
 *
 * The rest of this surface is built for an operator who can pause on it. A
 * first-time viewer watching a recording once through cannot: the composition,
 * the failure and the replacement all land in panels that reward reading, and
 * by the time they have been read the beat is over. This is the one element on
 * the surface addressed to that viewer.
 *
 * It is a derivation, not copy. Every line below is a function of state the
 * surface already computed — the focused objective's own `state`, its role
 * count, and the adaptation beat `MissionAuthorityPanel` is driven by. There is
 * no scene script, no timeline, and nothing here can say something the panels
 * are not simultaneously saying. If SwarmOS never publishes a failure, the
 * failure line never renders.
 *
 * Voice is the product's: confidence-bound, uppercase operational type, no
 * `FORBIDDEN_WORDS` token, and never a manual-control verb — the operator sends
 * intents and SwarmOS decides, and the narration describes SwarmOS deciding.
 */

import type { ObjectiveAuthority, SwarmComposition } from "@/lib/authority";

import { HAIRLINE } from "./Surface";
import type { AdaptationBeat } from "./useAdaptation";

/** Height the strip claims, so the camera's clear area can account for it. */
export const NARRATION_HEIGHT = 30;

/** Roles whose holder is present and has not failed — the panel's own count. */
function rolesHeld(objective: ObjectiveAuthority): number {
  return objective.slots.filter(
    (slot) => slot.agentId && slot.memberState !== "FAILED" && slot.phase !== "FAILED"
  ).length;
}

const pad = (value: number) => String(value).padStart(2, "0");

/** The swarm SwarmOS dispatched to reinforce another, when it has dispatched one. */
function reinforcementOf(objective: ObjectiveAuthority): SwarmComposition | null {
  return objective.swarms.find((swarm) => swarm.reinforcesGroupId != null) ?? null;
}

/**
 * A swarm that never reached the strength it was asked for.
 *
 * Read as a *composition* shortfall — roles SwarmOS could not fill at all,
 * which is ADR-0012 partial-strength composition — and not as a holder that has
 * since dropped out. The second is the adaptation beat, it already has a line,
 * and it already outranks this one; conflating them would have the strip
 * announce a shortfall in the middle of a replacement that is fixing it.
 */
function underStrength(objective: ObjectiveAuthority): SwarmComposition | null {
  return (
    objective.swarms.find((swarm) => swarm.composedMembers < swarm.requestedMembers) ?? null
  );
}

/**
 * The whole vocabulary, in priority order.
 *
 * The beat outranks the objective's settled state, because the beat is the
 * thing that just changed and this line exists to say what just changed.
 */
export function narrationFor(
  objective: ObjectiveAuthority | null,
  beat: AdaptationBeat
): string {
  if (!objective) return "AWAITING FLEET STATE";
  if (beat.phase === "adapting") return "EXECUTOR LOST · SWARMOS SELECTING REPLACEMENT";
  if (beat.phase === "restored") return "REPLACEMENT DISPATCHED · GROUP RESTORED";

  switch (objective.state) {
    case "COMPOSING":
      return "OBJECTIVE DETECTED · SWARMOS EVALUATING";
    case "ADAPTING":
      return "EXECUTOR LOST · SWARMOS SELECTING REPLACEMENT";
    case "VERIFIED":
      return "OBJECTIVE VERIFIED · MISSION COMPLETE";
    case "FAILED":
      return "OBJECTIVE CLOSED · NOT VERIFIED";
    case "EXECUTING":
    default: {
      const held = `${pad(rolesHeld(objective))} / ${pad(objective.requestedMembers)}`;

      // An objective SwarmOS is adding a swarm to. The reinforcement is still
      // composing, so the line says what SwarmOS decided, not what has arrived.
      const reinforcement = reinforcementOf(objective);
      if (reinforcement && reinforcement.state === "COMPOSING") {
        return "REINFORCEMENT DISPATCHED · SWARMOS ADDING EXECUTIONGROUP";
      }
      // Both swarms are running the objective. The count is the objective's,
      // across every swarm, because that is now the strength on the target.
      if (objective.swarms.length > 1) {
        return `${pad(objective.swarms.length)} EXECUTIONGROUPS COMBINED · ${held} ROLES ACTIVE`;
      }
      // Composed, running, and short of the strength it asked for. Stated
      // rather than left to a count nobody is looking at.
      if (underStrength(objective)) {
        return `EXECUTIONGROUP UNDER STRENGTH · ${held} ROLES HELD`;
      }

      // A single-executor objective has no ExecutionGroup, and the panel says so
      // in as many words. Claiming one here would be the surface inventing a
      // composition SwarmOS never made.
      return objective.groupId
        ? `EXECUTIONGROUP EXECUTING · ${held} ROLES ACTIVE`
        : `SINGLE EXECUTOR ON OBJECTIVE · ${held} ASSIGNED`;
    }
  }
}

/** Amber only where the state is genuinely degraded; never red, ever. */
function toneFor(objective: ObjectiveAuthority | null, beat: AdaptationBeat): string {
  if (beat.phase === "adapting" || objective?.state === "ADAPTING" || objective?.state === "FAILED") {
    return "#FFB45C";
  }
  if (beat.phase === "restored" || objective?.state === "VERIFIED") return "#B8FF66";
  // Under strength, and SwarmOS composing the swarm that answers it, are the
  // same condition read a moment apart. Both are amber; neither is a fault.
  if (objective && objective.state === "EXECUTING") {
    const reinforcement = reinforcementOf(objective);
    if (reinforcement?.state === "COMPOSING") return "#FFB45C";
    if (objective.swarms.length === 1 && underStrength(objective)) return "#FFB45C";
  }
  return "#A8AFB8";
}

export function NarrationStrip({
  focused,
  beat,
}: {
  focused: ObjectiveAuthority | null;
  beat: AdaptationBeat;
}) {
  const text = narrationFor(focused, beat);
  return (
    <div
      data-testid="narration-strip"
      /* Keyed on the text so each real transition re-runs the swap. The line
         changes only when the state behind it changed, so this never becomes a
         ticker. */
      key={text}
      className="value-swap flex items-center px-[13px]"
      style={{
        height: NARRATION_HEIGHT,
        background: "rgba(8, 11, 14, 0.86)",
        border: `1px solid ${HAIRLINE}`,
        borderRadius: 4,
        backdropFilter: "blur(14px) saturate(0.85)",
        WebkitBackdropFilter: "blur(14px) saturate(0.85)",
      }}
    >
      <span
        className="font-mono text-[11px] uppercase leading-none tracking-[0.19em]"
        style={{ color: toneFor(focused, beat) }}
      >
        {text}
      </span>
    </div>
  );
}
