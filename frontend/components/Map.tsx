"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useRouter } from "next/navigation";
import maplibregl, { type Map } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { AnomalySource, AnomalyView, OperatorCommand, UnitState } from "@/lib/api";
import { agentStateToSwarm, tokens, type SwarmState } from "@/lib/tokens";
import { AGENT_STATE_COPY, UNIT_LABEL } from "@/lib/copy";
import { anomalyCallout } from "@/lib/derive";
import {
  IconAnomaly,
  IconDroneCv,
  IconFireDetector,
  IconThermalSat,
  type IconProps,
} from "@/icons";
import { findLatestAutonomyCommand } from "@/lib/autonomy";

// Per-source provenance glyph, rendered into the imperative marker via
// `renderToStaticMarkup` so the icon set in `icons/index.tsx` stays the single
// source of truth (no duplicated SVG paths here).
const SOURCE_ICON: Record<AnomalySource, (p: IconProps) => React.ReactElement> = {
  thermal_sat: IconThermalSat,
  fire_detector: IconFireDetector,
  drone_cv: IconDroneCv,
  unknown: IconAnomaly,
};

function sourceGlyphMarkup(source: AnomalySource): string {
  const Icon = SOURCE_ICON[source] ?? IconAnomaly;
  return renderToStaticMarkup(<Icon size={12} />);
}

type Props = {
  units: UnitState[];
  anomalies: AnomalyView[];
  commands?: OperatorCommand[];
  selectedAgentId?: string | null;
  onSelectUnit?: (agentId: string) => void;
  onMapReady?: (map: Map) => void;
  children?: (map: Map | null) => ReactNode;
};

export const VINEYARD_CENTER: [number, number] = [8.03, 44.7]; // Langhe, IT

// Selectable real-world basemaps, layered *under* the tactical overlay:
//   - "tactical": CARTO dark-matter — dark, monochrome, design-system §5.2.
//   - "satellite": Esri World Imagery — real aerial imagery of the ground.
// Both hosts are CSP-allowlisted in `next.config.mjs` (MAP_CONNECT_SRC) and
// covered by `img-src https:`. Each carries its own licence attribution so the
// compact attribution control always credits the provider on screen.
export type BasemapMode = "tactical" | "satellite";

type BasemapConfig = {
  tiles: string[];
  maxzoom: number;
  attribution: string;
  opacity: number;
};

export const BASEMAPS: Record<BasemapMode, BasemapConfig> = {
  tactical: {
    // `@2x` tiles stay crisp on retina.
    tiles: ["a", "b", "c"].map(
      (s) => `https://${s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}@2x.png`
    ),
    maxzoom: 20,
    attribution:
      '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors © <a href="https://carto.com/attributions">CARTO</a>',
    // Muted: the dark map is context; accent state stays the loudest thing.
    opacity: 0.85,
  },
  satellite: {
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    maxzoom: 19,
    attribution:
      'Tiles © <a href="https://www.esri.com/">Esri</a> — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
    // Ground truth: show the imagery fully; the tactical overlay rides on top.
    opacity: 1,
  },
};

const BASEMAP_SRC = "swarm-basemap";
const BASEMAP_LAYER = "swarm-basemap-raster";
export const BASEMAP_STORAGE_KEY = "swarm.basemap";

export function readStoredBasemap(): BasemapMode {
  if (typeof window === "undefined") return "tactical";
  const stored = window.localStorage.getItem(BASEMAP_STORAGE_KEY);
  return stored === "satellite" || stored === "tactical" ? stored : "tactical";
}

/**
 * Base style — an absolute-black backdrop only. The selected real-world
 * basemap raster is attached as the lowest layer at runtime (see the basemap
 * effect in `MapView`), so the surface is never light even before tiles load.
 * The tactical grid, rings and parcel are drawn over it by `<TacticalBasemap/>`,
 * and unit/anomaly markers stack above that.
 */
