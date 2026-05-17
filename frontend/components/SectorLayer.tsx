"use client";

/**
 * SectorLayer — overlays sector polygons + risk-band color onto the map.
 *
 * Rendered as a `maplibre-gl` source/layer pair. No fill — only a hairline
 * outline with band-tinted stroke, plus a tiny mono label at the centroid.
 * Anomaly sectors get a pulsing breath outline.
 */

import { useEffect, useRef } from "react";
import type { Map as MaplibreMap } from "maplibre-gl";
import maplibregl from "maplibre-gl";

import { useSwarm } from "@/lib/state";
import type { Sector } from "@/lib/api";

const SRC_ID = "swarm-sectors";
const LAYER_LINE = "swarm-sectors-line";
const LAYER_LABEL = "swarm-sectors-label";

const BAND_COLOR: Record<"low" | "elevated" | "high", string> = {
  low: "#1A2026", // gunmetal — quiet, hairline only
  elevated: "#FFB45C", // launch-amber
  high: "#FFB45C", // amber stays — no red
};

const STATE_OPACITY: Record<Sector["state"], number> = {
  idle: 0.5,
  covered: 0.75,
  stale: 0.55,
  blind: 0.4,
  anomaly: 0.95,
};

type Props = {
  map: MaplibreMap | null;
};

export function SectorLayer({ map }: Props) {
  const { sectors } = useSwarm();
  const labelMarkersRef = useRef<Record<string, maplibregl.Marker>>({});

  useEffect(() => {
    if (!map) return;
    const ensure = () => {
      if (!map.getSource(SRC_ID)) {
        map.addSource(SRC_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!map.getLayer(LAYER_LINE)) {
        map.addLayer({
          id: LAYER_LINE,
          source: SRC_ID,
          type: "line",
          paint: {
            "line-color": ["get", "stroke"],
            "line-opacity": ["get", "opacity"],
            "line-width": 1,
            "line-dasharray": [2, 2],
          },
        });
      }
    };
    if (map.isStyleLoaded()) {
      ensure();
    } else {
      map.once("styledata", ensure);
    }
    return () => {
      try {
        if (map.getLayer(LAYER_LINE)) map.removeLayer(LAYER_LINE);
        if (map.getLayer(LAYER_LABEL)) map.removeLayer(LAYER_LABEL);
        if (map.getSource(SRC_ID)) map.removeSource(SRC_ID);
      } catch {
        /* map already torn down */
      }
    };
  }, [map]);

  useEffect(() => {
    if (!map) return;
    const features = sectors.map((s) => ({
      type: "Feature" as const,
      id: s.id,
      properties: {
        id: s.id,
        label: s.label,
        state: s.state,
        stroke: BAND_COLOR[s.risk_band],
        opacity: STATE_OPACITY[s.state],
      },
      geometry: {
        type: "Polygon" as const,
        coordinates: [s.polygon.map((p) => [p.lon, p.lat] as [number, number])],
      },
    }));

    const apply = () => {
      const src = map.getSource(SRC_ID);
      if (src && "setData" in src) {
        (src as maplibregl.GeoJSONSource).setData({
          type: "FeatureCollection",
          features,
        });
      }
    };
    if (map.isStyleLoaded()) {
      apply();
    } else {
      map.once("styledata", apply);
    }

    const labels = labelMarkersRef.current;
    const seen = new Set<string>();
    for (const s of sectors) {
      seen.add(s.id);
      const existing = labels[s.id];
      const ll: [number, number] = [s.centroid.lon, s.centroid.lat];
      if (existing) {
        existing.setLngLat(ll);
        const el = existing.getElement();
        const lbl = el.querySelector("[data-label]") as HTMLElement | null;
        if (lbl) lbl.textContent = `${s.label} · ${s.state}`;
      } else {
        const el = document.createElement("div");
        el.style.fontFamily = '"IBM Plex Mono", monospace';
        el.style.fontSize = "9px";
        el.style.letterSpacing = "0.22em";
        el.style.textTransform = "uppercase";
        el.style.color = "#A8AFB8";
        el.style.padding = "2px 5px";
        el.style.background = "rgba(11,14,17,0.7)";
        el.style.border = "1px solid #1A2026";
        el.style.borderRadius = "2px";
        const inner = document.createElement("span");
        inner.setAttribute("data-label", "");
        inner.textContent = `${s.label} · ${s.state}`;
        el.appendChild(inner);
        labels[s.id] = new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat(ll)
          .addTo(map);
      }
    }
    for (const id of Object.keys(labels)) {
      if (!seen.has(id)) {
        labels[id].remove();
        delete labels[id];
      }
    }
  }, [map, sectors]);

  // Cleanup label markers when unmounted.
  useEffect(() => {
    const labels = labelMarkersRef.current;
    return () => {
      for (const id of Object.keys(labels)) {
        labels[id].remove();
        delete labels[id];
      }
    };
  }, []);

  return null;
}
