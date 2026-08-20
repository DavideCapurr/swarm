"use client";

/**
 * SystemStatus — the top edge, and nothing more than that.
 *
 * No page title, no greeting, no breadcrumb. What sits here is what stays true
 * for the whole session: who this is, whether the Console is connected, where
 * the telemetry actually comes from, how much physical capacity SwarmOS holds,
 * and the clock.
 *
 * Two constraints are not stylistic. The literal string CONNECTED is the
 * recording runbook's start signal (`docs/bench/final-demo-rehearsal.md` §5) and
 * must stay exact. And the runtime-truth claim is read off the units' own
 * vendor/model — this surface never upgrades SITL into flight.
 */

import type { LinkState } from "@/lib/state";

import { Dot, HAIRLINE, Label, Mono } from "./Surface";
import { RAIL_WIDTH } from "./NavigationRail";

export const STATUS_HEIGHT = 46;

export function SystemStatus({
  link,
  telemetrySource,
  executorsTotal,
  executorsCommitted,
  clockText,
  replay = false,
}: {
  link: LinkState;
  telemetrySource: string;
  executorsTotal: number;
  executorsCommitted: number;
  clockText: string;
  replay?: boolean;
}) {
  const linkText =
    link === "connected" ? "CONNECTED" : link === "connecting" ? "CONNECTING" : "LINK LOST";

  return (
    <header
      data-testid="system-status"
      className="absolute inset-x-0 top-0 z-40 flex items-center justify-between gap-6 pr-4"
      style={{
        height: STATUS_HEIGHT,
        paddingLeft: RAIL_WIDTH + 16,
        background:
          "linear-gradient(180deg, rgba(4,6,8,0.92) 0%, rgba(4,6,8,0.72) 62%, rgba(4,6,8,0) 100%)",
      }}
    >
      <div className="flex items-baseline gap-3">
        <span className="swarm-wordmark text-platinum" style={{ fontSize: 13 }}>
          SWARM
        </span>
        <span
          className="h-[10px] w-px self-center"
          style={{ background: HAIRLINE }}
          aria-hidden="true"
        />
        <Mono size={10} tone="ash" className="!tracking-[0.04em]">
          SwarmOS · mission authority
        </Mono>
      </div>

      <div className="flex items-center gap-5">
        {replay ? (
          <span className="border border-launch-amber/70 px-[7px] py-[3px] font-console-mono text-[9px] uppercase leading-none tracking-[0.06em] text-launch-amber">
            REPLAY · RECORDED FRAMES · NOT LIVE
          </span>
        ) : null}

        <Field label="runtime">
          <Mono size={11} tone="silver">
            {telemetrySource}
          </Mono>
        </Field>

        <Field label="capacity">
          <Mono size={11} tone="platinum">
            {String(executorsCommitted).padStart(2, "0")} / {String(executorsTotal).padStart(2, "0")}
          </Mono>
        </Field>

        <div className="flex items-center gap-[7px]">
          <Dot tone={link === "connected" ? "green" : "amber"} />
          <Mono size={11} tone={link === "connected" ? "green" : "amber"}>
            <span data-testid="link-state">{linkText}</span>
          </Mono>
        </div>

        <Mono size={12} tone="platinum">
          {clockText}
        </Mono>
      </div>
    </header>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <Label>{label}</Label>
      {children}
    </div>
  );
}