const SWARM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {},
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#030406" } },
  ],
};

// State → accent. Monochrome platinum at rest; accent only when active.
export const STATE_COLOR: Record<SwarmState, string> = {
  rest: tokens.color.platinum,
  connected: tokens.color.orbitalBlue,
  operational: tokens.color.signalGreen,
  attention: tokens.color.launchAmber,
};

const AIRBORNE_STATES = new Set<UnitState["fsm_state"]>([
  "TAKEOFF",
  "EN_ROUTE",
  "ON_STATION",
  "RTL",
  "LANDING",
  "DOCKING",
]);

// Direction-of-travel delta ("ownship" glyph). Points north; the wrapper is
// rotated to heading. Hairline absolute-black keyline keeps it legible on the
// dark grid.
function deltaGlyph(color: string): string {
  return `<svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 1.5 L15.5 16 L9 12 L2.5 16 Z" fill="${color}" stroke="#030406" stroke-width="0.85" stroke-linejoin="round"/></svg>`;
}

// Parked unit — hollow rounded square with a centre dot. No heading.
function dockedGlyph(color: string): string {
  return `<svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2.25" y="2.25" width="9.5" height="9.5" rx="1.5" stroke="${color}" stroke-width="1.25"/><circle cx="7" cy="7" r="1.4" fill="${color}"/></svg>`;
}

