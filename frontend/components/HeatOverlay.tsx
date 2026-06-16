"use client";

/**
 * HeatOverlay — amber thermal mist around anomalies whose evidence carries a
 * surface-temperature signal (`evidence.metric === "temperature_c"`).
 *
 * Rendered as a single soft `circle` layer over a GeoJSON point source. The
 * radius scales by ΔT (value − baseline); the fill is launch-amber at low
 * opacity with a soft blur — a *state* cue, not chrome (radial mist is a brand
 * asset, PDF §5.2). Amber only: no red, no glassmorphism.
 *
 * The values come from SwarmOS / the honest simulator; this layer only maps
 * ΔT → radius. Every contributing anomaly is sim-modelled (`simulated: true`).
 */

import { useEffect } from "react";
import type { GeoJSONSource, Map as MaplibreMap } from "maplibre-gl";

import { useSwarm } from "@/lib/state";
import type { AnomalyView } from "@/lib/api";

const SRC_ID = "swarm-heat";
const LAYER_ID = "swarm-heat-circle";

const AMBER = "#FFB45C"; // launch-amber — escalation stays amber, never red

type Props = {
  map: MaplibreMap | null;
};

/** Anomalies that carry a usable surface-temperature signal. */
export function thermalAnomalies(anomalies: AnomalyView[]): AnomalyView[] {
  return anomalies.filter(
    (a) =>
      a.state !== "dismissed" &&
      a.state !== "marked_known" &&
      a.evidence?.metric === "temperature_c" &&
      a.evidence.value != null &&
      a.evidence.baseline != null
  );
}

export function HeatOverlay({ map }: Props) {
  const { anomalies } = useSwarm();

  // Create the source + layer once the style is ready.
  useEffect(() => {
    if (!map) return;
    const ensure = () => {
      if (!map.getSource(SRC_ID)) {
        map.addSource(SRC_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!map.getLayer(LAYER_ID)) {
        map.addLayer({
          id: LAYER_ID,
          source: SRC_ID,
          type: "circle",
          paint: {
            // Radius (screen px) scaled by ΔT: 0°C → 16px, 30°C → 48px.
            "circle-radius": [
              "interpolate",
              ["linear"],
              ["get", "dt"],
              0,
              16,
              30,
              48,
            ],
            "circle-color": AMBER,
            "circle-opacity": 0.16,
            "circle-blur": 0.85,
          },
        });
      }
    };
    if (map.isStyleLoaded()) ensure();
    else map.once("styledata", ensure);
    return () => {
      try {
        if (map.getLayer(LAYER_ID)) map.removeLayer(LAYER_ID);
        if (map.getSource(SRC_ID)) map.removeSource(SRC_ID);
      } catch {
        /* map already torn down */
      }
    };
  }, [map]);

  // Push the current thermal anomalies into the source on every change.
  useEffect(() => {
    if (!map) return;
    const features = thermalAnomalies(anomalies).map((a) => {
      const ev = a.evidence!;
      const dt = Math.max(0, (ev.value ?? 0) - (ev.baseline ?? 0));
      return {
        type: "Feature" as const,
        id: a.id,
        properties: { id: a.id, dt },
        geometry: {
          type: "Point" as const,
          coordinates: [a.geo.lon, a.geo.lat] as [number, number],
        },
      };
    });
    const apply = () => {
      const src = map.getSource(SRC_ID);
      if (src && "setData" in src) {
        (src as GeoJSONSource).setData({
          type: "FeatureCollection",
          features,
        });
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once("styledata", apply);
  }, [map, anomalies]);

  return null;
}
