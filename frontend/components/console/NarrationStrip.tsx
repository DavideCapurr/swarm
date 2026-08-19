"use client";

/**
 * NarrationStrip — one line saying what just happened.
 *
 * This line is addressed to a first-time viewer. The operator panels can carry
 * implementation detail; this cannot. The product-level noun is SWARM, while a
 * physical aircraft is a SUBUNIT. ExecutionGroup remains an internal/server
 * type and is intentionally absent from the demo narration.
 */

import type { DispositionDecision } from "@/lib/api";
import type { CompositionSlot, ObjectiveAuthority, SwarmComposition } from "@/lib/authority";

import { HAIRLINE } from "./Surface";
import type { AdaptationBeat } from "./useAdaptation";

export const NARRATION_HEIGHT = 30;

const pad = (value: number) => String(value).padStart(2, "0");

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

function reinforcementOf(objective: ObjectiveAuthority): SwarmComposition | null {
  return objective.swarms.find((swarm) => swarm.reinforcesGroupId != null) ?? null;
}

function reinforcementOnStation(swarm: SwarmComposition | null): boolean {
  if (!swarm) return false;
  return swarm.slots.some(
    (slot) => liveSlot(slot) && (slot.phase === "ON_STATION" || slot.phase === "DONE")
  );
}

function primaryUnderStrength(objective: ObjectiveAuthority): boolean {
  const primary = objective.swarms[0];
  return Boolean(primary && primary.composedMembers < primary.requestedMembers);
}

function dispositionLine(decision: DispositionDecision): string {
  const revision = String(decision.revision).padStart(2, "0");
  const radius = Math.round(decision.radius_m);
  return `DISPOSITION R${revision} ISSUED · R ${radius} M`;
}

export function narrationFor(
  objective: ObjectiveAuthority | null,
  beat: AdaptationBeat,
  disposition: DispositionDecision | null = null
): string {
  if (!objective) return "AWAITING FLEET STATE";

  if (beat.phase === "adapting") {
    return "SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT";
  }
  if (beat.phase === "restored") {
    return "SUBUNIT REPLACED · SWARM RESTORED";
  }

  switch (objective.state) {
    case "COMPOSING":
      return "OBJECTIVE DETECTED · SWARMOS COMPOSING SWARM";
    case "ADAPTING":
      return "SUBUNIT LOST · SWARMOS SELECTING REPLACEMENT";
    case "VERIFIED":
      return "OBJECTIVE VERIFIED · MISSION COMPLETE";
    case "FAILED":
      return "OBJECTIVE CLOSED · NOT VERIFIED";
    case "EXECUTING":
    default: {
      const required = requiredRoles(objective);
      const covered = rolesCovered(objective);
      const coverage = `${pad(covered)} / ${pad(required)}`;
      const reinforcement = reinforcementOf(objective);

      if (reinforcement?.state === "COMPOSING") {
        return "REINFORCEMENT REQUIRED · SWARM 02 DISPATCHED";
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

      return objective.groupId
        ? `SWARM 01 EXECUTING · ${coverage} ROLES COVERED`
        : `SINGLE SUBUNIT ON OBJECTIVE · ${coverage} ASSIGNED`;
    }
  }
}

function toneFor(objective: ObjectiveAuthority | null, beat: AdaptationBeat): string {
  if (
    beat.phase === "adapting" ||
    objective?.state === "ADAPTING" ||
    objective?.state === "FAILED"
  ) {
    return "#FFB45C";
  }
  if (beat.phase === "restored" || objective?.state === "VERIFIED") return "#B8FF66";
  if (objective?.state === "EXECUTING") {
    const reinforcement = reinforcementOf(objective);
    if (reinforcement?.state === "COMPOSING") return "#FFB45C";
    if (reinforcement && !reinforcementOnStation(reinforcement)) return "#FFB45C";
    if (objective.swarms.length === 1 && primaryUnderStrength(objective)) return "#FFB45C";
    if (objective.swarms.length > 1 && reinforcementOnStation(reinforcement)) return "#7BE7FF";
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