export function MapView({
  units,
  anomalies,
  commands,
  selectedAgentId,
  onSelectUnit,
  onMapReady,
  children,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const droneMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  const anomalyMarkersRef = useRef<Record<string, maplibregl.Marker>>({});
  const [mapReady, setMapReady] = useState<Map | null>(null);
  const [basemapMode, setBasemapMode] = useState<BasemapMode>(readStoredBasemap);
  const router = useRouter();
  // Latest selection callback, so the imperative marker click always calls
  // the current handler without rebinding listeners on every telemetry tick.
  const onSelectUnitRef = useRef(onSelectUnit);
  onSelectUnitRef.current = onSelectUnit;

  // Map lifecycle.
  useEffect(() => {
    if (!containerRef.current) return;
    // Phase 7.G — preserveDrawingBuffer is required for the M1 screenshot
    // harness (Playwright captures the WebGL frame *after* Chrome has
    // already cleared the default drawing buffer). Production paths skip
    // this flag because it costs ~5–10 % render perf. maplibre-gl v5 moved
    // the WebGL context flags out of the top-level options into
    // `canvasContextAttributes`, so passing it at the top level is silently
    // dropped (and rejected by tsc).
    const isCapture = typeof window !== "undefined" && (window as unknown as { __M1_CAPTURE__?: boolean }).__M1_CAPTURE__;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: SWARM_STYLE,
      center: VINEYARD_CENTER,
      zoom: 14.5,
      attributionControl: { compact: true },
      pitch: 0,
      canvasContextAttributes: { preserveDrawingBuffer: isCapture },
    });
    map.dragRotate.disable();
    map.touchZoomRotate.disableRotation();
    mapRef.current = map;
    // Phase 7.G — expose the map instance to the M1 screenshot harness
    // (`scripts/m1_capture_screenshots.py`) so it can force a `resize()`
    // after the React tree settles. Guarded by the `__M1_CAPTURE__` flag
    // so production builds don't leak the reference.
    if (typeof window !== "undefined" && (window as unknown as { __M1_CAPTURE__?: boolean }).__M1_CAPTURE__) {
      (window as unknown as { __SWARM_MAP__: Map }).__SWARM_MAP__ = map;
    }
    const ready = () => {
      setMapReady(map);
      onMapReady?.(map);
    };
    if (map.isStyleLoaded()) ready();
    else map.once("load", ready);
    // Keep maplibre's internal viewport in sync with the container — the
    // initial measurement can land before the parent flex/grid chain
    // settles, leaving the canvas at the first-paint height. We observe
    // the *parent* because maplibre locks an inline height on its own
    // container, so a ResizeObserver attached to it would never fire.
    const parentEl = containerRef.current.parentElement ?? containerRef.current;
    const ro = new ResizeObserver(() => map.resize());
    ro.observe(parentEl);
    // Belt-and-suspenders: nudge maplibre to remeasure on a couple of
    // animation frames after first paint. ResizeObserver alone misses
    // the case where the parent's height is already final at first
    // measurement and so RO fires with no further changes.
    requestAnimationFrame(() => map.resize());
    setTimeout(() => map.resize(), 250);
    setTimeout(() => map.resize(), 1000);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      droneMarkersRef.current = {};
      anomalyMarkersRef.current = {};
      setMapReady(null);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Real-world basemap — (re)attached as the lowest raster layer whenever the
  // operator switches mode. Inserted just above the black `bg` so the tactical
  // grid, sectors and unit markers always stack on top. Each provider declares
  // its own attribution, so the compact control credits the right source.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const cfg = BASEMAPS[basemapMode];
    const apply = () => {
      if (map.getLayer(BASEMAP_LAYER)) map.removeLayer(BASEMAP_LAYER);
      if (map.getSource(BASEMAP_SRC)) map.removeSource(BASEMAP_SRC);
      map.addSource(BASEMAP_SRC, {
        type: "raster",
        tiles: cfg.tiles,
        tileSize: 256,
        maxzoom: cfg.maxzoom,
        attribution: cfg.attribution,
      });
      // Keep the basemap at the bottom: insert before the first non-bg layer
      // (the tactical grid, sectors, etc.). When none exist yet it lands just
      // above `bg`, and later overlays still add on top.
      const layers = map.getStyle().layers ?? [];
      const beforeId = layers.find(
        (l) => l.id !== "bg" && l.id !== BASEMAP_LAYER
      )?.id;
      map.addLayer(
        {
          id: BASEMAP_LAYER,
          type: "raster",
          source: BASEMAP_SRC,
          paint: { "raster-opacity": cfg.opacity },
        },
        beforeId
      );
    };
    if (map.isStyleLoaded()) apply();
    else map.once("styledata", apply);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(BASEMAP_STORAGE_KEY, basemapMode);
    }
  }, [basemapMode, mapReady]);

  // Unit markers — geo comes from `UnitState`, refreshed on every telemetry
  // tick. Each unit is a directional "ownship" glyph (heading delta) with a
  // sweep, a heading vector, a sensor radius and a telemetry tag — not a bare
  // dot. Airborne units animate so the map is never static.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const seen = new Set<string>();
    for (const u of units) {
      seen.add(u.agent_id);
      const ll: [number, number] = [u.geo.lon, u.geo.lat];
      const swarmState = agentStateToSwarm(u.fsm_state);
      const color = STATE_COLOR[swarmState];
      const airborne = AIRBORNE_STATES.has(u.fsm_state);
      const verb = AGENT_STATE_COPY[u.fsm_state].verb;
      const selected = u.agent_id === selectedAgentId;
      const id = UNIT_LABEL(u.agent_id).toUpperCase();
      const sub = airborne
        ? `${verb} · ${u.altitude_agl_m.toFixed(0)} m · ${u.battery_pct.toFixed(0)}%`
        : `${verb} · ${u.battery_pct.toFixed(0)}%`;

      let marker = droneMarkersRef.current[u.agent_id];
      if (!marker) {
        const el = document.createElement("div");
        el.style.position = "relative";
        el.style.width = "0";
        el.style.height = "0";

        const selectRing = document.createElement("span");
        selectRing.setAttribute("data-select", "");
        selectRing.className = "unit-select-ring";

        const radius = document.createElement("span");
        radius.setAttribute("data-radius", "");
        radius.className = "unit-radius";

        const sweep = document.createElement("span");
        sweep.setAttribute("data-sweep", "");
        sweep.className = "unit-sweep";

        // Rotated container: holds the glyph + heading vector. Rotates about
        // the geo point (transform-origin 0,0).
        const rot = document.createElement("div");
        rot.setAttribute("data-rot", "");
        rot.style.position = "absolute";
        rot.style.left = "0";
        rot.style.top = "0";
        rot.style.transformOrigin = "0 0";

        const vector = document.createElement("span");
        vector.setAttribute("data-vector", "");
        vector.style.position = "absolute";
        vector.style.left = "-0.5px";
        vector.style.top = "-30px";
        vector.style.width = "1px";
        vector.style.height = "21px";

        const glyph = document.createElement("span");
        glyph.setAttribute("data-glyph", "");
        glyph.style.position = "absolute";
        glyph.style.display = "block";

        rot.appendChild(vector);
        rot.appendChild(glyph);

        const tag = document.createElement("button");
        tag.type = "button";
        tag.setAttribute("data-tag", "");
        tag.setAttribute("data-testid", `unit-marker-${u.agent_id}`);
        tag.style.position = "absolute";
        tag.style.left = "16px";
        tag.style.top = "-13px";
        tag.style.display = "flex";
        tag.style.flexDirection = "column";
        tag.style.gap = "1px";
        tag.style.alignItems = "flex-start";
        tag.style.padding = "3px 7px";
        tag.style.background = "rgba(3,4,6,0.92)";
        tag.style.border = "1px solid #1A2026";
        tag.style.borderRadius = "3px";
        tag.style.cursor = "pointer";
        tag.style.textAlign = "left";
        tag.style.whiteSpace = "nowrap";

        const idRow = document.createElement("span");
        idRow.setAttribute("data-id", "");
        idRow.style.fontFamily = '"IBM Plex Mono", monospace';
        idRow.style.fontSize = "10px";
        idRow.style.letterSpacing = "0.2em";
        idRow.style.lineHeight = "1.1";

        const subRow = document.createElement("span");
        subRow.setAttribute("data-sub", "");
        subRow.style.fontFamily = '"IBM Plex Mono", monospace';
        subRow.style.fontSize = "8px";
        subRow.style.letterSpacing = "0.12em";
        subRow.style.textTransform = "uppercase";
        subRow.style.color = tokens.color.ash;
        subRow.style.lineHeight = "1.2";

        tag.appendChild(idRow);
        tag.appendChild(subRow);
        const agentId = u.agent_id;
        tag.addEventListener("click", (e) => {
          e.stopPropagation();
          onSelectUnitRef.current?.(agentId);
        });

        el.appendChild(selectRing);
        el.appendChild(radius);
        el.appendChild(sweep);
        el.appendChild(rot);
        el.appendChild(tag);

        marker = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat(ll)
          .addTo(map);
        droneMarkersRef.current[u.agent_id] = marker;
      } else {
        marker.setLngLat(ll);
      }

      const el = marker.getElement();
      const rot = el.querySelector("[data-rot]") as HTMLElement;
      const glyph = el.querySelector("[data-glyph]") as HTMLElement;
      const vector = el.querySelector("[data-vector]") as HTMLElement;
      const sweep = el.querySelector("[data-sweep]") as HTMLElement;
      const radius = el.querySelector("[data-radius]") as HTMLElement;
      const selectRing = el.querySelector("[data-select]") as HTMLElement;
      const idRow = el.querySelector("[data-id]") as HTMLElement;
      const subRow = el.querySelector("[data-sub]") as HTMLElement;

      // Glyph: redraw only when the kind/colour changes (keeps 10 Hz cheap).
      const glyphKey = `${airborne ? "air" : "dock"}:${color}`;
      if (glyph.dataset.key !== glyphKey) {
        glyph.innerHTML = airborne ? deltaGlyph(color) : dockedGlyph(color);
        glyph.style.left = airborne ? "-9px" : "-7px";
        glyph.style.top = airborne ? "-9px" : "-7px";
        glyph.dataset.key = glyphKey;
      }
      rot.style.transform = `rotate(${airborne ? u.heading_deg : 0}deg)`;
      vector.style.display = airborne ? "block" : "none";
      vector.style.background = `linear-gradient(to top, ${color}, transparent)`;
      sweep.style.display = airborne ? "block" : "none";
      sweep.style.color = color;
      radius.style.display = airborne ? "block" : "none";
      radius.style.color = color;
      selectRing.style.display = selected ? "block" : "none";

      idRow.textContent = id;
      idRow.style.color = color;
      subRow.textContent = sub;
      el.title = `${id} · ${sub}`;
    }
    for (const id of Object.keys(droneMarkersRef.current)) {
      if (!seen.has(id)) {
        droneMarkersRef.current[id].remove();
        delete droneMarkersRef.current[id];
      }
    }
  }, [units, selectedAgentId]);

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
      const auto = findLatestAutonomyCommand(cmds, a.id);
      const calloutText = anomalyCallout(a, auto);
      const color = auto ? tokens.color.orbitalBlue : tokens.color.launchAmber;
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
        inner.style.background = tokens.color.launchAmber;

        const ring = document.createElement("span");
        ring.style.position = "absolute";
        ring.style.left = "-12px";
        ring.style.top = "-12px";
        ring.style.width = "24px";
        ring.style.height = "24px";
        ring.style.borderRadius = "50%";
        ring.style.border = `1px solid ${tokens.color.launchAmber}`;
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
        callout.style.position = "absolute";
        callout.style.left = "34px";
        callout.style.top = "-8px";
        callout.style.display = "inline-flex";
        callout.style.alignItems = "center";
        callout.style.gap = "5px";
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

        // Per-source provenance glyph — inherits the callout color via
        // `currentColor`. Empty when the anomaly carries no evidence yet.
        const glyph = document.createElement("span");
        glyph.setAttribute("data-glyph", "");
        glyph.style.display = "inline-flex";
        glyph.style.flex = "0 0 auto";
        glyph.innerHTML = a.evidence ? sourceGlyphMarkup(a.evidence.source) : "";

        const calloutTextSpan = document.createElement("span");
        calloutTextSpan.setAttribute("data-callout-text", "");
        calloutTextSpan.textContent = calloutText;

        callout.appendChild(glyph);
        callout.appendChild(calloutTextSpan);
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
        const calloutTextSpan = el.querySelector(
          "[data-callout-text]"
        ) as HTMLElement | null;
        const glyph = el.querySelector("[data-glyph]") as HTMLElement | null;
        const leader = el.querySelector("[data-leader]") as HTMLElement | null;
        if (calloutTextSpan) calloutTextSpan.textContent = calloutText;
        if (glyph) {
          glyph.innerHTML = a.evidence ? sourceGlyphMarkup(a.evidence.source) : "";
        }
        if (callout) {
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
      {/* Map container — inline style beats maplibre-gl.css's
          `.maplibregl-map { position: relative; }` rule that otherwise
          overrides Tailwind's `absolute` class (equal specificity, but
          maplibre is loaded later in the cascade). Without this the
          canvas collapses to ~78 px and tiles only render in a thin
          strip at the top of the map. */}
      <div ref={containerRef} className="absolute inset-0" style={{ position: "absolute", inset: 0 }} />

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
        <g fill="none" stroke="#3F4348" strokeWidth="0.6" strokeDasharray="2 4" opacity="0.5">
          <circle cx="400" cy="250" r="160" />
        </g>
      </svg>

      <MapLegend />
      <BasemapSwitch mode={basemapMode} onChange={setBasemapMode} />
      <CornerStamps units={units} />
    </div>
  );
}

