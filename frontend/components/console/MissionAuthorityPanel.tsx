"use client";

/**
 * MissionAuthorityPanel — what SwarmOS decided, and what it is holding.
 *
 * This is the panel the product lives in. A conventional fleet console makes
 * the aircraft the hero; here the hero is the decision loop, so the reading
 * order is fixed and deliberate:
 *
 *   objective → required capabilities → ownership → composition → executors
 *             → spare → evidence
 *
 * Every capability shown here is server truth. The Console formats labels; it
 * never derives a requirement or decides that an executor is eligible.
 */

import type {
  CapacityRow,
  CompositionSlot,
  ObjectiveAuthority,
  SwarmComposition,
} from "@/lib/authority";
import {
  capabilityLabel,
  capacitySummary,
  capacitySummaryLabel,
  compositionDigest,
  compositionDigestLabel,
  groupLabel,
  phaseLabel,
  roleLabel,
  CAPACITY_SUMMARY_THRESHOLD,
} from "@/lib/authority";
import type { PayloadChannel } from "@/lib/mission-story";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";
import type { AdaptationBeat } from "./useAdaptation";

export const AUTHORITY_WIDTH = 336;

const STATE_TONE = {
  COMPOSING: "orbital",
  EXECUTING: "orbital",
  ADAPTING: "amber",
  VERIFIED: "green",
  FAILED: "amber",
} as const;

