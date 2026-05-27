"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import maplibregl, { type Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AnomalyView, OperatorCommand, UnitState } from "@/lib/api";
import { agentStateToSwarm } from "@/lib/tokens";
import { AGENT_STATE_COPY, ANOMALY_STATE_COPY, UNIT_LABEL } from "@/lib/copy";
import { findActiveAutonomyCommand } from "@/lib/autonomy";

type Props = {
  units: UnitState[];
  anomalies: AnomalyView[];
  commands?: OperatorCommand[];
  onMapReady?: (map: Map) => void;
  children?: (map: Map | null) => ReactNode;
};

const VINEYARD_CENTER: [number, number] = [8.03, 44.7]; // Langhe, IT

/**
 * Map style — dark, minimal, matched to the SWARM Control surface.
 * MapLibre's "blank" style we build inline so we have full control of color.
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
    { id: "osm", type: "raster", source: "osm", paint: { "raster-opacity": 0.65 } },
  ],
};

const DOT_STATE_CLASS: Record<string, string> = {
  rest: "dot dot-rest",
  connected: "dot dot-connected",
  operational: "dot dot-operational",
  attention: "dot dot-attention",
};

export function MapView({ units, anomalies, commands, onMapReady, children }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const droneMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  const anomalyMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  const [mapReady, setMapReady] = useState<Map | null>(null);
  const router = useRouter();

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
    const ready = () => {
      setMapReady(map);
      onMapReady?.(map);
    };
    if (map.isStyleLoaded()) ready();
    else map.once("load", ready);
    return () => {
      map.remove();
      mapRef.current = null;
      setMapReady(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Unit dots — geo comes from `UnitState`, which the coordinator refreshes
  // on every telemetry tick. No separate telemetry overlay needed.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const u of units) {
      seen.add(u.agent_id);
      const ll: [number, number] = [u.geo.lon, u.geo.lat];
      const swarmState = agentStateToSwarm(u.fsm_state);
      const verb = AGENT_STATE_COPY[u.fsm_state].verb;
      const labelText = `${UNIT_LABEL(u.agent_id)} · ${verb}`;
      const tooltip = `${UNIT_LABEL(u.agent_id)} · ${verb} · battery ${u.battery_pct.toFixed(0)} %`;
      const existing = droneMarkersRef.current[u.agent_id];
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
          label.textContent = labelText;
        }
        el.title = tooltip;
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
        label.textContent = labelText;
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
        el.title = tooltip;

        droneMarkersRef.current[u.agent_id] = new maplibregl.Marker({
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
  }, [units]);

  // Anomaly markers — launch-amber concentric rings. When an autonomy
  // command is in flight for the anomaly we flip the callout to Orbital
  // Blue and prepend an AUTO eyebrow so the operator (and a YC observer)
  // sees that SwarmOS itself made the call. Filters out resolved
  // anomalies (dismissed / marked_known) so only live signals appear.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const live = anomalies.filter(
      (a) => a.state !== "dismissed" && a.state !== "marked_known"
    );
    const cmds = commands ?? [];
    const seen = new Set<string>();
    for (const a of live) {
      seen.add(a.id);
      const ll: [number, number] = [a.geo.lon, a.geo.lat];
      const auto = findActiveAutonomyCommand(cmds, a.id);
      const calloutText = anomalyCallout(a, auto);
      const color = auto ? "#7BE7FF" : "#FFB45C";
      const existing = anomalyMarkersRef.current[a.id];
      if (!existing) {
        const el = document.createElement("div");
        el.style.position = "relative";
        el.style.width = "0";
        el.style.height = "0";

        const inner = document.createElement("span");
        inner.style.position = "absolute";
        inner.style.left = "-3px";
        inner.style.top = "-3px";
        inner.style.width = "6px";
        inner.style.height = "6px";
        inner.style.borderRadius = "50%";
        inner.style.background = "#FFB45C";

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

        const leader = document.createElement("span");
        leader.setAttribute("data-leader", "");
        leader.style.position = "absolute";
        leader.style.left = "10px";
        leader.style.top = "-1px";
        leader.style.width = "22px";
        leader.style.height = "1px";
        leader.style.background = color;
        leader.style.opacity = "0.7";

        const callout = document.createElement("button");
        callout.type = "button";
        callout.setAttribute("data-callout", "");
        callout.setAttribute("data-testid", `anomaly-callout-${a.id}`);
        callout.textContent = calloutText;
        callout.style.position = "absolute";
        callout.style.left = "34px";
        callout.style.top = "-8px";
        callout.style.fontFamily = '"IBM Plex Mono", monospace';
        callout.style.fontSize = "9px";
        callout.style.letterSpacing = "0.22em";
        callout.style.textTransform = "uppercase";
        callout.style.color = color;
        callout.style.background = "rgba(11,14,17,0.85)";
        callout.style.padding = "3px 6px";
        callout.style.border = `1px solid ${color}`;
        callout.style.borderRadius = "2px";
        callout.style.whiteSpace = "nowrap";
        callout.style.cursor = "pointer";
        if (auto) callout.setAttribute("data-auto", "");
        callout.addEventListener("click", (e) => {
          e.stopPropagation();
          router.push(`/verify/${a.id}`);
        });

        el.appendChild(ring);
        el.appendChild(inner);
        el.appendChild(leader);
        el.appendChild(callout);
        anomalyMarkersRef.current[a.id] = new maplibregl.Marker({ element: el })
          .setLngLat(ll)
          .addTo(map);
      } else {
        existing.setLngLat(ll);
        const el = existing.getElement();
        const callout = el.querySelector("[data-callout]") as HTMLElement | null;
        const leader = el.querySelector("[data-leader]") as HTMLElement | null;
        if (callout) {
          callout.textContent = calloutText;
          callout.style.color = color;
          callout.style.border = `1px solid ${color}`;
          if (auto) callout.setAttribute("data-auto", "");
          else callout.removeAttribute("data-auto");
        }
        if (leader) leader.style.background = color;
      }
    }
    for (const id of Object.keys(anomalyMarkersRef.current)) {
      if (!seen.has(id)) {
        anomalyMarkersRef.current[id].remove();
        delete anomalyMarkersRef.current[id];
      }
    }
  }, [anomalies, units, commands, router]);

  return (
    <div className="relative w-full h-full">
      {/* Map container */}
      <div ref={containerRef} className="absolute inset-0" />

      {/* Map-overlay children (Sector + Route layers). Rendered as no-DOM
          children that hook into the maplibre instance. */}
      {children ? children(mapReady) : null}

      {/* Orbit graticule overlay — the brand signature, traced over the map.
          Mirrors spread 24: three concentric ellipses, a solid axial cross,
          a dashed operating-perimeter circle. */}
      <svg
        className="pointer-events-none absolute inset-0 w-full h-full"
        viewBox="0 0 800 500"
        preserveAspectRatio="xMidYMid slice"
      >
        <g stroke="#1A2026" strokeWidth="0.8" fill="none" opacity="0.55">
          <ellipse cx="400" cy="250" rx="340" ry="120" />
          <ellipse cx="400" cy="250" rx="240" ry="84" />
          <ellipse cx="400" cy="250" rx="140" ry="48" />
          <line x1="0" y1="250" x2="800" y2="250" />
          <line x1="400" y1="40" x2="400" y2="460" />
        </g>
        <g fill="none" stroke="#A8AFB8" strokeWidth="0.6" strokeDasharray="2 4" opacity="0.65">
          <circle cx="400" cy="250" r="160" />
        </g>
      </svg>

      <CornerStamps units={units} />
    </div>
  );
}

