"use client";

/**
 * TacticalBasemap — SWARM's self-contained dark basemap.
 *
 * No third-party raster tiles: the surface is rendered from procedural
 * geometry (`lib/tactical.ts`) so it is guaranteed dark, deterministic, and
 * network-free (design system §5.2 — no light chrome, no decorative anything).
 * Drawn as the lowest map layers so sectors, routes, heat, and unit markers
 * stack on top. Monochrome only — gunmetal graticule, ash range rings — with
 * no accent colour (accent is reserved for live state).
 */

import { useEffect } from "react";
import type { Map as MaplibreMap } from "maplibre-gl";
import maplibregl from "maplibre-gl";

import { buildTactical, type LngLat } from "@/lib/tactical";

const SRC = {
  grid: "swarm-tac-grid",
  coarse: "swarm-tac-coarse",
  rings: "swarm-tac-rings",
  parcel: "swarm-tac-parcel",
  axes: "swarm-tac-axes",
} as const;

type Props = {
  map: MaplibreMap | null;
  center: LngLat;
};

export function TacticalBasemap({ map, center }: Props) {
  useEffect(() => {
    if (!map) return;
    const geo = buildTactical(center);

    const ensure = () => {
      const addSource = (id: string, data: GeoJSON.FeatureCollection) => {
        if (!map.getSource(id)) map.addSource(id, { type: "geojson", data });
      };
      addSource(SRC.grid, geo.grid);
      addSource(SRC.coarse, geo.coarse);
      addSource(SRC.rings, geo.rings);
      addSource(SRC.parcel, geo.parcel);
      addSource(SRC.axes, geo.axes);

      // Parcel fill first (lowest), then graticule, rings, axes.
      if (!map.getLayer("swarm-tac-parcel-fill")) {
        map.addLayer({
          id: "swarm-tac-parcel-fill",
          source: SRC.parcel,
          type: "fill",
          paint: { "fill-color": "#0B0E11", "fill-opacity": 0.55 },
        });
      }
      if (!map.getLayer("swarm-tac-grid-line")) {
        map.addLayer({
          id: "swarm-tac-grid-line",
          source: SRC.grid,
          type: "line",
          paint: { "line-color": "#11161B", "line-width": 1 },
        });
      }
      if (!map.getLayer("swarm-tac-coarse-line")) {
        map.addLayer({
          id: "swarm-tac-coarse-line",
          source: SRC.coarse,
          type: "line",
          paint: { "line-color": "#1A2026", "line-width": 1 },
        });
      }
      if (!map.getLayer("swarm-tac-rings-line")) {
        map.addLayer({
          id: "swarm-tac-rings-line",
          source: SRC.rings,
          type: "line",
          paint: {
            "line-color": "#2A3138",
            "line-width": 1,
            "line-dasharray": [2, 4],
            "line-opacity": 0.7,
          },
        });
      }
      if (!map.getLayer("swarm-tac-axes-line")) {
        map.addLayer({
          id: "swarm-tac-axes-line",
          source: SRC.axes,
          type: "line",
          paint: { "line-color": "#1A2026", "line-width": 1, "line-opacity": 0.8 },
        });
      }
      if (!map.getLayer("swarm-tac-parcel-line")) {
        map.addLayer({
          id: "swarm-tac-parcel-line",
          source: SRC.parcel,
          type: "line",
          paint: {
            "line-color": "#3F4348",
            "line-width": 1,
            "line-dasharray": [4, 3],
          },
        });
      }
    };

    if (map.isStyleLoaded()) ensure();
    else map.once("styledata", ensure);

    // Range-ring distance labels — tiny mono Points rendered as DOM markers so
    // they read crisply without bundling a glyph stack.
    const labelMarkers: maplibregl.Marker[] = [];
    for (const f of geo.ringLabels.features) {
      const el = document.createElement("div");
      el.textContent = (f.properties?.label as string) ?? "";
      el.style.fontFamily = '"IBM Plex Mono", monospace';
      el.style.fontSize = "8px";
      el.style.letterSpacing = "0.18em";
      el.style.color = "#3F4348";
      el.style.background = "transparent";
      el.style.transform = "translateY(-6px)";
      const [lon, lat] = (f.geometry as GeoJSON.Point).coordinates as [number, number];
      labelMarkers.push(
        new maplibregl.Marker({ element: el, anchor: "center" })
          .setLngLat([lon, lat])
          .addTo(map)
      );
    }

    return () => {
      for (const m of labelMarkers) m.remove();
      try {
        for (const id of [
          "swarm-tac-parcel-line",
          "swarm-tac-axes-line",
          "swarm-tac-rings-line",
          "swarm-tac-coarse-line",
          "swarm-tac-grid-line",
          "swarm-tac-parcel-fill",
        ]) {
          if (map.getLayer(id)) map.removeLayer(id);
        }
        for (const id of Object.values(SRC)) {
          if (map.getSource(id)) map.removeSource(id);
        }
      } catch {
        /* map already torn down */
      }
    };
  }, [map, center]);

  return null;
}
