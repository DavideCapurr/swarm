"use client";

import { useEffect, useMemo, useState } from "react";

import type { AgentState, UnitState } from "@/lib/api";
import { useSwarm } from "@/lib/state";

const DEMO_DURATION_MS = 22_000;

const STAGES = [
  { at: 0, label: "Watching" },
  { at: 1_700, label: "Person detected" },
  { at: 3_600, label: "Fleet allocated" },
  { at: 6_000, label: "Drone dispatched" },
  { at: 8_700, label: "Support notified" },
  { at: 11_800, label: "Visual verified" },
  { at: 14_400, label: "Presence response" },
  { at: 18_000, label: "Tracking" },
] as const;

type StageIndex = 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7;

type ActionStatus = "pending" | "queued" | "active" | "done";

type ResponseAction = {
  id: string;
  label: string;
  detail: string;
  status: ActionStatus;
  simulated?: boolean;
};

const FALLBACK_UNITS: UnitState[] = [
  {
    agent_id: "mav-002",
    vendor: "mavlink",
    model: "PX4 iris SITL",
    fsm_state: "EN_ROUTE",
    battery_pct: 78,
    geo: { lat: 47.398, lon: 8.546, alt_m: 40 },
    current_mission_id: "5915bd56",
    current_sector_id: "C7",
    link_quality: 0.97,
    heading_deg: 32,
    altitude_agl_m: 40,
    dock_id: null,
    ts: "2026-08-15T10:07:25.000Z",
  },
  {
    agent_id: "mav-001",
    vendor: "mavlink",
    model: "PX4 iris SITL",
    fsm_state: "DOCKED",
    battery_pct: 92,
    geo: { lat: 47.3977, lon: 8.5457, alt_m: 0 },
    current_mission_id: null,
    current_sector_id: "B3",
    link_quality: 0.99,
    heading_deg: 0,
    altitude_agl_m: 0,
    dock_id: null,
    ts: "2026-08-15T10:07:25.000Z",
  },
];

function stageForElapsed(elapsed: number): StageIndex {
  let index: StageIndex = 0;
  for (let i = 0; i < STAGES.length; i += 1) {
    if (elapsed >= STAGES[i].at) index = i as StageIndex;
  }
  return index;
}

function statusTone(status: ActionStatus): string {
  if (status === "done") return "text-signal-green";
  if (status === "active") return "text-orbital-blue";
  if (status === "queued") return "text-launch-amber";
  return "text-ash";
}

function stateTone(state: AgentState): string {
  if (state === "EN_ROUTE" || state === "ON_STATION") return "text-signal-green";
  if (state === "TAKEOFF" || state === "RTL") return "text-orbital-blue";
  if (state === "ERROR") return "text-launch-amber";
  return "text-muted-silver";
}

function compactState(state: AgentState): string {
  return state.replaceAll("_", " ");
}

function Icon({ name }: { name: "camera" | "drone" | "phone" | "light" | "speaker" | "track" }) {
  const common = "h-4 w-4";
  switch (name) {
    case "camera":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M4 7.5h4l1.4-2h5.2l1.4 2h4v10H4z" />
          <circle cx="12" cy="12.5" r="3.1" />
        </svg>
      );
    case "drone":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M8 12h8M12 8v8M6.5 9.5l-2-2M17.5 9.5l2-2M6.5 14.5l-2 2M17.5 14.5l2 2" />
          <circle cx="12" cy="12" r="2.5" />
          <circle cx="3.5" cy="6.5" r="1.5" />
          <circle cx="20.5" cy="6.5" r="1.5" />
          <circle cx="3.5" cy="17.5" r="1.5" />
          <circle cx="20.5" cy="17.5" r="1.5" />
        </svg>
      );
    case "phone":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M7.2 4.5 9.5 8 8 10c1.2 2.4 3 4.2 5.5 5.5l2-1.5 3.5 2.3-.8 3.2c-.2.7-.8 1.1-1.5 1-7-.8-12.4-6.2-13.2-13.2-.1-.7.3-1.3 1-1.5z" />
        </svg>
      );
    case "light":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="12" cy="10" r="4" />
          <path d="M9.5 15.5h5M10 18h4M12 2v2M4.9 4.9l1.4 1.4M19.1 4.9l-1.4 1.4M3 10h2M19 10h2" />
        </svg>
      );
    case "speaker":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <path d="M5 10h3l4-3v10l-4-3H5zM15.5 9.2c1.7 1.5 1.7 4.1 0 5.6M18 7c3 2.8 3 7.2 0 10" />
        </svg>
      );
    case "track":
      return (
        <svg className={common} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </svg>
      );
  }
}

