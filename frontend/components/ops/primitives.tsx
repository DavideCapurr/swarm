/**
 * Operational primitives.
 *
 * Built on the SWARM design-system foundations (`lib/tokens.ts`): absolute
 * black ground, gunmetal hairlines, 85% monochrome with orbital blue / signal
 * green / launch amber reserved for state. No red, no shadow beyond the 1 px
 * inset highlight, no radius, no gradient, no glow.
 *
 * These are operational elements, not the editorial card/pill set used by the
 * legacy dashboard: every one of them encodes state, relation, decision or
 * evidence.
 */

import type { ReactNode } from "react";

import type { EvidenceTier } from "@/lib/mission-story";

// ── Tier colour ───────────────────────────────────────────────────────────────

export const TIER_TEXT: Record<EvidenceTier, string> = {
  verified: "text-signal-green",
  reported: "text-muted-silver",
  simulated: "text-launch-amber",
};

// ── Panel ─────────────────────────────────────────────────────────────────────

export function Panel({
  title,
  right,
  children,
  className = "",
  bodyClassName = "",
  ...rest
}: {
  title: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
} & Omit<React.HTMLAttributes<HTMLElement>, "title">) {
  return (
    <section
      className={`flex min-h-0 flex-col border border-gunmetal bg-absolute-black ${className}`}
      {...rest}
    >
      {/* 32px, not 38: the header holds one 13px eyebrow, and the six pixels it
          was spending on air are six pixels of body every scrollable panel
          needed. In the decision rail they are the difference between the
          causal chain closing on screen at step 04 and closing below the fold. */}
      <header className="flex h-[32px] shrink-0 items-center justify-between border-b border-gunmetal bg-obsidian px-3">
        <Eyebrow>{title}</Eyebrow>
        {right}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

export function Eyebrow({
  children,
  tone = "ash",
}: {
  children: ReactNode;
  tone?: "ash" | "platinum" | "orbital" | "amber" | "green";
}) {
  const color =
    tone === "platinum"
      ? "text-platinum"
      : tone === "orbital"
        ? "text-orbital-blue"
        : tone === "amber"
          ? "text-launch-amber"
          : tone === "green"
            ? "text-signal-green"
            : "text-ash";
  return (
    <span
      className={`font-grotesk text-[13px] font-medium uppercase leading-none tracking-[0.22em] ${color}`}
    >
      {children}
    </span>
  );
}

/** Numbered step marker for the decision rail's causal chain. */
export function StepNumber({ n }: { n: number }) {
  return (
    <span className="font-mono text-[14px] leading-none tracking-[0.1em] text-ash">
      {String(n).padStart(2, "0")}
    </span>
  );
}

// ── Value + label ─────────────────────────────────────────────────────────────

export function Value({
  children,
  size = "md",
  tone = "platinum",
  className = "",
}: {
  children: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
  tone?: "platinum" | "ash" | "silver" | "orbital" | "green" | "amber";
  className?: string;
}) {
  const sizes = {
    sm: "text-[15px]",
    md: "text-[18px]",
    lg: "text-[26px]",
    xl: "text-[44px]",
  } as const;
  const tones = {
    platinum: "text-platinum",
    ash: "text-ash",
    silver: "text-muted-silver",
    orbital: "text-orbital-blue",
    green: "text-signal-green",
    amber: "text-launch-amber",
  } as const;
  return (
    <span
      className={`font-mono tabular-nums leading-tight ${sizes[size]} ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

// ── Stamps ────────────────────────────────────────────────────────────────────

/**
 * Evidence stamp — the single visual device that separates what PX4 actually
 * confirmed from what is only simulated. Verified carries the claim boundary
 * (`PX4 SITL`) on its face so the screen never over-claims.
 */
export function EvidenceStamp({
  tier,
  children,
  bound,
}: {
  tier: EvidenceTier;
  children: ReactNode;
  bound?: string;
}) {
  const border =
    tier === "verified"
      ? "border-signal-green/60"
      : tier === "simulated"
        ? "border-launch-amber/60"
        : "border-gunmetal";
  return (
    <span
      className={`inline-flex items-center gap-2 border ${border} px-2 py-[4px] font-mono text-[14px] uppercase leading-none tracking-[0.12em] ${TIER_TEXT[tier]}`}
    >
      {tier === "verified" ? <VerifiedGlyph /> : null}
      {tier === "simulated" ? <SimulatedGlyph /> : null}
      <span>{children}</span>
      {bound ? <span className="text-ash">· {bound}</span> : null}
    </span>
  );
}

/** Named inline SVG, 1.5 px stroke, round caps — no external icon kit. */
function VerifiedGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 12.5 9.5 18 20 6"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function SimulatedGlyph() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M3 21 21 3M9 21 21 9M3 15 15 3"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ── Ladder ────────────────────────────────────────────────────────────────────

export function LadderTick({
  source,
  tone = "orbital",
}: {
  source: "observed" | "implied" | "pending";
  tone?: "orbital" | "green";
}) {
  if (source === "observed") {
    return (
      <span
        aria-hidden="true"
        className={`block h-[11px] w-[11px] ${tone === "green" ? "bg-signal-green" : "bg-orbital-blue"}`}
      />
    );
  }
  if (source === "implied") {
    return (
      <span
        aria-hidden="true"
        className="block h-[11px] w-[11px] border border-orbital-blue/50"
      />
    );
  }
  return <span aria-hidden="true" className="block h-[11px] w-[11px] border border-graphite" />;
}

// ── Battery ───────────────────────────────────────────────────────────────────

/** Five-segment charge readout. Amber below the verify threshold, never red. */
export function BatteryBar({ pct }: { pct: number }) {
  const filled = Math.round(Math.max(0, Math.min(100, pct)) / 20);
  const low = pct < 40;
  return (
    <span className="inline-flex items-center gap-[2px]" aria-hidden="true">
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className={`block h-[12px] w-[5px] border ${
            i < filled
              ? low
                ? "border-launch-amber bg-launch-amber"
                : "border-muted-silver bg-muted-silver"
              : "border-graphite"
          }`}
        />
      ))}
    </span>
  );
}