export function MissionAuthorityPanel({
  objectives,
  focused,
  beat,
  capacity,
  channels,
  onSelectObjective,
}: {
  objectives: ObjectiveAuthority[];
  focused: ObjectiveAuthority | null;
  beat: AdaptationBeat;
  capacity: CapacityRow[];
  channels: PayloadChannel[];
  onSelectObjective: (key: string) => void;
}) {
  const spare = capacity.filter((row) => row.commitment === "SPARE");
  const spareAggregate =
    spare.length > CAPACITY_SUMMARY_THRESHOLD ? capacitySummary(spare) : null;
  const excluded = capacity.filter((row) => row.excluded && row.commitment !== "SPARE");

  return (
    <Surface
      data-testid="mission-authority"
      data-beat={beat.phase}
      className="pointer-events-auto flex flex-col"
      style={{ width: AUTHORITY_WIDTH }}
    >
      <SurfaceHeader title="SwarmOS" sub="mission authority" />

      {!focused ? (
        <div className="px-3 py-6">
          <Mono size={11} tone="ash">NO OBJECTIVE HELD</Mono>
          <div className="mt-2">
            <Mono size={10} tone="ash">AWAITING ALLOCATOR FRAME</Mono>
          </div>
        </div>
      ) : (
        <>
          {objectives.length > 1 ? (
            <ObjectiveSwitch
              objectives={objectives}
              focusKey={focused.key}
              onSelect={onSelectObjective}
            />
          ) : null}

          <ObjectiveIdentity objective={focused} />
          <RequirementStrip objective={focused} />
          <OwnershipStamp objective={focused} />
          <Composition objective={focused} beat={beat} capacity={capacity} />

          <Divider />

          <div className="flex items-start justify-between gap-3 px-3 py-[10px]">
            <Label>spare capacity</Label>
            <div className="flex flex-col items-end gap-[6px]">
              {spare.length === 0 ? (
                <Mono size={11} tone="ash">NONE</Mono>
              ) : spareAggregate ? (
                <Mono size={11} tone="silver" data-testid="spare-summary">
                  {capacitySummaryLabel(spareAggregate)}
                </Mono>
              ) : (
                spare.map((row) => (
                  <div key={row.agentId} className="flex items-center gap-2">
                    <Mono size={12} tone="silver">{row.agentId}</Mono>
                    <Mono size={10} tone="ash">{row.batteryPct.toFixed(0)}%</Mono>
                  </div>
                ))
              )}
            </div>
          </div>

          {excluded.length > 0 ? (
            <>
              <Divider />
              <div className="px-3 py-[10px]" data-testid="capability-exclusions">
                <Label tone="amber">excluded from this objective</Label>
                <div className="mt-[7px] flex flex-col gap-[8px]">
                  {excluded.map((row) => (
                    <div key={row.agentId} className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <Mono size={12} tone="silver">{row.agentId}</Mono>
                        {row.capabilities.length > 0 ? (
                          <div className="mt-[4px] truncate">
                            <Mono size={8.5} tone="ash">
                              {row.capabilities.map(capabilityLabel).join(" · ")}
                            </Mono>
                          </div>
                        ) : null}
                      </div>
                      <div className="flex flex-col items-end gap-[4px]">
                        <Mono size={10} tone="amber">{row.excluded?.reason}</Mono>
                        {row.excluded?.activeMissionId ? (
                          <Mono size={9} tone="ash">
                            M-{row.excluded.activeMissionId.slice(0, 8)}
                          </Mono>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}

          {channels.some((channel) => channel.ts) ? (
            <>
              <Divider />
              <div className="px-3 pb-[10px] pt-[10px]">
                <Label>bounded response</Label>
                <div className="mt-[8px] flex flex-col gap-[7px]">
                  {channels.map((channel) => (
                    <div
                      key={channel.channel}
                      className="flex items-baseline justify-between gap-3"
                    >
                      <div className="flex items-baseline gap-2">
                        <Mono size={10} tone="ash">{channel.channel}</Mono>
                        <Mono
                          size={11}
                          tone={channel.tier === "simulated" ? "amber" : "silver"}
                        >
                          {channel.state}
                        </Mono>
                      </div>
                      <div className="flex items-center gap-[6px]">
                        <Dot tone={channel.tier === "verified" ? "green" : "amber"} />
                        <Mono
                          size={9.5}
                          tone={channel.tier === "verified" ? "green" : "amber"}
                        >
                          {channel.proof}
                        </Mono>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : null}
        </>
      )}
    </Surface>
  );
}

function ObjectiveSwitch({
  objectives,
  focusKey,
  onSelect,
}: {
  objectives: ObjectiveAuthority[];
  focusKey: string;
  onSelect: (key: string) => void;
}) {
  return (
    <div
      className="flex items-stretch"
      style={{ borderBottom: `1px solid ${HAIRLINE}` }}
      data-testid="objective-switch"
    >
      {objectives.map((objective) => {
        const active = objective.key === focusKey;
        return (
          <button
            key={objective.key}
            type="button"
            onClick={() => onSelect(objective.key)}
            className="flex flex-1 items-center gap-2 px-3 py-[9px] text-left"
            style={{
              background: active ? "rgba(19, 25, 32, 0.72)" : "transparent",
              opacity: active ? 1 : 0.5,
            }}
          >
            <Dot tone={objective.active ? (active ? "orbital" : "silver") : "green"} />
            <Mono size={10} tone={active ? "platinum" : "silver"}>
              {String(objective.index).padStart(2, "0")}
            </Mono>
            <Mono size={10} tone="ash" className="truncate">{objective.kind}</Mono>
          </button>
        );
      })}
    </div>
  );
}

function RequirementStrip({ objective }: { objective: ObjectiveAuthority }) {
  return (
    <div
      className="px-3 py-[10px]"
      style={{ borderTop: `1px solid ${HAIRLINE}`, borderBottom: `1px solid ${HAIRLINE}` }}
      data-testid="objective-requirements"
    >
      <div className="flex items-start justify-between gap-3">
        <Label>requires</Label>
        {objective.requiredCapabilities.length === 0 ? (
          <Mono size={9.5} tone="ash">NO EXPLICIT CAPABILITY</Mono>
        ) : (
          <div className="flex max-w-[220px] flex-wrap justify-end gap-x-2 gap-y-[5px]">
            {objective.requiredCapabilities.map((capability) => (
              <Mono key={capability} size={9.5} tone="orbital">
                {capabilityLabel(capability)}
              </Mono>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function OwnershipStamp({ objective }: { objective: ObjectiveAuthority }) {
  return (
    <div
      className="flex items-center gap-[9px] px-3 py-[9px]"
      style={{ background: "rgba(123, 231, 255, 0.055)", borderBottom: `1px solid ${HAIRLINE}` }}
      data-testid="ownership-stamp"
    >
      <Dot tone="orbital" />
      <span className="font-grotesk text-[11.5px] font-medium leading-none tracking-[0.03em] text-orbital-blue">
        SwarmOS owns this objective
      </span>
      <Mono size={11} tone="ash" className="ml-auto">{objective.label}</Mono>
    </div>
  );
}

function ObjectiveIdentity({ objective }: { objective: ObjectiveAuthority }) {
  const tone = STATE_TONE[objective.state];
  const held = objective.slots.filter(
    (slot) => slot.agentId && slot.memberState !== "FAILED" && slot.phase !== "FAILED"
  ).length;
  return (
    <div className="px-3 pb-[11px] pt-[11px]">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-grotesk text-[16px] font-medium uppercase leading-none tracking-[0.06em] text-platinum">
          {objective.kind}
        </span>
        {objective.confidence != null ? (
          <div className="flex items-baseline gap-[6px]">
            <Label>conf</Label>
            <Mono size={11} tone="silver">
              {(objective.confidence * 100).toFixed(0).padStart(3, "0")}%
            </Mono>
          </div>
        ) : null}
      </div>
      <div className="mt-[7px]">
        <Mono size={12} tone="silver">{objective.label}</Mono>
      </div>
      <div className="mt-[11px] flex items-end justify-between gap-3">
        <div className="flex flex-col gap-[6px]">
          <Label>state</Label>
          <div className="flex items-center gap-2">
            <Dot tone={tone} />
            <Mono size={13} tone={tone} data-testid="objective-state">{objective.state}</Mono>
          </div>
        </div>
        <div className="flex flex-col items-end gap-[6px]">
          <Label>roles held</Label>
          <Mono size={13} tone={held < objective.requestedMembers ? "amber" : "platinum"}>
            {String(held).padStart(2, "0")} / {String(objective.requestedMembers).padStart(2, "0")}
          </Mono>
        </div>
      </div>
    </div>
  );
}

function SwarmHeader({ swarm }: { swarm: SwarmComposition }) {
  const reinforcing = swarm.reinforcesGroupId != null;
  return (
    <div
      className="flex items-start justify-between gap-3 px-3 pb-[8px] pt-[11px]"
      data-testid={`swarm-${swarm.groupId}`}
      style={swarm.index > 1 ? { borderTop: `1px solid ${HAIRLINE}` } : undefined}
    >
      <div className="flex flex-col gap-[6px]">
        <Label tone={reinforcing ? "amber" : "silver"}>
          {reinforcing ? "reinforcement" : "execution group"}
        </Label>
        {reinforcing ? (
          <Mono size={9} tone="ash">reinforces {groupLabel(swarm.reinforcesGroupId)}</Mono>
        ) : null}
      </div>
      <div className="flex flex-col items-end gap-[6px]">
        <Mono size={10} tone="ash">{swarm.label}</Mono>
        <Mono
          size={11}
          tone={swarm.underStrength ? "amber" : "platinum"}
          data-testid={`swarm-strength-${swarm.groupId}`}
        >
          {String(swarm.heldMembers).padStart(2, "0")} / {String(swarm.requestedMembers).padStart(2, "0")}
        </Mono>
      </div>
    </div>
  );
}

function Composition({
  objective,
  beat,
  capacity,
}: {
  objective: ObjectiveAuthority;
  beat: AdaptationBeat;
  capacity: CapacityRow[];
}) {
  const composed = objective.groupId != null;
  const altitudeOf = new Map(capacity.map((row) => [row.agentId, row.altitudeAglM]));
  const digest = compositionDigest(objective.slots);
  const sectioned = objective.swarms.length > 1;
  const rowsBySwarm = new Map<number, CompositionSlot[]>();
  for (const slot of digest.rows) {
    const bucket = rowsBySwarm.get(slot.swarmIndex);
    if (bucket) bucket.push(slot);
    else rowsBySwarm.set(slot.swarmIndex, [slot]);
  }

  const row = (slot: CompositionSlot) => (
    <SlotRow
      key={`${slot.groupId ?? "single"}:${slot.role}:${slot.index}`}
      slot={slot}
      beat={beat}
      altitudeAglM={slot.agentId ? altitudeOf.get(slot.agentId) ?? null : null}
    />
  );

  return (
    <div>
      {sectioned ? null : (
        <div className="flex items-baseline justify-between gap-3 px-3 pb-[8px] pt-[11px]">
          <Label tone="silver">{composed ? "execution group" : "mission assignment"}</Label>
          <Mono size={10} tone="ash">
            {composed ? groupLabel(objective.groupId) : "SINGLE EXECUTOR"}
          </Mono>
        </div>
      )}

      {beat.phase !== "idle" ? <AdaptationBanner beat={beat} /> : null}

      <div className="flex flex-col">
        {sectioned
          ? objective.swarms.map((swarm) => (
              <div key={swarm.groupId} className="flex flex-col">
                <SwarmHeader swarm={swarm} />
                {(rowsBySwarm.get(swarm.index) ?? []).map(row)}
              </div>
            ))
          : digest.rows.map(row)}
        {digest.hidden ? (
          <div
            className="flex items-center gap-3 px-3 py-[9px]"
            style={{ borderTop: `1px solid ${HAIRLINE}` }}
            data-testid="composition-summary"
          >
            <Mono size={11} tone="ash">{compositionDigestLabel(digest.hidden)}</Mono>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function AdaptationBanner({ beat }: { beat: Exclude<AdaptationBeat, { phase: "idle" }> }) {
  if (beat.phase === "adapting") {
    return (
      <div
        data-testid="adaptation-banner"
        className="value-swap mx-3 mb-[9px] px-[10px] py-[9px]"
        style={{
          background: "rgba(255, 180, 92, 0.07)",
          border: "1px solid rgba(255, 180, 92, 0.34)",
          borderRadius: 4,
        }}
      >
        <Label tone="amber">executor unavailable</Label>
        <div className="mt-[7px] flex items-baseline gap-2">
          <Mono size={13} tone="amber">{beat.lostAgent}</Mono>
          <Mono size={10} tone="ash">{roleLabel(beat.role)}</Mono>
        </div>
        <div className="mt-[7px]">
          <Mono size={10} tone="amber">ADAPTING EXECUTION GROUP…</Mono>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="adaptation-banner"
      className="value-swap mx-3 mb-[9px] px-[10px] py-[9px]"
      style={{
        background: "rgba(184, 255, 102, 0.06)",
        border: "1px solid rgba(184, 255, 102, 0.30)",
        borderRadius: 4,
      }}
    >
      <Label tone="green">group restored</Label>
      <div className="mt-[7px] flex items-baseline gap-2">
        <Mono size={11} tone="ash">{roleLabel(beat.role)}</Mono>
      </div>
      <div className="mt-[6px] flex items-baseline gap-2">
        <Mono size={12} tone="ash" className="line-through">{beat.fromAgent}</Mono>
        <Mono size={11} tone="ash">→</Mono>
        <Mono size={13} tone="green">{beat.toAgent}</Mono>
      </div>
      <div className="mt-[7px]">
        <Mono size={10} tone="green">
          {String(beat.active).padStart(2, "0")} / {String(beat.required).padStart(2, "0")} ACTIVE
        </Mono>
      </div>
    </div>
  );
}

function SlotRow({
  slot,
  beat,
  altitudeAglM,
}: {
  slot: CompositionSlot;
  beat: AdaptationBeat;
  altitudeAglM: number | null;
}) {
  const failing = slot.adapting || slot.memberState === "FAILED";
  const done = slot.memberState === "COMPLETED" || slot.phase === "DONE";
  const highlighted =
    (beat.phase === "restored" && beat.role === slot.role) ||
    (beat.phase === "adapting" && beat.role === slot.role);
  const tone = failing ? "amber" : done ? "green" : "orbital";

  return (
    <div
      className="flex items-start gap-3 px-3 py-[9px]"
      data-testid={slot.groupId ? `slot-${slot.groupId}-${slot.role}` : `slot-${slot.role}`}
      style={{
        borderTop: `1px solid ${HAIRLINE}`,
        background: highlighted ? "rgba(19, 25, 32, 0.6)" : "transparent",
        transition: "background 320ms cubic-bezier(0.2, 0.7, 0.1, 1)",
      }}
    >
      <Mono size={11} tone="ash" className="pt-[2px]">
        {String(slot.index).padStart(2, "0")}
      </Mono>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate font-grotesk text-[11px] font-medium uppercase leading-none tracking-[0.06em] text-platinum">
            {slot.roleIsAssigned ? roleLabel(slot.role) : slot.role}
          </span>
          <Mono size={10} tone={tone}>{phaseLabel(slot.phase ?? slot.memberState)}</Mono>
        </div>

        <div className="mt-[7px] flex items-baseline gap-2">
          {slot.replacesAgentId ? (
            <>
              <Mono size={10} tone="ash" className="line-through">{slot.replacesAgentId}</Mono>
              <Mono size={10} tone="ash">→</Mono>
            </>
          ) : null}
          <Mono size={12} tone={failing ? "amber" : "platinum"} className="value-swap">
            {slot.agentId ?? "UNASSIGNED"}
          </Mono>
          {slot.replacesAgentId ? (
            <Mono size={9} tone="ash">replaced by swarmos</Mono>
          ) : null}
          {altitudeAglM != null && altitudeAglM >= 1 ? (
            <Mono size={9.5} tone="ash" className="ml-auto">
              {altitudeAglM.toFixed(0).padStart(3, "0")} m
            </Mono>
          ) : null}
        </div>
      </div>
    </div>
  );
}
