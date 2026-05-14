"use client";

import { useEffect, useMemo, useState } from "react";
import {
  api,
  type Anomaly,
  type EventLog,
  type FleetMember,
  type Telemetry,
} from "@/lib/api";
import { SwarmSocket, type WSMessage } from "@/lib/ws";
import { MapView } from "@/components/Map";
import { FleetGrid } from "@/components/FleetGrid";
import { EventFeed } from "@/components/EventFeed";
import { StatusPill } from "@/components/StatusPill";
import { UnitDetail } from "@/components/UnitDetail";
import { agentStateToSwarm } from "@/lib/tokens";

type LinkState = "connected" | "connecting" | "lost";

export default function ControlSurface() {
  const [fleet, setFleet] = useState<Record<string, FleetMember>>({});
  const [anomalies, setAnomalies] = useState<Record<string, Anomaly>>({});
  const [telemetry, setTelemetry] = useState<Record<string, Telemetry>>({});
  const [events, setEvents] = useState<EventLog[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [link, setLink] = useState<LinkState>("connecting");
  const [clock, setClock] = useState<string>("");
  const [date, setDate] = useState<string>("");

  // Clock — operator surfaces always show time. Mono, fixed columns.
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      const pad = (n: number) => String(n).padStart(2, "0");
      setClock(`${pad(d.getHours())}:${pad(d.getMinutes())}`);
      const dd = pad(d.getDate());
      const mm = pad(d.getMonth() + 1);
      const yy = String(d.getFullYear()).slice(2);
      setDate(`${dd} · ${mm} · ${yy}`);
    };
    tick();
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  // Initial REST snapshot + live updates over WebSocket.
  useEffect(() => {
    (async () => {
      try {
        const [f, a, t, e] = await Promise.all([
          api.fleet(),
          api.anomalies(),
          api.telemetryLatest(),
          api.events(50),
        ]);
        setFleet(Object.fromEntries(f.fleet.map((m) => [m.agent_id, m])));
        setAnomalies(Object.fromEntries(a.anomalies.map((x) => [x.id, x])));
        setTelemetry(t.telemetry);
        setEvents(e.events);
      } catch {
        /* backend not up yet — the WS will fill in */
      }
    })();

    const sock = new SwarmSocket();
    sock.connect();
    setLink("connecting");
    // 0 means "no frame yet" — keeps the badge in "connecting" until the
    // first real WS message arrives, instead of flashing "live" for 6 s.
    let lastFrame = 0;
    const heartbeat = setInterval(() => {
      setLink((curr) => {
        if (lastFrame === 0) return curr === "lost" ? "lost" : "connecting";
        if (Date.now() - lastFrame < 6_000) return "connected";
        return "lost";
      });
    }, 2_000);
    const off = sock.onMessage((msg: WSMessage) => {
      lastFrame = Date.now();
      setLink("connected");
      if (msg.kind === "fleet") {
        setFleet((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
      } else if (msg.kind === "anomaly") {
        setAnomalies((prev) => ({ ...prev, [msg.data.id]: msg.data }));
        // Spread first, then overwrite `kind` with the event-type tag — the
        // anomaly's own kind is preserved as `anomaly_kind` for the feed body.
        setEvents((prev) => [
          ...prev.slice(-499),
          { ...msg.data, anomaly_kind: msg.data.kind, kind: "anomaly" },
        ]);
      } else if (msg.kind === "telemetry") {
        setTelemetry((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
      } else if (msg.kind === "progress") {
        setEvents((prev) => [...prev.slice(-499), { kind: "progress", ...msg.data }]);
      }
    });

    return () => {
      off();
      sock.close();
      clearInterval(heartbeat);
    };
  }, []);

  const fleetList = useMemo(() => Object.values(fleet), [fleet]);
  const anomalyList = useMemo(() => Object.values(anomalies), [anomalies]);

  // Aggregate stats for the head bar pill.
  const onlineCount = fleetList.filter((f) => f.fsm_state !== "OFFLINE").length;
  const totalCount = fleetList.length;
  const dockedCount = fleetList.filter((f) => f.fsm_state === "DOCKED").length;
  const airborneCount = fleetList.filter((f) =>
    ["TAKEOFF", "EN_ROUTE", "ON_STATION", "RTL", "LANDING", "DOCKING"].includes(f.fsm_state)
  ).length;
  const pendingAnomalies = anomalyList.filter((a) => !a.verified).length;

  // Highest-severity state in the fleet drives the header pill state color.
  const fleetSwarmState = fleetList.some((f) => agentStateToSwarm(f.fsm_state) === "attention")
    ? "attention"
    : airborneCount > 0
      ? "operational"
      : onlineCount > 0
        ? "rest"
        : "rest";

  const selectedUnit = selectedAgentId ? fleet[selectedAgentId] ?? null : null;

  return (
    <main className="min-h-screen grid grid-rows-[44px_1fr_220px_28px]">
      {/* ── HEAD BAR ───────────────────────────────────────────────────── */}
      <header className="flex items-center justify-between px-4 border-b border-gunmetal bg-absolute-black">
        <div className="flex items-center gap-6 text-muted-silver">
          <span className="flex items-center gap-2 text-platinum">
            <span className="swarm-ring" style={{ width: 8, height: 8 }} />
            <span className="swarm-wordmark text-platinum" style={{ fontSize: 13 }}>
              SWARM
            </span>
          </span>
          <span className="eyebrow-mono">/ control</span>
          <span className="eyebrow-mono text-platinum">/ session 0001</span>
          <LinkBadge state={link} />
        </div>
        <div className="flex items-center gap-6">
          <span className="mono-num text-platinum text-ui">{date}</span>
          <span className="mono-num text-platinum text-ui">{clock} UTC</span>
          <StatusPill state={fleetSwarmState}>
            {`${String(onlineCount).padStart(3, "0")} / ${String(totalCount).padStart(3, "0")} online`}
          </StatusPill>
          {pendingAnomalies > 0 && (
            <StatusPill state="attention">{`${pendingAnomalies} pending`}</StatusPill>
          )}
        </div>
      </header>

      {/* ── VIEWPORT + UNITS / DETAIL ───────────────────────────────────── */}
      <section className="grid grid-cols-[1fr_340px] min-h-0">
        <div className="relative overflow-hidden bg-absolute-black border-r border-gunmetal">
          <MapView fleet={fleetList} anomalies={anomalyList} telemetry={telemetry} />
          {/* Aggregate stats overlay — top-left of the viewport. */}
          <div className="absolute left-4 top-4 flex flex-col gap-1 eyebrow-mono">
            <span>sector · vineyard-01 · langhe</span>
            <span className="mono-num text-platinum text-ui mt-2">
              {String(dockedCount).padStart(3, "0")} docked · {String(airborneCount).padStart(3, "0")} airborne
            </span>
          </div>
        </div>
        <aside className="bg-obsidian p-4 overflow-y-auto">
          {selectedUnit ? (
            <UnitDetail
              unit={selectedUnit}
              telemetry={telemetry[selectedUnit.agent_id]}
              events={events}
              onClose={() => setSelectedAgentId(null)}
            />
          ) : (
            <FleetGrid
              fleet={fleetList}
              anomalies={anomalyList}
              onSelect={(id) => setSelectedAgentId(id)}
            />
          )}
        </aside>
      </section>

      {/* ── EVENT FEED ─────────────────────────────────────────────────── */}
      <footer className="bg-obsidian border-t border-gunmetal p-4 overflow-hidden">
        <EventFeed events={events} />
      </footer>

      {/* ── CANON FOOTER — the Control spread's bilingual cadence
            (docs/design-system/v1.html · spread 24 foot-bar). ───────────── */}
      <div className="bg-absolute-black border-t border-gunmetal px-4 flex items-center justify-between">
        <span className="font-editorial text-eyebrow text-muted-silver">
          One map. One intention.
        </span>
        <span className="font-editorial text-eyebrow text-muted-silver">
          Una mappa. Una sola intenzione.
        </span>
      </div>
    </main>
  );
}

function LinkBadge({ state }: { state: LinkState }) {
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
