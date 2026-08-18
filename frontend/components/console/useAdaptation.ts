"use client";

/**
 * useAdaptationBeat — makes SwarmOS recomposing a group perceivable.
 *
 * The moment a physical executor drops out and SwarmOS puts spare capacity into
 * the vacated role is the single most important thing this surface has to
 * communicate. It is also fast: on the validated PX4 run the runtime published
 * failure and replacement close together, and a state that is only ever true
 * for one frame is a state nobody watching the recording will see.
 *
 * So this hook holds the presentation, and only the presentation:
 *
 *   · it never enters a beat SwarmOS did not publish. `adapting` requires an
 *     observed member state of FAILED; `restored` requires an observed
 *     `replaces_agent_id`, which is the server's own provenance field;
 *   · it never suppresses a later truth — a beat can only delay leaving a state
 *     that was genuinely observed, by at most MIN_ADAPTING_MS;
 *   · it expires. The banner is an announcement, not a status; the settled row
 *     underneath keeps the replacement provenance permanently.
 */

import { useEffect, useRef, useState } from "react";

import type { ObjectiveAuthority } from "@/lib/authority";

/** Long enough to register, short enough that the mission does not appear stuck. */
const MIN_ADAPTING_MS = 700;
/** How long the completed swap is announced before the panel settles. */
const RESTORED_MS = 2_800;

export type AdaptationBeat =
  | { phase: "idle" }
  | { phase: "adapting"; role: string; lostAgent: string }
  | {
      phase: "restored";
      role: string;
      fromAgent: string;
      toAgent: string;
      active: number;
      required: number;
    };

/** Stable identity of the composition, so effects fire on real change only. */
function signatureOf(objective: ObjectiveAuthority | null): string {
  if (!objective) return "";
  return (
    objective.key +
    "|" +
    objective.slots
      .map(
        (slot) =>
          `${slot.role}:${slot.agentId ?? "-"}:${slot.memberState ?? "-"}:${
            slot.replacesAgentId ?? "-"
          }:${slot.adapting ? "1" : "0"}`
      )
      .join(",")
  );
}

export function useAdaptationBeat(objective: ObjectiveAuthority | null): AdaptationBeat {
  const [beat, setBeat] = useState<AdaptationBeat>({ phase: "idle" });
  /** Replacements whose announcement has already run to completion. */
  const announced = useRef<Set<string>>(new Set());
  /** The announcement currently on screen, if any. */
  const announcing = useRef<string | null>(null);
  const enteredAdaptingAt = useRef<number>(0);
  const signature = signatureOf(objective);

  useEffect(() => {
    if (!objective) {
      setBeat({ phase: "idle" });
      return;
    }

    const failing = objective.slots.find((slot) => slot.adapting && slot.agentId);
    if (failing?.agentId) {
      enteredAdaptingAt.current = Date.now();
      setBeat({ phase: "adapting", role: failing.role, lostAgent: failing.agentId });
      return;
    }

    const replaced = objective.slots.find(
      (slot) => slot.replacesAgentId && slot.agentId
    );
    const token = replaced
      ? `${objective.key}:${replaced.role}:${replaced.replacesAgentId}->${replaced.agentId}`
      : null;

    if (replaced && token && !announced.current.has(token)) {
      const active = objective.slots.filter(
        (slot) => slot.agentId && slot.memberState !== "FAILED"
      ).length;
      // Leaving `adapting` early would cut the beat the viewer is mid-way
      // through reading, so the announcement waits out the remainder.
      const elapsed = Date.now() - enteredAdaptingAt.current;
      const wait = enteredAdaptingAt.current > 0 ? Math.max(0, MIN_ADAPTING_MS - elapsed) : 0;
      announcing.current = token;
      const show = window.setTimeout(() => {
        setBeat({
          phase: "restored",
          role: replaced.role,
          fromAgent: replaced.replacesAgentId as string,
          toAgent: replaced.agentId as string,
          active,
          required: objective.requestedMembers,
        });
      }, wait);
      // The token is banked when the announcement has run, never when it is
      // scheduled. Banking it up front meant any re-run of this effect — Strict
      // Mode's second pass, or the next composition frame — cancelled the
      // timers while the replacement counted as already shown, and the beat
      // was silently lost.
      const clear = window.setTimeout(() => {
        announced.current.add(token);
        announcing.current = null;
        setBeat({ phase: "idle" });
      }, wait + RESTORED_MS);
      return () => {
        window.clearTimeout(show);
        window.clearTimeout(clear);
        if (announcing.current === token) announcing.current = null;
      };
    }

    setBeat({ phase: "idle" });
    // `signature` is the real dependency; `objective` is read through it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature]);

  return beat;
}
