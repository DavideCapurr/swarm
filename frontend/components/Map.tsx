"use client";

import { useEffect, useRef } from "react";
import maplibregl, { type Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Anomaly, FleetMember, Telemetry } from "@/lib/api";

type Props = {
  fleet: FleetMember[];
  anomalies: Anomaly[];
  telemetry: Record<string, Telemetry>;
};

const VINEYARD_CENTER: [number, number] = [8.03, 44.7]; // Langhe, Italy

export function MapView({ fleet, anomalies, telemetry }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  const anomalyMarkersRef = useRef<Record<string, maplibregl.Marker>>({});

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      // Free, no-API-key style — replace with custom SWARM style later.
      style: "https://demotiles.maplibre.org/style.json",
      center: VINEYARD_CENTER,
      zoom: 15,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Fleet + telemetry markers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const m of fleet) {
      seen.add(m.agent_id);
      const tele = telemetry[m.agent_id];
      const geo = tele?.geo ?? m.geo;
      const ll: [number, number] = [geo.lon, geo.lat];
      const existing = markersRef.current[m.agent_id];
      if (existing) {
        existing.setLngLat(ll);
      } else {
        const el = document.createElement("div");
        el.className =
          "w-2 h-2 bg-accent rounded-full ring-1 ring-accent/30 shadow-[0_0_8px_rgba(188,213,255,0.6)]";
        el.title = `${m.vendor}/${m.model} · ${m.fsm_state}`;
        markersRef.current[m.agent_id] = new maplibregl.Marker({ element: el })
          .setLngLat(ll)
          .addTo(map);
      }
    }
    // Remove markers for vanished agents.
    for (const id of Object.keys(markersRef.current)) {
      if (!seen.has(id)) {
        markersRef.current[id].remove();
        delete markersRef.current[id];
      }
    }
  }, [fleet, telemetry]);

  // Anomaly markers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const a of anomalies) {
      seen.add(a.id);
      const ll: [number, number] = [a.geo.lon, a.geo.lat];
      const existing = anomalyMarkersRef.current[a.id];
      if (existing) {
        existing.setLngLat(ll);
      } else {
        const el = document.createElement("div");
        el.className =
          "w-3 h-3 border border-warn rounded-full animate-pulse";
        el.title = `${a.kind} · c=${a.confidence.toFixed(2)}`;
        anomalyMarkersRef.current[a.id] = new maplibregl.Marker({ element: el })
          .setLngLat(ll)
          .addTo(map);
      }
    }
    for (const id of Object.keys(anomalyMarkersRef.current)) {
      if (!seen.has(id)) {
        anomalyMarkersRef.current[id].remove();
        delete anomalyMarkersRef.current[id];
      }
    }
  }, [anomalies]);

  return <div ref={containerRef} className="w-full h-full" />;
}
