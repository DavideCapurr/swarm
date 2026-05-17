"use client";

/**
 * TerritoryControl — the Console's main viewport (PDF §5 / spread 24).
 *
 * Lifted from the original `app/page.tsx` (314 LOC) into the (console) shell.
 * Reads all state from `useSwarm()`; never fetches on its own. Map gets the
 * Sector and Route overlays from Phase 1's projection. The right column hosts
 * the mode-ordered `RightRail` plus a fixed `ActionRail` and a unit list.
 */

import { useState } from "react";

import { useSwarm } from "@/lib/state";
import { describeMode } from "@/lib/derive";
import { ActionRail } from "./ActionRail";
import { CommandTimeline } from "./CommandTimeline";
import { EventFeed } from "./EventFeed";
import { FleetGrid } from "./FleetGrid";
import { MapView } from "./Map";
import { RightRail } from "./RightRail";
import { RouteLayer } from "./RouteLayer";
import { SectorLayer } from "./SectorLayer";
import { UnitDetail } from "./UnitDetail";

export function TerritoryControl() {
  const { units, anomalies, events, sectors, mode, awareness, session } = useSwarm();
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const selectedUnit = selectedAgentId ? units.find((u) => u.agent_id === selectedAgentId) ?? null : null;
  const dockedCount = units.filter((u) => u.fsm_state === "DOCKED").length;
  const airborneCount = units.filter((u) =>
    (
      [
        "TAKEOFF",
        "EN_ROUTE",
        "ON_STATION",
        "RTL",
        "LANDING",
        "DOCKING",
      ] as const
    ).includes(u.fsm_state as never)
  ).length;
  const siteLabel = session?.site_id ?? "vineyard-01";

  return (
    <section className="grid grid-rows-[1fr_220px] min-h-0 flex-1">
      <div className="grid grid-cols-[1fr_380px] min-h-0">
        <div className="relative overflow-hidden bg-absolute-black border-r border-gunmetal">
          <MapView units={units} anomalies={anomalies}>
            {(m) => (
              <>
                <SectorLayer map={m} />
                <RouteLayer map={m} />
              </>
            )}
          </MapView>
          {/* Map overlays — aggregate stats top-left + intent line bottom-left. */}
          <div className="absolute left-4 top-4 flex flex-col gap-1 eyebrow-mono">
            <span>sector · {siteLabel} · langhe</span>
            <span className="mono-num text-platinum text-ui mt-2">
              {String(dockedCount).padStart(3, "0")} docked ·{" "}
              {String(airborneCount).padStart(3, "0")} airborne
            </span>
            <span className="mono-num text-platinum text-ui">
              {String(Math.round(awareness.score)).padStart(3, "0")} % awareness ·{" "}
              {sectors.length} sectors
            </span>
          </div>
          <div className="absolute left-4 bottom-12 eyebrow-mono">
            <span className="text-platinum">{describeMode(mode)}</span>
          </div>
        </div>

        <aside className="bg-obsidian overflow-y-auto flex flex-col gap-3 border-l border-gunmetal">
          {selectedUnit ? (
            <div className="p-4">
              <UnitDetail unit={selectedUnit} onClose={() => setSelectedAgentId(null)} />
            </div>
          ) : (
            <>
              <div className="p-4 pb-0">
                <RightRail />
              </div>
              <div className="px-4">
                <ActionRail selectedAgentId={selectedAgentId} />
              </div>
              <div className="px-4">
                <CommandTimeline />
              </div>
              <div className="px-4 pb-4">
                <FleetGrid
                  units={units}
                  anomalies={anomalies}
                  onSelect={(id) => setSelectedAgentId(id)}
                />
              </div>
            </>
          )}
        </aside>
      </div>

      <footer className="bg-obsidian border-t border-gunmetal p-4 overflow-hidden">
        <EventFeed events={events} />
      </footer>
    </section>
  );
}
