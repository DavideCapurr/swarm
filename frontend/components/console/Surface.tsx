"use client";

/**
 * Surface — the floating plane every operating panel is built on.
 *
 * v2 of the design system makes depth load-bearing: elevation ranks what
 * matters now above what does not. Over a satellite ground that means three
 * things and no more —
 *
 *   · a near-opaque black body, because operational type at 10–13px has to
 *     clear its contrast ramp over imagery that changes as the fleet moves;
 *   · a single hairline in low-opacity white rather than the flat gunmetal
 *     border, which disappears against dark vegetation;
 *   · one soft shadow, wide and low, so the panel separates from the world
 *     without announcing itself.
 *
 * The 6% backdrop that survives at the body's alpha is the whole translucency
 * budget. It is enough to feel the world behind the panel at its edges and not
 * enough to cost a readout any contrast — the rule is legibility outranks
 * depth, so the blur loses every argument it has with small type.
 */

import type { CSSProperties, ReactNode } from "react";

export const SURFACE_STYLE: CSSProperties = {
  background: "rgba(8, 11, 14, 0.93)",
  backdropFilter: "blur(16px) saturate(0.85)",
  WebkitBackdropFilter: "blur(16px) saturate(0.85)",
  border: "1px solid rgba(238, 240, 243, 0.075)",
  borderRadius: 6,
  boxShadow:
    "0 20px 52px -14px rgba(0, 0, 0, 0.78), 0 2px 10px -2px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(238, 240, 243, 0.045)",
};

/** One step up the ramp — panel headers, selected rows, the command strip. */
export const RAISED_STYLE: CSSProperties = {
  background: "rgba(19, 25, 32, 0.72)",
};

export const HAIRLINE = "rgba(238, 240, 243, 0.075)";

export function Surface({
  children,
  className = "",
  style,
  ...rest
}: {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`surface-in overflow-hidden ${className}`}
      style={{ ...SURFACE_STYLE, ...style }}
      {...rest}
    >
      {children}
    </div>
  );
}

/** Panel header. One line, uppercase, the smallest type on the surface. */
export function SurfaceHeader({
  title,
  sub,
  right,
}: {
  title: string;
  sub?: string;
  right?: ReactNode;
}) {
  return (
    <header
      className="flex h-[34px] shrink-0 items-center justify-between gap-3 px-3"
      style={{ ...RAISED_STYLE, borderBottom: `1px solid ${HAIRLINE}` }}
    >
      <div className="flex min-w-0 items-baseline gap-2">
        <span className="font-grotesk text-[10px] font-medium uppercase leading-none tracking-[0.22em] text-muted-silver">
          {title}
        </span>
        {sub ? (
          <span className="truncate font-mono text-[9px] uppercase leading-none tracking-[0.18em] text-ash">
            {sub}
          </span>
        ) : null}
      </div>
      {right}
    </header>
  );
}

/** The 10px uppercase label tier. */
export function Label({
  children,
  tone = "ash",
  className = "",
}: {
  children: ReactNode;
  tone?: "ash" | "silver" | "orbital" | "amber" | "green";
  className?: string;
}) {
  const tones = {
    ash: "text-ash",
    silver: "text-muted-silver",
    orbital: "text-orbital-blue",
    amber: "text-launch-amber",
    green: "text-signal-green",
  } as const;
  return (
    <span
      className={`font-grotesk text-[10px] font-medium uppercase leading-none tracking-[0.2em] ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}

/** Monospace operational value. IDs, counts, timers, states. */
export function Mono({
  children,
  size = 13,
  tone = "platinum",
  className = "",
}: {
  children: ReactNode;
  size?: number;
  tone?: "platinum" | "silver" | "ash" | "orbital" | "amber" | "green";
  className?: string;
}) {
  const tones = {
    platinum: "text-platinum",
    silver: "text-muted-silver",
    ash: "text-ash",
    orbital: "text-orbital-blue",
    amber: "text-launch-amber",
    green: "text-signal-green",
  } as const;
  return (
    <span
      className={`font-mono tabular-nums leading-none tracking-[0.07em] ${tones[tone]} ${className}`}
      style={{ fontSize: size }}
    >
      {children}
    </span>
  );
}

export function Divider({ className = "" }: { className?: string }) {
  return (
    <div
      className={`h-px w-full ${className}`}
      style={{ background: HAIRLINE }}
      aria-hidden="true"
    />
  );
}

/** State dot. Green nominal, amber transition or degraded, blue live channel. */
export function Dot({
  tone,
  className = "",
}: {
  tone: "green" | "amber" | "orbital" | "silver" | "ash";
  className?: string;
}) {
  const bg = {
    green: "bg-signal-green",
    amber: "bg-launch-amber",
    orbital: "bg-orbital-blue",
    silver: "bg-muted-silver",
    ash: "bg-ash",
  }[tone];
  return (
    <span
      aria-hidden="true"
      className={`block h-[5px] w-[5px] rounded-full ${bg} ${className}`}
    />
  );
}