function PanelHeader({
  eyebrow,
  title,
  meta,
}: {
  eyebrow: string;
  title: string;
  meta?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-14 items-center justify-between gap-4 border-b border-gunmetal px-4">
      <div className="min-w-0">
        <div className="eyebrow-mono">{eyebrow}</div>
        <div className="mt-1 truncate font-display text-ui text-platinum">{title}</div>
      </div>
      {meta}
    </div>
  );
}

function DemoStamp({ children = "SIMULATED STOCK FOOTAGE" }: { children?: React.ReactNode }) {
  return (
    <div className="absolute left-3 top-3 z-30 border border-platinum/25 bg-absolute-black/85 px-2 py-1 font-mono text-[9px] tracking-[0.18em] text-platinum">
      {children}
    </div>
  );
}

function Scanlines() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 z-10 opacity-20"
      style={{
        backgroundImage:
          "repeating-linear-gradient(to bottom, rgba(238,240,243,.08) 0px, rgba(238,240,243,.08) 1px, transparent 1px, transparent 4px)",
      }}
    />
  );
}

function CameraFeed({ active }: { active: boolean }) {
  return (
    <section className="card min-h-0 overflow-hidden">
      <PanelHeader
        eyebrow="Detection source"
        title="CAM-04 · North perimeter"
        meta={
          <div className="flex items-center gap-2 font-mono text-[10px] text-signal-green">
            <span className="dot dot-operational" /> LIVE DEMO
          </div>
        }
      />
      <div className="relative aspect-[16/10] overflow-hidden bg-black">
        <video
          className="h-full w-full object-cover grayscale contrast-125 brightness-[0.58]"
          src="/sim-feed/intrusion-pov.mp4"
          autoPlay
          muted
          loop
          playsInline
          aria-label="Simulated stock security camera footage"
        />
        <Scanlines />
        <DemoStamp />
        <div className="absolute right-3 top-3 z-30 text-right font-mono text-[10px] leading-4 text-platinum/75">
          <div>2026-08-15 23:47:18</div>
          <div>CAM-04 · 12 FPS</div>
        </div>
        <div className="absolute bottom-3 left-3 z-30 flex gap-3 font-mono text-[9px] tracking-[0.12em] text-muted-silver">
          <span>ZONE C7</span>
          <span>MOTION · ARMED</span>
        </div>

        <div
          className={`absolute z-20 border transition-all duration-500 ${
            active
              ? "left-[56%] top-[43%] h-[39%] w-[13%] border-launch-amber opacity-100"
              : "left-[56%] top-[43%] h-[39%] w-[13%] border-transparent opacity-0"
          }`}
        >
          <span className="absolute -top-6 left-0 whitespace-nowrap bg-launch-amber px-2 py-1 font-mono text-[9px] font-medium tracking-[0.12em] text-absolute-black">
            PERSON · 0.96
          </span>
          <span className="absolute -left-px -top-px h-2 w-2 border-l border-t border-platinum" />
          <span className="absolute -right-px -top-px h-2 w-2 border-r border-t border-platinum" />
          <span className="absolute -bottom-px -left-px h-2 w-2 border-b border-l border-platinum" />
          <span className="absolute -bottom-px -right-px h-2 w-2 border-b border-r border-platinum" />
        </div>
      </div>
    </section>
  );
}