const VINEYARD_AIRBORNE_STATES = new Set<UnitState["fsm_state"]>([
  "TAKEOFF",
  "EN_ROUTE",
  "ON_STATION",
  "RTL",
  "LANDING",
  "DOCKING",
]);

function CornerStamps({ units }: { units: UnitState[] }) {
  const airborne = units.filter((u) => VINEYARD_AIRBORNE_STATES.has(u.fsm_state));
  const maxAlt = airborne.length
    ? airborne.reduce((acc, u) => Math.max(acc, u.altitude_agl_m), 0)
    : null;
  const lat = VINEYARD_CENTER[1];
  const lon = VINEYARD_CENTER[0];
  return (
    <>
      <div className="pointer-events-none absolute right-4 top-4 eyebrow-mono mono-num text-right text-ash">
        {maxAlt != null ? `altitude · ${maxAlt.toFixed(0)} m` : "altitude · —"}
      </div>
      <div className="pointer-events-none absolute left-4 bottom-4 eyebrow-mono mono-num text-ash">
        {lat.toFixed(3)}°N · {lon.toFixed(3)}°E
      </div>
    </>
  );
}

function anomalyCallout(
  a: AnomalyView,
  auto: OperatorCommand | null
): string {
  const pct = Math.round(a.confidence * 100);
  const state = ANOMALY_STATE_COPY[a.state];
  let prefix = "";
  if (auto) {
    prefix = auto.rule ? `auto · ${auto.rule.toLowerCase()} · ` : "auto · ";
  }
  if (a.state === "verifying" && a.verifying_agent) {
    return `${prefix}${UNIT_LABEL(a.verifying_agent)} · ${state}`;
  }
  if (a.state === "verified" || a.state === "escalated") {
    return `${prefix}anomaly ${state}`;
  }
  return `${prefix}anomaly ${state} · confidence ${String(pct).padStart(3, "0")} %`;
}

