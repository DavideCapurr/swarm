"use client";

/**
 * TerritoryControl — the Console viewport (DS Spread 24).
 *
 * "Never a dashboard; a viewport." The right rail is one calm QuietPanel
 * (Spread 24 canon); the SceneHeader above the map is the YC pitch
 * surface (playbook §5.4, §12.1, §15). Reads from `useSwarm()`; never
 * fetches on its own. UnitDetail swaps into the rail when a unit is
 * selected.
 */

import { useState } from "react";

import { useSwarm } from "@/lib/state";
import { HeatOverlay } from "./HeatOverlay";
import { MapView, VINEYARD_CENTER } from "./Map";
import { QuietPanel } from "./QuietPanel";
import { RouteLayer } from "./RouteLayer";
import { SceneHeader } from "./SceneHeader";
import { SectorLayer } from "./SectorLayer";
import { TacticalBasemap } from "./TacticalBasemap";
import { UnitDetail } from "./UnitDetail";

export function TerritoryControl() {
  const { units, anomalies, commands } = useSwarm();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const selectedUnit = selectedAgentId
    ? units.find((u) => u.agent_id === selectedAgentId) ?? null
    : null;

  return (
    <section className="grid grid-rows-[auto_1fr] min-h-0 flex-1">
      <SceneHeader />
      <div className="grid grid-cols-[1fr_380px] min-h-0">
        <div className="relative overflow-hidden bg-absolute-black border-r border-gunmetal">
          <MapView
            units={units}
            anomalies={anomalies}
            commands={commands}
            selectedAgentId={selectedAgentId}
            onSelectUnit={setSelectedAgentId}
          >
            {(m) => (
              <>
                {/* Tactical basemap first → lowest layers (dark grid + rings). */}
                <TacticalBasemap map={m} center={VINEYARD_CENTER} />
                {/* Heat mist sits under sectors/routes so the hairlines stay crisp. */}
                <HeatOverlay map={m} />
                <SectorLayer map={m} />
                <RouteLayer map={m} />
              </>
            )}
          </MapView>
        </div>

        <aside className="bg-obsidian border-l border-gunmetal overflow-y-auto">
          {selectedUnit ? (
            <div className="p-4">
              <UnitDetail
                unit={selectedUnit}
                onClose={() => setSelectedAgentId(null)}
              />
            </div>
          ) : (
            <QuietPanel onSelectAgent={setSelectedAgentId} />
          )}
        </aside>
      </div>
    </section>
  );
}