function DroneFeed({ active, verified }: { active: boolean; verified: boolean }) {
  return (
    <section className="card min-h-0 overflow-hidden">
      <PanelHeader
        eyebrow="Mobile verifier"
        title="U-02 · PX4 SITL response"
        meta={
          <div className={`flex items-center gap-2 font-mono text-[10px] ${active ? "text-signal-green" : "text-ash"}`}>
            <span className={`dot ${active ? "dot-operational" : "dot-rest"}`} />
            {active ? "EN ROUTE" : "STANDBY"}
          </div>
        }
      />
      <div className="relative aspect-[16/10] overflow-hidden bg-black">
        <video
          className={`h-full w-full object-cover grayscale contrast-125 transition-opacity duration-700 ${active ? "opacity-100 brightness-[0.72]" : "opacity-20 brightness-[0.35]"}`}
          src="/sim-feed/drone-pov.mp4"
          autoPlay
          muted
          loop
          playsInline
          aria-label="Simulated stock drone response footage"
        />
        <DemoStamp>SIMULATED DRONE VIEW</DemoStamp>
        <div className="pointer-events-none absolute inset-x-7 top-6 z-20 flex justify-between font-mono text-[9px] tracking-[0.16em] text-signal-green/80">
          <span>W 300 330</span>
          <span>N</span>
          <span>030 060 E</span>
        </div>
        <div className="absolute left-3 top-12 z-30 font-mono text-[9px] leading-5 text-platinum/70">
          <div>ALT 040 M</div>
          <div>BAT 078%</div>
          <div>LINK 097%</div>
          <div>HDG 032°</div>
        </div>
        <div className="absolute right-3 top-12 z-30 text-right font-mono text-[9px] leading-5 text-platinum/70">
          <div>47.39800 N</div>
          <div>008.54600 E</div>
          <div className="text-orbital-blue">GPS · LOCK</div>
        </div>

        <div className={`absolute inset-0 z-20 transition-opacity duration-500 ${active ? "opacity-100" : "opacity-0"}`} aria-hidden="true">
          <div className="absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 border border-signal-green/50">
            <span className="absolute left-1/2 top-1/2 h-px w-8 -translate-x-1/2 bg-signal-green/70" />
            <span className="absolute left-1/2 top-1/2 h-8 w-px -translate-y-1/2 bg-signal-green/70" />
          </div>
          <div className="absolute inset-x-0 top-1/2 h-px bg-signal-green/10" />
          <div className="absolute inset-y-0 left-1/2 w-px bg-signal-green/10" />
        </div>

        <div className="absolute bottom-3 left-3 z-30 flex items-center gap-3">
          <span className="pill pill-operational">U-02</span>
          {active && <span className="font-mono text-[9px] tracking-[0.12em] text-muted-silver">MAVLINK · SITL</span>}
        </div>
        {verified && (
          <div className="absolute bottom-3 right-3 z-30 border border-signal-green bg-absolute-black/85 px-2 py-1 font-mono text-[9px] tracking-[0.15em] text-signal-green">
            VISUAL VERIFIED
          </div>
        )}
      </div>
    </section>
  );
}