// Compact key so the operational surface explains itself at a glance — the
// glyphs mirror the live markers, the colour line maps accent → state.
function MapLegend() {
  return (
    <div className="pointer-events-none absolute left-4 top-4 flex flex-col gap-1.5 border border-gunmetal rounded-card bg-obsidian/85 px-3 py-2.5">
      <div className="eyebrow-mono text-ash">key</div>
      <LegendRow
        glyph={
          <svg width="14" height="14" viewBox="0 0 18 18">
            <path d="M9 1.5 L15.5 16 L9 12 L2.5 16 Z" fill="#B8FF66" stroke="#030406" strokeWidth="0.85" strokeLinejoin="round" />
          </svg>
        }
        label="unit · airborne"
      />
      <LegendRow
        glyph={
          <svg width="13" height="13" viewBox="0 0 14 14">
            <rect x="2.25" y="2.25" width="9.5" height="9.5" rx="1.5" stroke="#EEF0F3" strokeWidth="1.25" fill="none" />
            <circle cx="7" cy="7" r="1.4" fill="#EEF0F3" />
          </svg>
        }
        label="unit · docked"
      />
      <LegendRow
        glyph={
          <svg width="14" height="14" viewBox="0 0 14 14">
            <circle cx="7" cy="7" r="5.5" stroke="#FFB45C" strokeWidth="1" fill="none" />
            <circle cx="7" cy="7" r="1.6" fill="#FFB45C" />
          </svg>
        }
        label="anomaly · verify"
      />
      <div className="mt-0.5 flex items-center gap-2 eyebrow-mono" style={{ fontSize: 8 }}>
        <span className="text-orbital-blue">verify</span>
        <span className="text-signal-green">online</span>
        <span className="text-launch-amber">attention</span>
      </div>
    </div>
  );
}

