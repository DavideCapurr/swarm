"use client";

/**
 * PhysicalCapacityPanel — the fleet as replaceable physical capacity.
 *
 * Not a fleet list. Rows answer two questions: what capacity SwarmOS can see,
 * and what it has committed. Capability labels are canonical UnitState truth;
 * this surface never infers them from model names, roles or mission state.
 */

import type { CapacityRow, ObjectiveAuthority } from "@/lib/authority";
import {
  capabilityLabel,
  capacitySummary,
  capacitySummaryLabel,
  groupLabel,
  missionLabel,
  phaseLabel,
  roleLabel,
  CAPACITY_SUMMARY_THRESHOLD,
} from "@/lib/authority";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";

export const CAPACITY_WIDTH = 338;
const ROSTER_MAX_H = 320;

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

const BUCKET_LABEL: Record<CapacityRow["commitment"], string> = {
  ASSIGNED: "committed",
  COMMITTED: "committed",
  SPARE: "reserve",
  UNAVAILABLE: "unavailable",
};

function capabilitySummary(row: CapacityRow): string {
  if (row.capabilities.length === 0) return "—";
  return row.capabilities.map(capabilityLabel).join(" · ");
}

export function PhysicalCapacityPanel({
  capacity,
  selected,
  objectives,
  namedAgents,
  onSelect,
}: {
  capacity: CapacityRow[];
  selected: string | null;
  objectives: ObjectiveAuthority[];
  namedAgents: ReadonlySet<string>;
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

  const sorted = capacity
    .slice()
    .sort(
      (a, b) =>
        ORDER[a.commitment] - ORDER[b.commitment] || a.agentId.localeCompare(b.agentId)
    );

  const named = sorted.filter(
    (row) => row.commitment === "UNAVAILABLE" || namedAgents.has(row.agentId)
  );
  const rest = sorted.filter((row) => !named.includes(row));

  const buckets: { commitment: CapacityRow["commitment"]; rows: CapacityRow[] }[] = [];
  for (const row of rest) {
    const bucket = buckets.find((b) => b.commitment === row.commitment);
    if (bucket) bucket.rows.push(row);
    else buckets.push({ commitment: row.commitment, rows: [row] });
  }

  const summarised = buckets.filter((b) => b.rows.length > CAPACITY_SUMMARY_THRESHOLD);
  const rows = [
    ...named,
    ...buckets.filter((b) => !summarised.includes(b)).flatMap((b) => b.rows),
  ].sort(
    (a, b) => ORDER[a.commitment] - ORDER[b.commitment] || a.agentId.localeCompare(b.agentId)
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

      {rows.length === 0 && summarised.length === 0 ? (
        <div className="px-3 py-5">
          <Mono size={10} tone="ash">WAITING FOR FLEET STATE</Mono>
        </div>
      ) : null}

      <div className="flex flex-col overflow-y-auto" style={{ maxHeight: ROSTER_MAX_H }}>
        {rows.map((row, i) => (
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

            <span className="min-w-0 flex-1 truncate font-grotesk text-[9.5px] font-medium uppercase leading-none tracking-[0.06em] text-muted-silver">
              {row.role ? roleLabel(row.role) : capabilitySummary(row)}
            </span>

            <Mono
              size={9.5}
              tone={COMMITMENT_TONE[row.commitment]}
              className="uppercase !tracking-[0.06em]"
            >
              {row.commitment}
            </Mono>

            <Mono size={10} tone="ash" className="w-[30px] text-right">
              {row.batteryPct.toFixed(0)}%
            </Mono>
          </button>
        ))}
      </div>

      {summarised.map((bucket, i) => {
        const summary = capacitySummary(bucket.rows);
        if (!summary) return null;
        return (
          <div
            key={bucket.commitment}
            className="flex items-center gap-[10px] px-3 py-[9px]"
            style={{
              borderTop:
                rows.length === 0 && i === 0 ? undefined : `1px solid ${HAIRLINE}`,
            }}
            data-testid={`capacity-summary-${bucket.commitment.toLowerCase()}`}
          >
            <Dot tone={COMMITMENT_TONE[bucket.commitment]} />
            <Label>{BUCKET_LABEL[bucket.commitment]}</Label>
            <Mono size={11} tone="silver" className="ml-auto">
              {capacitySummaryLabel(summary)}
            </Mono>
          </div>
        );
      })}
    </Surface>
  );
}

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
            className="font-console-mono text-[9px] leading-none tracking-[0.04em] text-ash"
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
          <Mono size={10} tone={COMMITMENT_TONE[row.commitment]}>{row.commitment}</Mono>
        </div>
      </div>

      {row.role ? (
        <div className="px-3 pb-[11px]">
          <span className="font-grotesk text-[12px] font-medium uppercase leading-none tracking-[0.06em] text-orbital-blue">
            {roleLabel(row.role)}
          </span>
        </div>
      ) : null}

      <Divider />

      <div className="px-3 py-[10px]" data-testid="selected-executor-capabilities">
        <Label>capabilities</Label>
        <div className="mt-[7px] flex flex-wrap gap-x-2 gap-y-[5px]">
          {row.capabilities.length === 0 ? (
            <Mono size={10} tone="ash">NONE DECLARED</Mono>
          ) : (
            row.capabilities.map((capability) => (
              <Mono key={capability} size={10} tone="orbital">
                {capabilityLabel(capability)}
              </Mono>
            ))
          )}
        </div>
      </div>

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
              <Mono size={11} tone="ash" className="line-through">{slot.replacesAgentId}</Mono>
              <Mono size={10} tone="ash">→</Mono>
              <Mono size={12} tone="green">{row.agentId}</Mono>
            </div>
          </div>
        </>
      ) : null}

      {row.excluded ? (
        <>
          <Divider />
          <div className="flex items-baseline justify-between gap-3 px-3 py-[10px]">
            <Label tone="amber">excluded</Label>
            <Mono size={10} tone="amber">{row.excluded.reason}</Mono>
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
      <Mono size={12} tone="platinum">{value}</Mono>
    </div>
  );
}
