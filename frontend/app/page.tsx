"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Anomaly, type EventLog, type FleetMember, type Telemetry } from "@/lib/api";
import { SwarmSocket, type WSMessage } from "@/lib/ws";
import { MapView } from "@/components/Map";
import { FleetGrid } from "@/components/FleetGrid";
import { EventFeed } from "@/components/EventFeed";

export default function OperatorDashboard() {
  const [fleet, setFleet] = useState<Record<string, FleetMember>>({});
  const [anomalies, setAnomalies] = useState<Record<string, Anomaly>>({});
  const [telemetry, setTelemetry] = useState<Record<string, Telemetry>>({});
  const [events, setEvents] = useState<EventLog[]>([]);

  useEffect(() => {
    // Initial REST snapshot.
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
        /* backend not up yet — websocket will fill in */
      }
    })();

    // Live updates over WebSocket.
    const sock = new SwarmSocket();
    sock.connect();
    const off = sock.onMessage((msg: WSMessage) => {
      if (msg.kind === "fleet") {
        setFleet((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
      } else if (msg.kind === "anomaly") {
        setAnomalies((prev) => ({ ...prev, [msg.data.id]: msg.data }));
        setEvents((prev) => [...prev.slice(-499), { kind: "anomaly", ...msg.data }]);
      } else if (msg.kind === "telemetry") {
        setTelemetry((prev) => ({ ...prev, [msg.data.agent_id]: msg.data }));
      } else if (msg.kind === "progress") {
        setEvents((prev) => [...prev.slice(-499), { kind: "progress", ...msg.data }]);
      }
    });

    return () => {
      off();
      sock.close();
    };
  }, []);

  const fleetList = useMemo(() => Object.values(fleet), [fleet]);
  const anomalyList = useMemo(() => Object.values(anomalies), [anomalies]);

  return (
    <main className="min-h-screen grid grid-cols-[1fr_360px] grid-rows-[60px_1fr_240px] gap-px bg-line">
      <header className="col-span-2 bg-bg flex items-center px-6 orbital-line">
        <div className="flex items-baseline gap-4">
          <h1 className="text-lg tracking-[0.3em]">SWARM</h1>
          <span className="text-muted text-xs">operator · v0.1</span>
        </div>
        <div className="ml-auto text-xs text-muted">
          {fleetList.length} units · {anomalyList.length} anomalies
        </div>
      </header>

      <section className="bg-bg overflow-hidden">
        <MapView fleet={fleetList} anomalies={anomalyList} telemetry={telemetry} />
      </section>

      <aside className="bg-surface p-4 overflow-y-auto">
        <FleetGrid fleet={fleetList} />
      </aside>

      <section className="col-span-2 bg-surface p-4 overflow-y-auto">
        <EventFeed events={events} />
      </section>
    </main>
  );
}
