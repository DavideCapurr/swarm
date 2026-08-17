"use client";

/**
 * CommandBar — the standing header of the operational surface.
 *
 * It carries only facts that are true of the whole session: what SwarmOS is
 * doing at mission level, who is connected, how many agents SwarmOS holds, how
 * many objectives are open, and where the claim boundary of this surface sits.
 *
 * The literal word CONNECTED is the recording runbook's start signal
 * (`docs/bench/final-demo-rehearsal.md` §5) — it must stay exact.
 */

import type { LinkState } from "@/lib/state";

import { Eyebrow } from "./primitives";

export function CommandBar({
  link,
  sessionLabel,
  operatorId,
  role,
  fleetTotal,
  fleetOwning,
  objectivesOpen,
  clockText,
  replay = false,
}: {
  link: LinkState;
  sessionLabel: string;
  operatorId: string;
  role: string | null;
  fleetTotal: number;
  fleetOwning: number;
  objectivesOpen: number;
  clockText: string;
  replay?: boolean;
}) {
  const linkText =
    link === "connected" ? "CONNECTED" : link === "connecting" ? "CONNECTING" : "LINK LOST";
  const linkTone =
    link === "connected" ? "text-signal-green" : "text-launch-amber";

  return (
    <header className="flex h-[64px] shrink-0 items-stretch whitespace-nowrap border border-gunmetal bg-obsidian shadow-inset-highlight">
      <div className="flex items-center gap-3 border-r border-gunmetal px-4">
        <span className="swarm-ring text-orbital-blue" />
        <span className="swarm-wordmark text-platinum" style={{ fontSize: 17 }}>
          SWARM
        </span>
        <span className="font-mono text-[13px] tracking-[0.18em] text-ash">SwarmOS</span>
      </div>

      <Cell label="mission layer" tone="orbital">
        DECIDES WHAT THE FLEET SHOULD DO
      </Cell>

      <Cell label="operation">PERIMETER RESPONSE · {sessionLabel}</Cell>

      <div className="flex items-center gap-2 border-r border-gunmetal px-4">
        <span
          className={`block h-[7px] w-[7px] ${
            link === "connected" ? "bg-signal-green" : "bg-launch-amber"
          }`}
          aria-hidden="true"
        />
        <div className="flex flex-col gap-[3px]">
          <Eyebrow>link</Eyebrow>
          <span
            data-testid="link-state"
            className={`font-mono text-[15px] tracking-[0.16em] ${linkTone}`}
          >
            {linkText}
          </span>
        </div>
      </div>

      <Cell label="fleet">
        {String(fleetTotal).padStart(3, "0")} AGENTS · {String(fleetOwning).padStart(2, "0")} OWNING
      </Cell>

      <Cell label="objectives">{String(objectivesOpen).padStart(2, "0")} OPEN</Cell>

      <Cell label="decision authority" tone="orbital">
        SWARMOS
      </Cell>

      <div className="flex flex-1 items-center justify-end gap-6 px-4">
        {replay ? (
          <span className="border border-launch-amber px-2 py-[3px] font-mono text-[13px] tracking-[0.18em] text-launch-amber">
            REPLAY · RECORDED FRAMES · NOT LIVE
          </span>
        ) : null}
        <div className="flex flex-col items-end gap-[3px]">
          <Eyebrow>runtime truth</Eyebrow>
          <span className="font-mono text-[13px] tracking-[0.12em] text-muted-silver">
            PX4 SITL TELEMETRY · IMAGERY SIMULATED
          </span>
        </div>
        <div className="flex flex-col items-end gap-[3px]">
          <Eyebrow>operator</Eyebrow>
          <span className="font-mono text-[13px] tracking-[0.12em] text-platinum">
            {role ?? "—"} · {operatorId || "—"}
          </span>
        </div>
        <div className="flex flex-col items-end gap-[3px]">
          <Eyebrow>utc</Eyebrow>
          <span className="font-mono text-[15px] tabular-nums text-platinum">{clockText}</span>
        </div>
      </div>
    </header>
  );
}

function Cell({
  label,
  children,
  tone = "platinum",
}: {
  label: string;
  children: React.ReactNode;
  tone?: "platinum" | "orbital";
}) {
  return (
    <div className="flex flex-col justify-center gap-[3px] border-r border-gunmetal px-4">
      <Eyebrow>{label}</Eyebrow>
      <span
        className={`font-mono text-[13px] tracking-[0.12em] ${
          tone === "orbital" ? "text-orbital-blue" : "text-platinum"
        }`}
      >
        {children}
      </span>
    </div>
  );
}
