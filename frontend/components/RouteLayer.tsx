"use client";

/**
 * RouteLayer — traces mission waypoints + recent observed tracks onto the map.
 *
 * Waypoints are rendered as hairline gunmetal polylines with platinum hinge
 * points; the recently observed track uses orbital-blue dashed lines to
 * distinguish "intended" from "observed". No glow, no fill.
 */

import { useEffect } from "react";
import type { Map as MaplibreMap } from "maplibre-gl";
import type { GeoJSONSource } from "maplibre-gl";

import { useSwarm } from "@/lib/state";
import type { MissionView } from "@/lib/api";

const WAYPOINTS_SRC = "swarm-routes-waypoints";
const TRACK_SRC = "swarm-routes-track";
const WAYPOINTS_LAYER = "swarm-routes-waypoints-line";
const HINGES_LAYER = "swarm-routes-waypoints-hinges";
const TRACK_LAYER = "swarm-routes-track-line";

type Props = { map: MaplibreMap | null };

export function RouteLayer({ map }: Props) {
  const { missions } = useSwarm();

  useEffect(() => {
    if (!map) return;
    const ensure = () => {
      if (!map.getSource(WAYPOINTS_SRC)) {
        map.addSource(WAYPOINTS_SRC, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!map.getSource(TRACK_SRC)) {
        map.addSource(TRACK_SRC, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });
      }
      if (!map.getLayer(WAYPOINTS_LAYER)) {
        map.addLayer({
          id: WAYPOINTS_LAYER,
          source: WAYPOINTS_SRC,
          type: "line",
          filter: ["==", ["geometry-type"], "LineString"],
          paint: {
            "line-color": "#A8AFB8",
            "line-opacity": 0.7,
            "line-width": 1,
          },
        });
      }
      if (!map.getLayer(HINGES_LAYER)) {
        map.addLayer({
          id: HINGES_LAYER,
          source: WAYPOINTS_SRC,
          type: "circle",
          filter: ["==", ["geometry-type"], "Point"],
          paint: {
            "circle-color": "#EEF0F3",
            "circle-radius": 2,
            "circle-stroke-color": "#1A2026",
            "circle-stroke-width": 1,
          },
        });
      }
      if (!map.getLayer(TRACK_LAYER)) {
        map.addLayer({
          id: TRACK_LAYER,
          source: TRACK_SRC,
          type: "line",
          paint: {
            "line-color": "#7BE7FF",
            "line-opacity": 0.8,
            "line-width": 1,
            "line-dasharray": [1, 2],
          },
        });
      }
    };
    if (map.isStyleLoaded()) ensure();
    else map.once("styledata", ensure);
    return () => {
      try {
        for (const id of [WAYPOINTS_LAYER, HINGES_LAYER, TRACK_LAYER]) {
          if (map.getLayer(id)) map.removeLayer(id);
        }
        for (const id of [WAYPOINTS_SRC, TRACK_SRC]) {
          if (map.getSource(id)) map.removeSource(id);
        }
      } catch {
        /* map torn down */
      }
    };
  }, [map]);

  useEffect(() => {
    if (!map) return;
    const wp = waypointsFeatures(missions);
    const tr = trackFeatures(missions);
    const apply = () => {
      const wpSrc = map.getSource(WAYPOINTS_SRC) as GeoJSONSource | undefined;
      const trSrc = map.getSource(TRACK_SRC) as GeoJSONSource | undefined;
      wpSrc?.setData({ type: "FeatureCollection", features: wp });
      trSrc?.setData({ type: "FeatureCollection", features: tr });
    };
    if (map.isStyleLoaded()) apply();
    else map.once("styledata", apply);
  }, [map, missions]);

  return null;
}

function waypointsFeatures(missions: MissionView[]) {
  const features: GeoJSON.Feature[] = [];
  for (const m of missions) {
    if (m.waypoints.length >= 2) {
      features.push({
        type: "Feature",
        properties: { id: m.id, kind: "waypoints" },
        geometry: {
          type: "LineString",
          coordinates: m.waypoints.map((g) => [g.lon, g.lat] as [number, number]),
        },
      });
    }
    for (const g of m.waypoints) {
      features.push({
        type: "Feature",
        properties: { id: m.id, kind: "hinge" },
        geometry: { type: "Point", coordinates: [g.lon, g.lat] },
      });
    }
  }
  return features;
}

function trackFeatures(missions: MissionView[]) {
  const features: GeoJSON.Feature[] = [];
  for (const m of missions) {
    if (m.track.length >= 2) {
      features.push({
        type: "Feature",
        properties: { id: m.id, kind: "track" },
        geometry: {
          type: "LineString",
          coordinates: m.track.map((g) => [g.lon, g.lat] as [number, number]),
        },
      });
    }
  }
  return features;
}