function DecisionPanel({ stage, units }: { stage: StageIndex; units: UnitState[] }) {
  const actions: ResponseAction[] = [
    {
      id: "verify",
      label: "Verify from mobile camera",
      detail: "Dispatch the nearest available aerial unit to C7.",
      status: stage >= 5 ? "done" : stage >= 2 ? "active" : stage >= 1 ? "queued" : "pending",
    },
    {
      id: "support",
      label: "Notify site support",
      detail: "Open the on-site guard desk channel. No external call is placed in demo mode.",
      status: stage >= 5 ? "done" : stage >= 4 ? "active" : stage >= 2 ? "queued" : "pending",
      simulated: true,
    },
    {
      id: "presence",
      label: "Establish bounded presence",
      detail: "Hold standoff, illuminate the area and keep the subject in view.",
      status: stage >= 7 ? "done" : stage >= 6 ? "active" : stage >= 5 ? "queued" : "pending",
      simulated: true,
    },
    {
      id: "speaker",
      label: "Play site warning",
      detail: "Speaker: “Restricted area. Please return to the marked exit.”",
      status: stage >= 7 ? "done" : stage >= 6 ? "active" : stage >= 5 ? "queued" : "pending",
      simulated: true,
    },
  ];

  const winner = units.find((u) => u.agent_id === "mav-002") ?? units[0];
  const reserve = units.find((u) => u.agent_id !== winner?.agent_id) ?? units[1];

  return (
    <section className="card flex min-h-0 flex-col overflow-hidden">
      <PanelHeader
        eyebrow="SWARM decision"
        title="Verify · deter · notify"
        meta={<span className="pill pill-attention">INTRUSION</span>}
      />

      <div className="border-b border-gunmetal px-4 py-4">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <div className="eyebrow">Classification</div>
            <div className="mt-1 font-display text-h3 text-platinum">Person in restricted zone</div>
          </div>
          <div className="text-right">
            <div className="mono-num text-2xl text-launch-amber">96%</div>
            <div className="eyebrow-mono mt-1">camera confidence</div>
          </div>
        </div>
        <p className="mt-3 max-w-xl text-ui leading-5 text-muted-silver">
          Policy keeps force bounded: verify first, notify a human support channel, then use light and speaker presence only after visual confirmation.
        </p>
      </div>

      <div className="border-b border-gunmetal px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="eyebrow">Fleet allocation</span>
          <span className="font-mono text-[9px] tracking-[0.15em] text-orbital-blue">RECORDED SITL OUTCOME</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {winner && (
            <div className={`border px-3 py-3 ${stage >= 2 ? "border-signal-green bg-signal-green/[0.035]" : "border-gunmetal"}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-ui text-platinum">{winner.agent_id}</span>
                <span className="font-mono text-[9px] tracking-[0.14em] text-signal-green">{stage >= 2 ? "SELECTED" : "AVAILABLE"}</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[10px] text-muted-silver">
                <span>{Math.round(winner.battery_pct)}% BAT</span>
                <span className="text-right">{Math.round(winner.link_quality * 100)}% LINK</span>
              </div>
            </div>
          )}
          {reserve && (
            <div className="border border-gunmetal px-3 py-3">
              <div className="flex items-center justify-between gap-3">
                <span className="font-mono text-ui text-platinum">{reserve.agent_id}</span>
                <span className={`font-mono text-[9px] tracking-[0.14em] ${stateTone(reserve.fsm_state)}`}>
                  {compactState(reserve.fsm_state)}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 font-mono text-[10px] text-muted-silver">
                <span>{Math.round(reserve.battery_pct)}% BAT</span>
                <span className="text-right">RESERVE</span>
              </div>
            </div>
          )}
        </div>
        <div className="mt-3 border-l border-orbital-blue pl-3 text-ui leading-5 text-muted-silver">
          {stage >= 2
            ? "Allocator committed U-02 to the verification mission. The Console is replaying the validated two-PX4 SITL path; it does not fabricate an allocation score."
            : "Waiting for the detection gate before opening the fleet auction."}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <div className="mb-3 flex items-center justify-between">
          <span className="eyebrow">Response plan</span>
          <span className="font-mono text-[9px] tracking-[0.14em] text-muted-silver">BOUNDED DEMO POLICY</span>
        </div>
        <div className="space-y-0">
          {actions.map((action, index) => (
            <div key={action.id} className="grid grid-cols-[24px_1fr_auto] gap-3 border-t border-gunmetal py-3 first:border-t-0">
              <div className={`font-mono text-[10px] ${statusTone(action.status)}`}>{String(index + 1).padStart(2, "0")}</div>
              <div>
                <div className="text-ui text-platinum">{action.label}</div>
                <div className="mt-1 text-[12px] leading-5 text-muted-silver">{action.detail}</div>
              </div>
              <div className="text-right">
                <div className={`font-mono text-[9px] tracking-[0.14em] uppercase ${statusTone(action.status)}`}>{action.status}</div>
                {action.simulated && <div className="mt-1 font-mono text-[8px] tracking-[0.12em] text-ash">SIMULATED</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ActionStrip({ stage }: { stage: StageIndex }) {
  const actionItems = [
    { icon: "phone" as const, label: "Site support", state: stage >= 4 ? "CHANNEL OPEN" : "READY", tone: stage >= 4 ? "text-orbital-blue" : "text-muted-silver" },
    { icon: "light" as const, label: "Spotlight", state: stage >= 6 ? "ON · SIM" : "ARMED", tone: stage >= 6 ? "text-launch-amber" : "text-muted-silver" },
    { icon: "speaker" as const, label: "Speaker", state: stage >= 6 ? "PLAYING · SIM" : "READY", tone: stage >= 6 ? "text-launch-amber" : "text-muted-silver" },
    { icon: "track" as const, label: "Track", state: stage >= 7 ? "ACTIVE" : "PENDING", tone: stage >= 7 ? "text-signal-green" : "text-muted-silver" },
  ];

  return (
    <section className="card grid grid-cols-4 divide-x divide-gunmetal overflow-hidden">
      {actionItems.map((item) => (
        <div key={item.label} className="flex min-w-0 items-center gap-3 px-4 py-3">
          <div className={item.tone}><Icon name={item.icon} /></div>
          <div className="min-w-0">
            <div className="truncate text-ui text-platinum">{item.label}</div>
            <div className={`mt-1 truncate font-mono text-[9px] tracking-[0.13em] ${item.tone}`}>{item.state}</div>
          </div>
        </div>
      ))}
    </section>
  );
}

function Timeline({ stage }: { stage: StageIndex }) {
  const rows = [
    [1, "23:47:18", "CAM-04", "Person detected · confidence 0.96"],
    [2, "23:47:20", "SWARM", "Verification mission opened · U-02 selected"],
    [3, "23:47:22", "U-02", "PX4 mission accepted · en route"],
    [4, "23:47:25", "SUPPORT", "On-site guard desk channel opened · demo sink"],
    [5, "23:47:29", "U-02", "Visual confirmation received · restricted zone"],
    [6, "23:47:32", "PAYLOAD", "Standoff + spotlight + speaker response · simulated"],
    [7, "23:47:36", "SWARM", "Subject tracking maintained · human escalation available"],
  ] as const;

  return (
    <section className="card overflow-hidden">
      <PanelHeader eyebrow="Incident log" title="One chain of custody" meta={<span className="font-mono text-[9px] tracking-[0.14em] text-ash">DEMO CLOCK</span>} />
      <div className="grid grid-cols-[80px_90px_1fr] px-4 py-1 text-[9px] tracking-[0.14em] text-ash font-mono">
        <span>TIME</span><span>SOURCE</span><span>EVENT</span>
      </div>
      {rows.map(([required, time, source, body]) => {
        const visible = stage >= required;
        return (
          <div key={`${time}-${source}`} className={`grid grid-cols-[80px_90px_1fr] border-t border-gunmetal px-4 py-2.5 transition-opacity duration-300 ${visible ? "opacity-100" : "opacity-20"}`}>
            <span className="font-mono text-[10px] text-ash">{time}</span>
            <span className={`font-mono text-[9px] tracking-[0.12em] ${source === "SWARM" ? "text-orbital-blue" : source === "PAYLOAD" ? "text-launch-amber" : "text-muted-silver"}`}>{source}</span>
            <span className="text-[12px] text-platinum">{body}</span>
          </div>
        );
      })}
    </section>
  );
}

function FleetRail({ units, stage }: { units: UnitState[]; stage: StageIndex }) {
  return (
    <section className="card overflow-hidden">
      <PanelHeader eyebrow="Fleet" title="Two PX4 units · one allocator" meta={<span className="font-mono text-[9px] tracking-[0.14em] text-signal-green">SITL VALIDATED</span>} />
      <div className="divide-y divide-gunmetal">
        {units.slice(0, 2).map((unit, index) => {
          const demoState: AgentState = unit.agent_id === "mav-002" && stage >= 3 ? (stage >= 5 ? "ON_STATION" : "EN_ROUTE") : unit.fsm_state;
          return (
            <div key={unit.agent_id} className="grid grid-cols-[1fr_auto] gap-4 px-4 py-3">
              <div>
                <div className="flex items-center gap-2">
                  <Icon name="drone" />
                  <span className="font-mono text-ui text-platinum">{unit.agent_id}</span>
                  {index === 0 && stage >= 2 && <span className="pill pill-operational !px-1.5 !py-0.5 !text-[8px]">WINNER</span>}
                </div>
                <div className="mt-2 font-mono text-[9px] tracking-[0.11em] text-ash">{unit.model} · {Math.round(unit.battery_pct)}% BAT</div>
              </div>
              <div className="text-right">
                <div className={`font-mono text-[9px] tracking-[0.13em] ${stateTone(demoState)}`}>{compactState(demoState)}</div>
                <div className="mt-2 font-mono text-[9px] text-ash">LINK {Math.round(unit.link_quality * 100)}%</div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DemoHeader({ stage, elapsed, replay }: { stage: StageIndex; elapsed: number; replay: () => void }) {
  const progress = Math.min(100, (elapsed / DEMO_DURATION_MS) * 100);
  return (
    <header className="border-b border-gunmetal bg-obsidian px-4 py-3">
      <div className="flex items-center justify-between gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <span className="eyebrow text-launch-amber">Incident response demo</span>
            <span className="pill pill-attention">ACTIVE</span>
            <span className="pill">STOCK VIDEO · SITL REPLAY</span>
          </div>
          <div className="mt-2 flex items-baseline gap-4">
            <h1 className="font-editorial text-3xl font-medium text-platinum">North perimeter · intrusion</h1>
            <span className="font-mono text-[10px] tracking-[0.13em] text-muted-silver">IR-014 / C7</span>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-5">
          <div className="hidden text-right md:block">
            <div className="font-mono text-[9px] tracking-[0.13em] text-ash">CURRENT STEP</div>
            <div className="mt-1 font-mono text-[11px] text-orbital-blue">{STAGES[stage].label}</div>
          </div>
          <button
            type="button"
            onClick={replay}
            className="border border-gunmetal bg-absolute-black px-3 py-2 font-mono text-[10px] tracking-[0.14em] text-muted-silver transition-colors hover:border-orbital-blue hover:text-orbital-blue"
          >
            REPLAY
          </button>
        </div>
      </div>
      <div className="mt-3 h-px w-full bg-gunmetal">
        <div className="h-px bg-orbital-blue transition-[width] duration-300" style={{ width: `${progress}%` }} />
      </div>
    </header>
  );
}

export function IntrusionResponseDemo() {
  const { units: liveUnits, link } = useSwarm();
  const units = useMemo(() => {
    const mav = liveUnits.filter((u) => u.vendor === "mavlink");
    return mav.length >= 2 ? mav.slice(0, 2) : FALLBACK_UNITS;
  }, [liveUnits]);

  const [runStartedAt, setRunStartedAt] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const next = Date.now() - runStartedAt;
      setElapsed(Math.min(next, DEMO_DURATION_MS));
    }, 120);
    return () => window.clearInterval(timer);
  }, [runStartedAt]);

  const stage = stageForElapsed(elapsed);
  const replay = () => {
    setElapsed(0);
    setRunStartedAt(Date.now());
  };

  return (
    <main className="flex min-h-0 flex-1 flex-col bg-absolute-black">
      <DemoHeader stage={stage} elapsed={elapsed} replay={replay} />

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)_430px] xl:grid-rows-[minmax(0,1fr)_auto]">
        <CameraFeed active={stage >= 1} />
        <DroneFeed active={stage >= 3} verified={stage >= 5} />
        <DecisionPanel stage={stage} units={units} />

        <div className="space-y-3 xl:col-span-2">
          <ActionStrip stage={stage} />
          <Timeline stage={stage} />
        </div>
        <div className="space-y-3">
          <FleetRail units={units} stage={stage} />
          <div className="card px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="eyebrow-mono">Truth boundary</div>
                <div className="mt-1 text-ui text-platinum">Real coordination. Simulated imagery and side effects.</div>
              </div>
              <span className={`pill ${link === "connected" ? "pill-connected" : ""}`}>
                {link === "connected" ? "BACKEND LIVE" : "RECORDED RUN"}
              </span>
            </div>
            <p className="mt-3 text-[12px] leading-5 text-muted-silver">
              Fleet allocation and PX4 mission behavior mirror the validated two-vehicle SITL path. CCTV/drone footage, support call, spotlight and speaker are demo-only until their runtime integrations are explicitly connected.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
