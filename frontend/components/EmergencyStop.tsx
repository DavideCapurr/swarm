"use client";

/**
 * EmergencyStop — fleet-wide return intent (Phase 6.G).
 *
 * Visible to all roles, but the button is disabled for anyone below
 * commander. Two-step confirmation lives entirely inside this component:
 * a click opens the modal, the operator types the exact phrase, and the
 * Confirm button stays disabled until the typed phrase matches.
 *
 * Voice: "Return all units" — confidence-bound copy, no "alarm" /
 * "emergency" in operator-facing strings. The audit event body the
 * backend logs uses "emergency rtl all", but the UI surface stays
 * neutral. Colour is Launch Amber (design system §5.2 — never red).
 */

import { useCallback, useEffect, useState } from "react";

import { api, EMERGENCY_CONFIRMATION_PHRASE } from "@/lib/api";
import { canDo, useRole } from "@/lib/auth";
import { IconClose, IconEmergencyReturn } from "@/icons";

type Phase = "idle" | "confirm" | "sending" | "accepted" | "rejected";

export function EmergencyStop() {
  const role = useRole();
  const isCommander = canDo(role, "commander");
  const [phase, setPhase] = useState<Phase>("idle");
  const [typed, setTyped] = useState("");
  const [detail, setDetail] = useState<string | null>(null);

  // Auto-reset after a terminal outcome so the trigger button breathes.
  useEffect(() => {
    if (phase !== "accepted" && phase !== "rejected") return;
    const id = window.setTimeout(() => {
      setPhase("idle");
      setTyped("");
      setDetail(null);
    }, 4_000);
    return () => window.clearTimeout(id);
  }, [phase]);

  // Esc closes the modal — only while it's actually open.
  useEffect(() => {
    if (phase !== "confirm") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPhase("idle");
        setTyped("");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [phase]);

  const open = useCallback(() => {
    if (!isCommander) return;
    setTyped("");
    setDetail(null);
    setPhase("confirm");
  }, [isCommander]);

  const close = useCallback(() => {
    setPhase("idle");
    setTyped("");
  }, []);

  const phraseOk = typed.trim() === EMERGENCY_CONFIRMATION_PHRASE;

  const send = useCallback(async () => {
    if (!phraseOk) return;
    setPhase("sending");
    try {
      const { data, status } = await api.emergencyRtlAll(typed.trim());
      const ok = status >= 200 && status < 300;
      if (ok) {
        setPhase("accepted");
        setDetail(data.status ?? "accepted");
      } else {
        setPhase("rejected");
        setDetail(data.rejected_reason ?? `code ${status}`);
      }
    } catch (err) {
      setPhase("rejected");
      setDetail(err instanceof Error ? err.message : "network error");
    }
  }, [phraseOk, typed]);

  const buttonLabel = (() => {
    if (phase === "sending") return "dispatching";
    if (phase === "accepted") return "intent acknowledged";
    if (phase === "rejected") return detail ?? "rejected";
    return "Return all units";
  })();

  const buttonTone =
    phase === "accepted"
      ? "border-signal-green text-signal-green"
      : phase === "rejected"
        ? "border-launch-amber text-launch-amber"
        : phase === "sending"
          ? "border-orbital-blue text-orbital-blue"
          : isCommander
            ? "border-launch-amber text-launch-amber hover:bg-launch-amber/10"
            : "border-graphite text-ash";

  return (
    <>
      <button
        type="button"
        onClick={open}
        disabled={!isCommander || phase === "sending"}
        aria-haspopup="dialog"
        aria-expanded={phase === "confirm"}
        title={
          isCommander
            ? "return every airborne unit to its dock"
            : "commander role required"
        }
        className={`flex items-center gap-2 border ${buttonTone} rounded-input px-3 py-1.5 transition-all duration-press ease-swarm bg-absolute-black disabled:opacity-40 disabled:cursor-not-allowed`}
        data-testid="emergency-stop-trigger"
      >
        <IconEmergencyReturn size={18} />
        <span className="eyebrow-mono">{buttonLabel}</span>
      </button>
      {phase === "confirm" && (
        <ConfirmDialog
          typed={typed}
          phraseOk={phraseOk}
          onChange={setTyped}
          onConfirm={send}
          onCancel={close}
        />
      )}
    </>
  );
}

function ConfirmDialog({
  typed,
  phraseOk,
  onChange,
  onConfirm,
  onCancel,
}: {
  typed: string;
  phraseOk: boolean;
  onChange: (v: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="emergency-stop-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-absolute-black/80"
      onClick={onCancel}
      data-testid="emergency-stop-dialog"
    >
      <div
        className="border border-launch-amber bg-absolute-black rounded-card p-6 max-w-md w-[90vw] flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-baseline justify-between">
          <h2
            id="emergency-stop-title"
            className="font-display text-h3 text-platinum"
          >
            Return all units
          </h2>
          <button
            type="button"
            onClick={onCancel}
            aria-label="cancel"
            className="text-ash hover:text-platinum"
          >
            <IconClose size={18} />
          </button>
        </div>
        <p className="eyebrow-mono text-launch-amber">
          commander confirmation required
        </p>
        <p className="text-ui text-muted-silver">
          Every airborne unit will be dispatched to its dock immediately.
          Patrol scheduling will be held until the fleet is recovered. Safety
          policy gates (battery, link, weather) are bypassed for this intent —
          the audit trail records the bypass.
        </p>
        <label className="flex flex-col gap-2">
          <span className="eyebrow-mono text-ash">
            type{" "}
            <span className="text-platinum">
              {EMERGENCY_CONFIRMATION_PHRASE}
            </span>{" "}
            to confirm
          </span>
          <input
            type="text"
            autoFocus
            spellCheck={false}
            autoComplete="off"
            value={typed}
            onChange={(e) => onChange(e.target.value)}
            className="bg-absolute-black border border-graphite rounded-input px-3 py-2 text-platinum font-mono"
            data-testid="emergency-stop-input"
          />
        </label>
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="border border-graphite rounded-input px-3 py-1.5 eyebrow-mono text-muted-silver hover:text-platinum"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={!phraseOk}
            className="border border-launch-amber rounded-input px-3 py-1.5 eyebrow-mono text-launch-amber disabled:opacity-40 disabled:cursor-not-allowed hover:bg-launch-amber/10"
            data-testid="emergency-stop-confirm"
          >
            Confirm return
          </button>
        </div>
      </div>
    </div>
  );
}
