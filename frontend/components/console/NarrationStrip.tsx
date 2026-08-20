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

import type { DispositionDecision } from "@/lib/api";
import type { CompositionSlot, ObjectiveAuthority, SwarmComposition } from "@/lib/authority";

import { HAIRLINE } from "./Surface";
import type { AdaptationBeat } from "./useAdaptation";

/** Height the strip claims, so the camera's clear area can account for it. */
export const NARRATION_HEIGHT = 30;

function liveSlot(slot: CompositionSlot): boolean {
  return Boolean(
    slot.agentId &&
      slot.memberState !== "FAILED" &&
      slot.memberState !== "REPLACED" &&
      slot.phase !== "FAILED"
  );
}

/** The originating swarm defines what the objective originally required. */
function requiredRoles(objective: ObjectiveAuthority): number {
  return objective.swarms[0]?.requestedMembers ?? objective.requestedMembers;
}

/**
 * Objective coverage is role coverage, not the sum of each reinforcing swarm's
 * requested_members. A reinforcement can bring extra capacity without changing
 * the original objective from 3 required roles into a fictitious 5-role task.
 */
function rolesCovered(objective: ObjectiveAuthority): number {
  const required = requiredRoles(objective);
  const roles = new Set(objective.slots.filter(liveSlot).map((slot) => slot.role));
  return Math.min(required, roles.size);
}

const pad = (value: number) => String(value).padStart(2, "0");

/** The swarm SwarmOS dispatched to reinforce another, when it has dispatched one. */
function reinforcementOf(objective: ObjectiveAuthority): SwarmComposition | null {
  return objective.swarms.find((swarm) => swarm.reinforcesGroupId != null) ?? null;
}

function reinforcementOnStation(swarm: SwarmComposition | null): boolean {
  if (!swarm) return false;
  return swarm.slots.some(
    (slot) => liveSlot(slot) && (slot.phase === "ON_STATION" || slot.phase === "DONE")
  );
}

/** True while the objective's originating swarm never reached the strength it was asked for. */
function primaryUnderStrength(objective: ObjectiveAuthority): boolean {
  const primary = objective.swarms[0];
  return Boolean(primary && primary.composedMembers < primary.requestedMembers);
}

/** A SwarmOS-issued disposition revision, rendered as the geometry it just committed to. */
function dispositionLine(decision: DispositionDecision): string {
  const revision = String(decision.revision).padStart(2, "0");
  const radius = Math.round(decision.radius_m);
  return `DISPOSITION R${revision} ISSUED · R ${radius} M`;
}

/**
 * Roles SwarmOS is still moving onto the objective from somewhere else.
 *
 * `divertedFromMissionId` is provenance, not a station: a slot keeps it for
 * the life of the role, so this only counts one still `EN_ROUTE` — once it
 * reports `ON_STATION` the diversion is done and the line has nothing current
 * left to say.
 */
function divertingCount(objective: ObjectiveAuthority): number {
  return objective.slots.filter((slot) => slot.divertedFromMissionId && slot.phase === "EN_ROUTE")
    .length;
}

/**
 * The unit SwarmOS turned down for this objective because another objective
 * already had it, if any.
 *
 * This is the moment two objectives are provably concurrent rather than
 * queued: the nearest executor was unavailable and SwarmOS held its ground on
 * the objective already running while still answering the new one. Read off
 * this objective's own award (`excludedUnits`), not the capacity-wide "newest
 * allocation" a roster row uses, so a later, unrelated exclusion elsewhere
 * cannot make an older objective claim a reallocation that was never its own.
 */
function busyExclusionOf(objective: ObjectiveAuthority) {
  return objective.excludedUnits.find((unit) => unit.reason === "BUSY") ?? null;
}

/**
 * The whole vocabulary, in priority order.
 *
 * The beat outranks the objective's settled state during EXECUTING, but
 * terminal objective truth (VERIFIED/FAILED) is authoritative and must not be
 * hidden by a presentation beat that began a few frames earlier.
 */
