"use client";

/**
 * HeadBar — the canon Control spread head bar (PDF §5.2 / spread 24).
 *
 * Reads from `useSwarm()` only. No data hops on its own. Tracks the operating
 * mode pill, live link badge, online/total ring, pending count.
 */

import Link from "next/link";

import { useSwarm } from "@/lib/state";
import { StatusPill } from "./StatusPill";

const MODE_STATE: Record<
  "rest" | "patrol" | "verification" | "escalation" | "maintenance",
  "rest" | "connected" | "operational" | "attention"
> = {
  rest: "rest",
  patrol: "operational",
  verification: "attention",
  escalation: "attention",
  maintenance: "attention",
};

export function HeadBar() {
  const { session, units, anomalies, link, clock, mode } = useSwarm();
  const online = units.filter((u) => u.fsm_state !== "OFFLINE").length;
  const total = units.length;
  const pending = anomalies.filter((a) => a.state === "pending" || a.state === "verifying").length;

  const fleetState: "rest" | "connected" | "operational" | "attention" = units.some(
    (u) => u.fsm_state === "ERROR"
  )
    ? "attention"
    : units.some((u) =>
          (
            [
              "TAKEOFF",
              "EN_ROUTE",
              "ON_STATION",
              "RTL",
              "LANDING",
              "DOCKING",
            ] as const
          ).includes(u.fsm_state as never)
        )
      ? "operational"
      : online > 0
        ? "rest"
        : "rest";

  const sessionLabel = session?.label ?? "session 0001";

  return (
    <header className="flex items-center justify-between px-4 border-b border-gunmetal bg-absolute-black h-[44px]">
      <div className="flex items-center gap-6 text-muted-silver">
        <Link href="/" className="flex items-center gap-2 text-platinum focus:outline-none focus-visible:outline-1 focus-visible:outline-orbital-blue">
          <span className="swarm-ring" style={{ width: 8, height: 8 }} />
          <span className="swarm-wordmark text-platinum" style={{ fontSize: 13 }}>
            SWARM
          </span>
        </Link>
        <ConsoleNav />
        <span className="eyebrow-mono text-platinum">/ {sessionLabel}</span>
        <LinkBadge state={link} />
      </div>
      <div className="flex items-center gap-6">
        <span className="mono-num text-platinum text-ui">{clock.date}</span>
        <span className="mono-num text-platinum text-ui">{clock.time} UTC</span>
        <span className="flex items-center gap-2">
          <StatusPill state={MODE_STATE[mode.value]}>{`mode · ${mode.value}`}</StatusPill>
          {mode.derived && <span className="eyebrow-mono text-ash">derived</span>}
        </span>
        <StatusPill state={fleetState}>
          {`${String(online).padStart(3, "0")} / ${String(total).padStart(3, "0")} online`}
        </StatusPill>
        {pending > 0 && <StatusPill state="attention">{`${pending} pending`}</StatusPill>}
      </div>
    </header>
  );
}

function ConsoleNav() {
  return (
    <nav className="flex items-center gap-4 eyebrow-mono">
      <Link
        href="/"
        className="hover:text-platinum transition-colors duration-press ease-swarm"
      >
        / control
      </Link>
      <Link
        href="/verify"
        className="hover:text-platinum transition-colors duration-press ease-swarm"
      >
        / verify
      </Link>
      <Link
        href="/system"
        className="hover:text-platinum transition-colors duration-press ease-swarm"
      >
        / system
      </Link>
    </nav>
  );
}

function LinkBadge({ state }: { state: "connected" | "connecting" | "lost" }) {
  const cls =
    state === "connected"
      ? "dot dot-operational"
      : state === "connecting"
        ? "dot dot-connected"
        : "dot dot-attention";
  const text =
    state === "connected" ? "live" : state === "connecting" ? "linking" : "offline";
  return (
    <span className="flex items-center gap-2 eyebrow-mono">
      <span className={cls} />
      <span className="text-platinum">{text}</span>
    </span>
  );
}
