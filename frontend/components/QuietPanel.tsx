"use client";

/**
 * QuietPanel — the Control viewport's right rail (DS Spread 24 canon).
 *
 * Five eyebrow-mono sections separated by hairline gunmetal:
 *   Fleet · Performance · Units · Recent action · (inline actions)
 * Plus a commander-only ghost row that hosts the EmergencyStop.
 *
 * Reads every value from `useSwarm()`. No client-side derivation that
 * the backend can supply. When a metric isn't calculable, the row
 * shows "—" rather than a fabricated number.
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useSwarm } from "@/lib/state";
import {
  AGENT_STATE_COPY,
  UNIT_LABEL_RING,
  ACTION_LABELS,
} from "@/lib/copy";
import type { UnitState } from "@/lib/api";
import { EmergencyStop } from "./EmergencyStop";

type Props = {
  onSelectAgent: (agentId: string) => void;
};

export function QuietPanel({ onSelectAgent }: Props) {
  const {
    units,
    docks,
    primaryDock,
    commands,
    autonomyEnabled,
    dispatch,
  } = useSwarm();

  // ── Fleet stats ──
  const online = units.filter((u) => u.fsm_state !== "OFFLINE");
  const total = units.length;
  const linkMean = online.length
    ? (online.reduce((s, u) => s + u.link_quality, 0) / online.length) * 100
    : null;
  const [nowMs, setNowMs] = useState<number>(() => 0);
  useEffect(() => {
    setNowMs(Date.now());
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const nextPatrolAt = primaryDock?.next_patrol_at ?? null;
  const nextPatrolDelta = useMemo(() => {
    if (!nextPatrolAt || nowMs === 0) return null;
    const next = new Date(nextPatrolAt).getTime();
    return Math.round((next - nowMs) / 1000);
  }, [nextPatrolAt, nowMs]);

  // ── Performance KPIs ──
  // Time to action = median of (accepted_at - submitted_at) across recent
  // operator commands. Cycles done = completed verifies. Weather pulled
  // from primaryDock when present.
  const completedLatencies = commands
    .filter((c) => c.accepted_at && c.submitted_at)
    .map((c) => {
      const a = new Date(c.accepted_at as string).getTime();
      const s = new Date(c.submitted_at).getTime();
      return a - s;
    })
    .filter((ms) => ms >= 0)
    .sort((a, b) => a - b);
  const medianMs = completedLatencies.length
    ? completedLatencies[Math.floor(completedLatencies.length / 2)]
    : null;
  const timeToAction = medianMs != null ? `${(medianMs / 1000).toFixed(1)} s` : "—";
  const cyclesDone = commands.filter(
    (c) => c.status === "completed" && c.action === "verify"
  ).length;
  const weather = primaryDock?.weather_lock
    ? "hold"
    : primaryDock?.wind_mps != null
      ? `clear · ${primaryDock.wind_mps.toFixed(1)} m/s`
      : "—";

  // ── Recent action ──
  const recent = useMemo(() => {
    if (commands.length === 0) return null;
    const sorted = [...commands].sort((a, b) =>
      a.submitted_at < b.submitted_at ? 1 : -1
    );
    return sorted[0];
  }, [commands]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex flex-col gap-5 p-4 flex-1 overflow-y-auto">
        <FleetSection
          onlineCount={online.length}
          totalCount={total}
          linkMean={linkMean}
          nextPatrolSec={nextPatrolDelta}
          dockCount={docks.length}
        />

        <Hairline />

        <PerformanceSection
          timeToAction={timeToAction}
          cyclesDone={cyclesDone}
          weather={weather}
          autonomyEnabled={autonomyEnabled}
        />

        <Hairline />

        <UnitsSection units={units} onSelect={onSelectAgent} />

        <Hairline />

        <RecentSection
          recentTime={recent?.submitted_at ?? null}
          recentText={recent ? recentLabel(recent.action, recent.status) : null}
          recentAuto={recent?.source === "autonomy"}
          recentRule={recent?.rule ?? null}
        />

        <Hairline />

        <InlineActions dispatch={dispatch} />
      </div>

      <CommanderGhost />
    </div>
  );
}

function Hairline() {
  return <div className="bg-gunmetal h-px" />;
}

function FleetSection({
  onlineCount,
  totalCount,
  linkMean,
  nextPatrolSec,
  dockCount,
}: {
  onlineCount: number;
  totalCount: number;
  linkMean: number | null;
  nextPatrolSec: number | null;
  dockCount: number;
}) {
  return (
    <section className="flex flex-col gap-3">
      <SectionLabel>Fleet</SectionLabel>
      <Row
        hero={`${String(onlineCount).padStart(3, "0")} / ${String(totalCount).padStart(3, "0")}`}
        label="online"
      />
      <Row
        hero={linkMean != null ? `${linkMean.toFixed(1)} %` : "—"}
        label="link mean"
      />
      <Row
        hero={nextPatrolSec != null ? formatDelta(nextPatrolSec) : "—"}
        label="next patrol"
      />
      {dockCount > 0 && (
        <span className="eyebrow-mono text-ash">
          {String(dockCount).padStart(3, "0")} {dockCount === 1 ? "dock" : "docks"}
        </span>
      )}
    </section>
  );
}

function PerformanceSection({
  timeToAction,
  cyclesDone,
  weather,
  autonomyEnabled,
}: {
  timeToAction: string;
  cyclesDone: number;
  weather: string;
  autonomyEnabled: boolean;
}) {
  return (
    <section className="flex flex-col gap-3">
      <SectionLabel>Performance</SectionLabel>
      <Row hero={timeToAction} label="time to action" />
      <Row hero={String(cyclesDone).padStart(3, "0")} label="cycles done" />
      <Row hero={weather} label="weather" mono={false} />
      {autonomyEnabled && (
        <span className="eyebrow-mono text-ash" data-testid="autonomy-ghost">
          autonomy · baseline
        </span>
      )}
    </section>
  );
}

function UnitsSection({
  units,
  onSelect,
}: {
  units: UnitState[];
  onSelect: (agentId: string) => void;
}) {
  if (units.length === 0) {
    return (
      <section className="flex flex-col gap-2">
        <SectionLabel>Units</SectionLabel>
        <span className="eyebrow-mono text-ash">no units online.</span>
      </section>
    );
  }
  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>Units</SectionLabel>
      {units.map((u) => {
        const meta = AGENT_STATE_COPY[u.fsm_state];
        const dotClass = `dot dot-${meta.swarm}`;
        return (
          <button
            key={u.agent_id}
            type="button"
            onClick={() => onSelect(u.agent_id)}
            className="flex items-center justify-between py-1.5 text-left transition-colors duration-press ease-swarm hover:bg-graphite/30 focus:outline-none focus-visible:bg-graphite/40 px-1 -mx-1"
            data-testid={`unit-row-${u.agent_id}`}
          >
            <span className="eyebrow-mono text-platinum">
              {UNIT_LABEL_RING(u.agent_id)}
            </span>
            <span className="flex items-center gap-2">
              <span className={dotClass} />
              <span className="eyebrow-mono text-platinum">{meta.verb}</span>
              <span className="mono-num text-ash text-eyebrow">
                {u.battery_pct.toFixed(0)} %
              </span>
            </span>
          </button>
        );
      })}
    </section>
  );
}

function RecentSection({
  recentTime,
  recentText,
  recentAuto,
  recentRule,
}: {
  recentTime: string | null;
  recentText: string | null;
  recentAuto: boolean;
  recentRule: string | null;
}) {
  return (
    <section className="flex flex-col gap-2">
      <SectionLabel>Recent action</SectionLabel>
      {recentText && recentTime ? (
        <span className="eyebrow-mono text-platinum">
          <span className="mono-num text-platinum">{shortTime(recentTime)}</span>
          {" · "}
          {recentAuto && (
            <span
              className="text-orbital-blue"
              data-testid="recent-auto-chip"
            >
              {recentRule ? `auto · ${recentRule.toLowerCase()} · ` : "auto · "}
            </span>
          )}
          {recentText}
        </span>
      ) : (
        <span className="eyebrow-mono text-ash">no operator action yet.</span>
      )}
      <Link
        href="/system"
        className="eyebrow-mono text-ash hover:text-platinum transition-colors duration-press ease-swarm"
      >
        — see full audit
      </Link>
    </section>
  );
}

function InlineActions({
  dispatch,
}: {
  dispatch: ReturnType<typeof useSwarm>["dispatch"];
}) {
  const { anomalies } = useSwarm();
  const focus = anomalies.find(
    (a) => a.state === "pending" || a.state === "verifying"
  );
  const verifyEnabled = !!focus;
  const onVerify = () => {
    if (!focus) return;
    void dispatch("verify", `anomaly:${focus.id}`);
  };
  const onHold = () => {
    void dispatch("hold_patrol", "session:current");
  };
  return (
    <section className="flex flex-col gap-2">
      <div className="flex gap-2">
        <button
          type="button"
          disabled={!verifyEnabled}
          onClick={onVerify}
          className="flex-1 bg-platinum text-absolute-black font-display text-ui rounded-input px-3 py-2 transition-all duration-press ease-swarm hover:brightness-105 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed"
          title={ACTION_LABELS.verify.hint}
        >
          {ACTION_LABELS.verify.label}
        </button>
        <button
          type="button"
          onClick={onHold}
          className="flex-1 border border-graphite text-platinum font-display text-ui rounded-input px-3 py-2 transition-all duration-press ease-swarm hover:bg-graphite/40 active:scale-[0.99]"
          title={ACTION_LABELS.hold_patrol.hint}
        >
          {ACTION_LABELS.hold_patrol.label}
        </button>
      </div>
    </section>
  );
}

function CommanderGhost() {
  return (
    <div className="border-t border-gunmetal p-4 bg-absolute-black">
      <EmergencyStop />
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="eyebrow-mono text-ash">— {children}</div>;
}

function Row({
  hero,
  label,
  mono = true,
}: {
  hero: string;
  label: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between">
      <span
        className={`${mono ? "mono-num" : "font-display"} text-platinum`}
        style={{ fontSize: 22, lineHeight: 1.1 }}
      >
        {hero}
      </span>
      <span className="eyebrow-mono text-ash">{label}</span>
    </div>
  );
}

function formatDelta(sec: number): string {
  if (sec === 0) return "T 00:00";
  const sign = sec < 0 ? "+" : "−";
  const abs = Math.abs(sec);
  const m = Math.floor(abs / 60);
  const s = abs % 60;
  return `T ${sign}${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function shortTime(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}`;
}

function recentLabel(
  action: string,
  status: string
): string {
  const verb = action.replace(/_/g, " ");
  const result =
    status === "accepted" || status === "in_flight" || status === "completed"
      ? "accepted"
      : status === "rejected" || status === "timed_out"
        ? "rejected"
        : status;
  return `${verb} ${result}`;
}
