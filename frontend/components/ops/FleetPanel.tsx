"use client";

/**
 * FleetPanel — fleet state as SwarmOS sees it, with mission ownership on the
 * same row as the agent.
 *
 * The exclusion line is the point of this panel during the second objective:
 * the agent that already owns a mission is shown, on its own row, as excluded
 * from the new one, with the exact active mission id that caused it.
 */

import { shortId, type FleetRow } from "@/lib/mission-story";

import { BatteryBar, Panel, Value } from "./primitives";

export function FleetPanel({
  rows,
  className = "",
}: {
  rows: FleetRow[];
  className?: string;
}) {
  const owning = rows.filter((row) => row.missionId).length;
  return (
    <Panel
      className={className}
      title="Fleet"
      right={
        <span className="font-mono text-[12px] tracking-[0.16em] text-ash">
          {String(owning).padStart(2, "0")} / {String(rows.length).padStart(2, "0")} OWNING MISSION
        </span>
      }
      bodyClassName="overflow-y-auto"
    >
      {rows.length === 0 ? (
        <div className="px-3 py-5">
          <span className="font-mono text-[13px] text-ash">WAITING FOR FLEET STATE</span>
        </div>
      ) : (
        rows.map((row) => (
          <div
            key={row.agentId}
            data-testid={`fleet-${row.agentId}`}
            className={`border-b border-gunmetal border-l-2 px-3 py-3 ${
              row.missionId ? "border-l-orbital-blue" : "border-l-transparent"
            }`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <Value size="md">{row.agentId}</Value>
              <span className="flex items-center gap-2">
                <BatteryBar pct={row.batteryPct} />
                <Value size="sm" tone="silver">
                  {row.batteryPct.toFixed(0)}%
                </Value>
              </span>
            </div>

            <div className="mt-[6px] flex items-baseline justify-between gap-3">
              <span
                className={`font-mono text-[15px] uppercase tracking-[0.14em] ${
                  row.missionId ? "text-orbital-blue" : "text-muted-silver"
                }`}
              >
                {row.fsmState}
              </span>
              <span className="font-mono text-[13px] tracking-[0.1em] text-ash">
                {row.altitudeAglM > 1 ? `${row.altitudeAglM.toFixed(0)} m AGL · ` : ""}
                link {(row.linkQuality * 100).toFixed(0)}%
              </span>
            </div>

            {/* One line per fact, each truncating on its own. Packing objective,
                mission id and step into a single wrapping line put the wrapped
                tail on top of the row beneath it. */}
            <div className="mt-[6px] font-mono text-[13px] leading-5 tracking-[0.08em]">
              {row.missionId ? (
                <>
                  <div className="truncate text-ash">
                    owns <span className="text-platinum">{row.objectiveLabel}</span>
                    {" · mission "}
                    <span className="text-muted-silver">{shortId(row.missionId)}</span>
                  </div>
                  {row.step ? (
                    <div className="truncate text-ash">step {row.step}</div>
                  ) : null}
                </>
              ) : (
                <span className="text-ash">no mission · available</span>
              )}
            </div>

            {row.role ? (
              <div className="mt-[4px] truncate font-mono text-[12px] tracking-[0.12em] text-ash">
                role <span className="text-muted-silver">{row.role.replaceAll("_", " ")}</span>
              </div>
            ) : null}

            {/* Exclusion is a real decision state, so it keeps the amber — but
                only on the verdict. The reason and the mission id behind it are
                explanation, and explanation in escalation colour is why nothing
                on this surface used to stand out. */}
            {row.excludedFrom ? (
              <div
                data-testid={`fleet-excluded-${row.agentId}`}
                className="mt-2 border-l-2 border-launch-amber bg-launch-amber/[0.05] px-2 py-2 font-mono tracking-[0.1em]"
              >
                <div className="truncate text-[15px] leading-5">
                  <span className="font-medium text-launch-amber">EXCLUDED</span>
                  <span className="text-muted-silver">
                    {` FROM ${row.excludedFrom.label} · ${row.excludedFrom.reason}`}
                  </span>
                </div>
                {row.excludedFrom.activeMissionId ? (
                  <div className="mt-[2px] truncate text-[13px] leading-5 text-ash">
                    already holds mission {shortId(row.excludedFrom.activeMissionId)}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))
      )}
    </Panel>
  );
}