function LegendRow({ glyph, label }: { glyph: ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="inline-flex w-[14px] justify-center">{glyph}</span>
      <span className="eyebrow-mono text-muted-silver" style={{ fontSize: 9 }}>
        {label}
      </span>
    </div>
  );
}

// Basemap selector — lets the operator put the real satellite imagery under
// the tactical overlay, or keep the dark tactical map. Monochrome chrome;
// Orbital Blue marks the active mode (accent reserved for state, §5.2).
export function BasemapSwitch({
  mode,
  onChange,
}: {
  mode: BasemapMode;
  onChange: (m: BasemapMode) => void;
}) {
  const options: { id: BasemapMode; label: string }[] = [
    { id: "tactical", label: "tactical" },
    { id: "satellite", label: "satellite" },
  ];
  return (
    <div className="pointer-events-auto absolute right-4 top-4 flex items-center gap-0.5 rounded-card border border-gunmetal bg-obsidian/85 p-0.5">
      {options.map((o) => {
        const active = o.id === mode;
        return (
          <button
            key={o.id}
            type="button"
            onClick={() => onChange(o.id)}
            aria-pressed={active}
            data-testid={`basemap-${o.id}`}
            className={`eyebrow-mono rounded-[3px] px-2 py-1 transition-colors duration-press ease-swarm ${
              active
                ? "bg-graphite/60 text-orbital-blue"
                : "text-muted-silver hover:text-platinum"
            }`}
            style={{ fontSize: 9 }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

function CornerStamps({ units }: { units: UnitState[] }) {
  const airborne = units.filter((u) => AIRBORNE_STATES.has(u.fsm_state));
  const maxAlt = airborne.length
    ? airborne.reduce((acc, u) => Math.max(acc, u.altitude_agl_m), 0)
    : null;
  const lat = VINEYARD_CENTER[1];
  const lon = VINEYARD_CENTER[0];
  return (
    <>
      <div className="pointer-events-none absolute right-4 top-14 eyebrow-mono mono-num text-right text-ash">
        {maxAlt != null ? `altitude · ${maxAlt.toFixed(0)} m` : "altitude · —"}
      </div>
      <div className="pointer-events-none absolute left-4 bottom-4 eyebrow-mono mono-num text-ash">
        {lat.toFixed(3)}°N · {lon.toFixed(3)}°E
      </div>
    </>
  );
}

