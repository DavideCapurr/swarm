"use client";

/**
 * PhysicalCapacityPanel — the fleet as replaceable capacity.
 *
 * Not a fleet list. The distinction the product turns on is what SwarmOS has
 * committed and what it is holding in reserve, so the rows are ordered by
 * commitment and the role is the second thing on every line. Battery is the one
 * number kept, because it is the reminder that these are physical machines with
 * a finite budget; altitude, velocity, heading and link belong to a selected
 * executor, not to a standing list.
 *
 * Selecting an executor transforms this same surface rather than opening a
 * second card. One panel, two states — the composition never changes shape.
 */

import type { CapacityRow } from "@/lib/authority";
import { missionLabel, groupLabel, phaseLabel, roleLabel } from "@/lib/authority";
import type { ObjectiveAuthority } from "@/lib/authority";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";

export const CAPACITY_WIDTH = 338;

const ORDER: Record<CapacityRow["commitment"], number> = {
  ASSIGNED: 0,
  COMMITTED: 1,
  SPARE: 2,
  UNAVAILABLE: 3,
};

const COMMITMENT_TONE = {
  ASSIGNED: "orbital",
  COMMITTED: "silver",
  SPARE: "ash",
  UNAVAILABLE: "amber",
} as const;

export function PhysicalCapacityPanel({
  capacity,
  selected,
  objectives,
  onSelect,
}: {
  capacity: CapacityRow[];
  selected: string | null;
  objectives: ObjectiveAuthority[];
  onSelect: (agentId: string | null) => void;
}) {
  const selectedRow = selected ? capacity.find((row) => row.agentId === selected) ?? null : null;

  if (selectedRow) {
    return (
      <SelectedExecutor
        row={selectedRow}
        objectives={objectives}
        onClear={() => onSelect(null)}
      />
    );
  }

  const rows = capacity
    .slice()
    .sort(
      (a, b) =>
        ORDER[a.commitment] - ORDER[b.commitment] || a.agentId.localeCompare(b.agentId)
    );

  return (
    <Surface
      data-testid="physical-capacity"
      className="pointer-events-auto flex flex-col"
      style={{ width: CAPACITY_WIDTH }}
    >
      <SurfaceHeader
        title="physical capacity"
        right={
          <Mono size={10} tone="ash">
            {String(capacity.length).padStart(2, "0")} EXECUTORS
          </Mono>
        }
      />

      {rows.length === 0 ? (
        <div className="px-3 py-5">
          <Mono size={10} tone="ash">
            WAITING FOR FLEET STATE
          </Mono>
        </div>
      ) : (
        rows.map((row, i) => (
          <button
            key={row.agentId}
            type="button"
            onClick={() => onSelect(row.agentId)}
            data-testid={`capacity-${row.agentId}`}
            className="flex items-center gap-[10px] px-3 py-[9px] text-left"
            style={{ borderTop: i === 0 ? undefined : `1px solid ${HAIRLINE}` }}
          >
            <Dot tone={COMMITMENT_TONE[row.commitment]} />

            <Mono size={12} tone={row.commitment === "UNAVAILABLE" ? "amber" : "platinum"}>
              {row.agentId}
            </Mono>

            <span className="min-w-0 flex-1 truncate font-grotesk text-[9.5px] font-medium uppercase leading-none tracking-[0.15em] text-muted-silver">
              {row.role ? roleLabel(row.role) : "—"}
            </span>

            <Mono size={9.5} tone={COMMITMENT_TONE[row.commitment]} className="uppercase">
              {row.commitment}
            </Mono>

            <Mono size={10} tone="ash" className="w-[30px] text-right">
              {row.batteryPct.toFixed(0)}%
            </Mono>
          </button>
        ))
      )}
    </Surface>
  );
}

/**
 * The selected executor.
 *
 * Answers where this machine sits in the decision, then what it is doing. Only
 * telemetry SwarmOS actually publishes appears: battery, altitude AGL, heading
 * and link quality are `UnitState` fields. Link is shown as the number the
 * runtime reports rather than a word this surface graded it into — a word would
 * be a Console-side derivation of operational state.
 */
function SelectedExecutor({
  row,
  objectives,
  onClear,
}: {
  row: CapacityRow;
  objectives: ObjectiveAuthority[];
  onClear: () => void;
}) {
  const objective = objectives.find((o) => o.key === row.objectiveKey) ?? null;
  const slot = objective?.slots.find((s) => s.agentId === row.agentId) ?? null;

  return (
    <Surface
      data-testid="selected-executor"
      className="pointer-events-auto flex flex-col"
      style={{ width: CAPACITY_WIDTH }}
    >
      <SurfaceHeader
        title="selected executor"
        right={
          <button
            type="button"
            onClick={onClear}
            className="font-mono text-[9px] uppercase leading-none tracking-[0.18em] text-ash"
          >
            close
          </button>
        }
      />

      <div className="flex items-baseline justify-between gap-3 px-3 pb-[10px] pt-[11px]">
        <Mono size={17} tone={row.commitment === "UNAVAILABLE" ? "amber" : "platinum"}>
          {row.agentId}
        </Mono>
        <div className="flex items-center gap-2">
          <Dot tone={COMMITMENT_TONE[row.commitment]} />
          <Mono size={10} tone={COMMITMENT_TONE[row.commitment]}>
            {row.commitment}
          </Mono>
        </div>
      </div>

      {row.role ? (
        <div className="px-3 pb-[11px]">
          <span className="font-grotesk text-[12px] font-medium uppercase leading-none tracking-[0.16em] text-orbital-blue">
            {roleLabel(row.role)}
          </span>
        </div>
      ) : null}

      <Divider />

      <div className="grid grid-cols-2">
        <Field label="mission" value={row.missionId ? missionLabel(row.missionId) : "—"} border />
        <Field
          label="execution group"
          value={objective?.groupId ? groupLabel(objective.groupId) : "—"}
        />
        <Field label="state" value={phaseLabel(row.phase ?? row.fsmState)} border top />
        <Field label="battery" value={`${row.batteryPct.toFixed(0)}%`} top />
        <Field label="altitude agl" value={`${row.altitudeAglM.toFixed(0)} m`} border top />
        <Field label="link quality" value={`${(row.linkQuality * 100).toFixed(0)}%`} top />
      </div>

      {slot?.replacesAgentId ? (
        <>
          <Divider />
          <div className="px-3 py-[10px]">
            <Label tone="green">central replacement</Label>
            <div className="mt-[7px] flex items-baseline gap-2">
              <Mono size={11} tone="ash" className="line-through">
                {slot.replacesAgentId}
              </Mono>
              <Mono size={10} tone="ash">
                →
              </Mono>
              <Mono size={12} tone="green">
                {row.agentId}
              </Mono>
            </div>
          </div>
        </>
      ) : null}

      {row.excluded ? (
        <>
          <Divider />
          <div className="flex items-baseline justify-between gap-3 px-3 py-[10px]">
            <Label tone="amber">excluded</Label>
            <Mono size={10} tone="amber">
              {row.excluded.reason}
            </Mono>
          </div>
        </>
      ) : null}
    </Surface>
  );
}

function Field({
  label,
  value,
  border = false,
  top = false,
}: {
  label: string;
  value: string;
  border?: boolean;
  top?: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-[7px] px-3 py-[10px]"
      style={{
        borderRight: border ? `1px solid ${HAIRLINE}` : undefined,
        borderTop: top ? `1px solid ${HAIRLINE}` : undefined,
      }}
    >
      <Label>{label}</Label>
      <Mono size={12} tone="platinum">
        {value}
      </Mono>
    </div>
  );
}
