"use client";

import { useEffect, useRef } from "react";
import maplibregl, { type Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Anomaly, FleetMember, Telemetry } from "@/lib/api";
import { agentStateToSwarm } from "@/lib/tokens";

type Props = {
  fleet: FleetMember[];
  anomalies: Anomaly[];
  telemetry: Record<string, Telemetry>;
};

const VINEYARD_CENTER: [number, number] = [8.03, 44.7]; // Langhe, IT

/**
 * Map style — dark, minimal, matched to the SWARM Control surface.
 * MapLibre's "blank" style we build inline so we have full control of color.
 * For real basemaps later, swap to a custom Mapbox/Stamen style.
 */
const SWARM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    osm: {
      type: "raster",
      tiles: [
        "https://a.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://b.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
        "https://c.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      attribution: "© OpenStreetMap · CartoDB",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#030406" } },
    { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.45 } },
  ],
};

const DOT_STATE_CLASS: Record<string, string> = {
  rest: "dot dot-rest",
  connected: "dot dot-connected",
  operational: "dot dot-operational",
  attention: "dot dot-attention",
};

export function MapView({ fleet, anomalies, telemetry }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const droneMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  const anomalyMarkersRef = useRef<Record<string, maplibregl.Marker>>({});

  // Map lifecycle.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SWARM_STYLE,
      center: VINEYARD_CENTER,
      zoom: 14.5,
      attributionControl: { compact: true },
      pitch: 0,
    });
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Fleet dots + telemetry trail.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const m of fleet) {
      seen.add(m.agent_id);
      const tele = telemetry[m.agent_id];
      const geo = tele?.geo ?? m.geo;
      const ll: [number, number] = [geo.lon, geo.lat];
      const swarmState = agentStateToSwarm(m.fsm_state);
      const existing = droneMarkersRef.current[m.agent_id];
      if (existing) {
        existing.setLngLat(ll);
        const el = existing.getElement();
        const dot = el.querySelector("[data-dot]") as HTMLElement | null;
        if (dot) {
          dot.className = DOT_STATE_CLASS[swarmState];
          dot.style.width = "10px";
          dot.style.height = "10px";
        }
        const label = el.querySelector("[data-label]") as HTMLElement | null;
        if (label) {
          label.textContent = unitLabel(m.agent_id);
        }
      } else {
        const el = document.createElement("div");
        el.style.position = "relative";
        el.style.display = "flex";
        el.style.alignItems = "center";
        el.style.gap = "6px";
        el.style.transform = "translate(-5px, -5px)";

        const dot = document.createElement("span");
        dot.setAttribute("data-dot", "");
        dot.className = DOT_STATE_CLASS[swarmState];
        dot.style.width = "10px";
        dot.style.height = "10px";

        const label = document.createElement("span");
        label.setAttribute("data-label", "");
        label.textContent = unitLabel(m.agent_id);
        label.style.fontFamily = '"IBM Plex Mono", monospace';
        label.style.fontSize = "10px";
        label.style.letterSpacing = "0.18em";
        label.style.textTransform = "uppercase";
        label.style.color = "#A8AFB8";
        label.style.background = "rgba(11,14,17,0.7)";
        label.style.padding = "2px 6px";
        label.style.border = "1px solid #1A2026";
        label.style.borderRadius = "2px";

        el.appendChild(dot);
        el.appendChild(label);
        el.title = `${m.vendor}/${m.model} · ${m.fsm_state}`;

        droneMarkersRef.current[m.agent_id] = new maplibregl.Marker({
          element: el,
          anchor: "left",
        })
          .setLngLat(ll)
          .addTo(map);
      }
    }
    for (const id of Object.keys(droneMarkersRef.current)) {
      if (!seen.has(id)) {
        droneMarkersRef.current[id].remove();
        delete droneMarkersRef.current[id];
      }
    }
  }, [fleet, telemetry]);

  // Anomaly markers — launch-amber concentric rings.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const a of anomalies) {
      seen.add(a.id);
      const ll: [number, number] = [a.geo.lon, a.geo.lat];
      const existing = anomalyMarkersRef.current[a.id];
      if (!existing) {
        const el = document.createElement("div");
        el.style.position = "relative";
        el.style.width = "0";
        el.style.height = "0";
        el.style.transform = "translate(0,0)";

        const inner = document.createElement("span");
        inner.style.position = "absolute";
        inner.style.left = "-3px";
        inner.style.top = "-3px";
        inner.style.width = "6px";
        inner.style.height = "6px";
        inner.style.borderRadius = "50%";
        inner.style.background = "#FFB45C";
        inner.style.boxShadow = "0 0 6px rgba(255,180,92,0.6)";

        const ring = document.createElement("span");
        ring.style.position = "absolute";
        ring.style.left = "-12px";
        ring.style.top = "-12px";
        ring.style.width = "24px";
        ring.style.height = "24px";
        ring.style.borderRadius = "50%";
        ring.style.border = "1px solid #FFB45C";
        ring.style.opacity = "0.6";
        ring.style.animation = "breath 4s cubic-bezier(0.2, 0.7, 0.1, 1) infinite";

        el.appendChild(ring);
        el.appendChild(inner);
        el.title = `${a.kind} · c=${a.confidence.toFixed(2)}`;
        anomalyMarkersRef.current[a.id] = new maplibregl.Marker({ element: el })
          .setLngLat(ll)
          .addTo(map);
      } else {
        existing.setLngLat(ll);
      }
    }
    for (const id of Object.keys(anomalyMarkersRef.current)) {
      if (!seen.has(id)) {
        anomalyMarkersRef.current[id].remove();
        delete anomalyMarkersRef.current[id];
      }
    }
  }, [anomalies]);

  return (
    <div className="relative w-full h-full">
      {/* Map container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Orbit graticule overlay — the brand signature, traced over the map.
          Mirrors spread 24: three concentric ellipses, a solid axial cross,
          a dashed operating-perimeter circle. */}
      <svg
        className="pointer-events-none absolute inset-0 w-full h-full"
        viewBox="0 0 800 500"
        preserveAspectRatio="xMidYMid slice"
      >
        <g stroke="#1A2026" strokeWidth="0.6" fill="none">
          <ellipse cx="400" cy="250" rx="340" ry="120" />
          <ellipse cx="400" cy="250" rx="240" ry="84" />
          <ellipse cx="400" cy="250" rx="140" ry="48" />
          <line x1="0" y1="250" x2="800" y2="250" />
          <line x1="400" y1="40" x2="400" y2="460" />
        </g>
        <g fill="none" stroke="#A8AFB8" strokeWidth="0.6" strokeDasharray="2 4" opacity="0.45">
          <circle cx="400" cy="250" r="160" />
        </g>
      </svg>

      {/* Cartographic corner stamps — four quadrants, the spec's ambient
          context strip (spread 24). */}
      <div className="pointer-events-none absolute right-4 top-4 eyebrow-mono mono-num text-right">
        alt 240m
      </div>
      <div className="pointer-events-none absolute right-4 bottom-4 eyebrow-mono mono-num text-right">
        44.700°N · 8.030°E
      </div>
      <div className="pointer-events-none absolute left-4 bottom-4 eyebrow-mono mono-num">
        wind 4.2 m/s
      </div>
    </div>
  );
}

/** "sim-1" → "001 · RING-A" — units always read as zero-padded numerals. */
function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  const n = m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
  return `${n} · ring-a`;
}