export function narrationFor(
  objective: ObjectiveAuthority | null,
  beat: AdaptationBeat,
  disposition: DispositionDecision | null = null
): string {
  if (!objective) return "AWAITING FLEET STATE";

  if (objective.state === "VERIFIED") {
    return "OBJECTIVE VERIFIED · MISSION COMPLETE";
  }
  if (objective.state === "FAILED") {
    return "OBJECTIVE CLOSED · NOT VERIFIED";
  }

  if (beat.phase === "adapting") {
    return "SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT";
  }
  if (beat.phase === "restored") {
    return "SUBUNIT REPLACED · SWARM RESTORED";
  }

  switch (objective.state) {
    case "COMPOSING":
      return "OBJECTIVE DETECTED · SWARMOS EVALUATING";
    case "ADAPTING":
      return "SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT";
    case "EXECUTING":
    default: {
      const required = requiredRoles(objective);
      const covered = rolesCovered(objective);
      const coverage = `${pad(covered)} / ${pad(required)}`;
      const reinforcement = reinforcementOf(objective);

      // An objective SwarmOS is adding a swarm to. The reinforcement is still
      // composing, so the line says what SwarmOS decided, not what has arrived.
      if (reinforcement?.state === "COMPOSING") {
        return "REINFORCEMENT DISPATCHED · SWARMOS ADDING SWARM";
      }

      // Subunits SwarmOS pulled off another objective are still inbound. Below
      // the reinforcement line — dispatching a whole second swarm outranks one
      // subunit still in transit — and above the steady-state lines, because
      // this is the thing currently changing.
      const diverting = divertingCount(objective);
      if (diverting > 0) {
        return `SWARMOS DIVERTING SWEEP CAPACITY · ${pad(diverting)} SUBUNITS REASSIGNED`;
      }

      if (reinforcement && !reinforcementOnStation(reinforcement)) {
        // A formation/disposition claim requires a SwarmOS disposition frame.
        // Group state alone is enough to say the reinforcing swarm is inbound,
        // but absence of disposition truth must never be interpreted as a
        // physical reconfiguration.
        if (disposition?.reason === "REINFORCEMENT") {
          return `SWARM 02 EN ROUTE · ${dispositionLine(disposition)}`;
        }
        return "SWARM 02 EN ROUTE";
      }

      if (objective.swarms.length > 1 && reinforcementOnStation(reinforcement)) {
        return `${pad(objective.swarms.length)} SWARMS COORDINATED · ${coverage} ROLES COVERED`;
      }

      if (objective.swarms.length === 1 && primaryUnderStrength(objective)) {
        return `SWARM 01 UNDER STRENGTH · ${coverage} ROLES COVERED`;
      }

      // The nearest subunit was already committed elsewhere, and SwarmOS
      // dispatched a second one rather than pulling the first off what it was
      // doing. Outranks the generic steady-state lines below because this is
      // the fact that makes the objective concurrent, not just active.
      if (busyExclusionOf(objective)) {
        return "PRIOR SUBUNIT BUSY · SWARMOS SELECTED ANOTHER";
      }

      // A single-subunit objective has no ExecutionGroup, and the panel says so
      // in as many words. Claiming one here would be the surface inventing a
      // composition SwarmOS never made.
      return objective.groupId
        ? `SWARM 01 EXECUTING · ${coverage} ROLES COVERED`
        : `SINGLE SUBUNIT ON OBJECTIVE · ${coverage} ASSIGNED`;
    }
  }
}

/** Amber only where the state is genuinely degraded; never red, ever. */
function toneFor(objective: ObjectiveAuthority | null, beat: AdaptationBeat): string {
  if (objective?.state === "VERIFIED") return "#B8FF66";
  if (objective?.state === "FAILED") return "#FFB45C";
  if (beat.phase === "adapting" || objective?.state === "ADAPTING") {
    return "#FFB45C";
  }
  if (beat.phase === "restored") return "#B8FF66";
  // Under strength, and SwarmOS composing the swarm that answers it, are the
  // same condition read a moment apart. Both are amber; neither is a fault.
  if (objective?.state === "EXECUTING") {
    const reinforcement = reinforcementOf(objective);
    if (reinforcement?.state === "COMPOSING") return "#FFB45C";
    if (reinforcement && !reinforcementOnStation(reinforcement)) return "#FFB45C";
    if (objective.swarms.length === 1 && primaryUnderStrength(objective)) return "#FFB45C";
    // Not a degraded reading — SwarmOS answered a second objective while
    // holding the first. Orbital blue is the product's own "SwarmOS decided,
    // live" accent (see `OwnershipStamp`), which is exactly what this is.
    if (busyExclusionOf(objective)) return "#7BE7FF";
  }
  return "#A8AFB8";
}

export function NarrationStrip({
  focused,
  beat,
  disposition = null,
}: {
  focused: ObjectiveAuthority | null;
  beat: AdaptationBeat;
  disposition?: DispositionDecision | null;
}) {
  const text = narrationFor(focused, beat, disposition);
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
        className="font-console-mono text-[11px] uppercase leading-none tracking-[0.06em]"
        style={{ color: toneFor(focused, beat) }}
      >
        {text}
      </span>
    </div>
  );
}
