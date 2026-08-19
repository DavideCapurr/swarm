"use client";

import type { CapacityRow, CompositionSlot, ObjectiveAuthority, SwarmComposition } from "@/lib/authority";
import { roleLabel } from "@/lib/authority";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";
import type { AdaptationBeat } from "./useAdaptation";

export const AUTHORITY_WIDTH = 336;

const pad = (value: number) => String(value).padStart(2, "0");

function liveSlot(slot: CompositionSlot): boolean {
  return Boolean(
    slot.agentId &&
      slot.memberState !== "FAILED" &&
      slot.memberState !== "REPLACED" &&
      slot.phase !== "FAILED"
  );
}

function requiredRoles(objective: ObjectiveAuthority): number {
  return objective.swarms[0]?.requestedMembers ?? objective.requestedMembers;
}

function roleCoverage(objective: ObjectiveAuthority): { held: number; required: number } {
  const required = requiredRoles(objective);
  const roles = new Set(objective.slots.filter(liveSlot).map((slot) => slot.role));
  return { held: Math.min(required, roles.size), required };
}

function currentSubunits(swarm: SwarmComposition): CompositionSlot[] {
  return swarm.slots.filter(liveSlot);
}

function swarmName(swarm: SwarmComposition): string {
  return `SWARM ${pad(swarm.index)}`;
}

function swarmTone(swarm: SwarmComposition): "amber" | "orbital" | "green" {
  if (swarm.state === "VERIFIED") return "green";
  if (swarm.state === "ADAPTING" || swarm.underStrength) return "amber";
  return "orbital";
}

export function SwarmAuthorityPanel({
  objectives,
  focused,
  beat,
  capacity,
  onSelectObjective,
}: {
  objectives: ObjectiveAuthority[];
  focused: ObjectiveAuthority | null;
  beat: AdaptationBeat;
  capacity: CapacityRow[];
  onSelectObjective: (key: string) => void;
}) {
  const spare = capacity.filter((row) => row.commitment === "SPARE").length;

  return (
    <Surface
      data-testid="mission-authority"
      data-beat={beat.phase}
      className="pointer-events-auto flex flex-col"
      style={{ width: AUTHORITY_WIDTH }}
    >
      <SurfaceHeader title="SwarmOS" sub="swarm authority" />

      {!focused ? (
        <div className="px-3 py-6">
          <Mono size={11} tone="ash">NO OBJECTIVE HELD</Mono>
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

          <ObjectiveBlock objective={focused} />
          <OwnershipStamp objective={focused} />
          <CoverageBlock objective={focused} />

          {beat.phase !== "idle" ? <AdaptationBanner beat={beat} focused={focused} /> : null}

          <Divider />

          <div className="flex flex-col">
            {focused.swarms.length > 0 ? (
              focused.swarms.map((swarm) => (
                <SwarmBlock key={swarm.groupId} swarm={swarm} objective={focused} />
              ))
            ) : (
              <SingleSubunit objective={focused} />
            )}
          </div>

          <Divider />
          <div className="flex items-baseline justify-between gap-3 px-3 py-[10px]">
            <Label>reserve capacity</Label>
            <Mono size={11} tone={spare > 0 ? "silver" : "ash"}>
              {pad(spare)} SUBUNITS
            </Mono>
          </div>
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
    <div className="flex items-stretch" style={{ borderBottom: `1px solid ${HAIRLINE}` }}>
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
              opacity: active ? 1 : 0.45,
            }}
          >
            <Dot tone={objective.active ? (active ? "orbital" : "silver") : "green"} />
            <Mono size={10} tone={active ? "platinum" : "silver"}>
              {pad(objective.index)}
            </Mono>
            <Mono size={10} tone="ash" className="truncate">
              {objective.kind}
            </Mono>
          </button>
        );
      })}
    </div>
  );
}

function ObjectiveBlock({ objective }: { objective: ObjectiveAuthority }) {
  return (
    <div className="px-3 pb-[10px] pt-[11px]">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-grotesk text-[16px] font-medium uppercase leading-none tracking-[0.13em] text-platinum">
          {objective.kind}
        </span>
        <Mono size={11} tone="ash">{objective.label}</Mono>
      </div>
      <div className="mt-[8px] flex items-center gap-2">
        <Dot tone={objective.state === "VERIFIED" ? "green" : objective.state === "ADAPTING" ? "amber" : "orbital"} />
        <Mono size={11} tone={objective.state === "VERIFIED" ? "green" : objective.state === "ADAPTING" ? "amber" : "orbital"}>
          {objective.state}
        </Mono>
      </div>
    </div>
  );
}

function OwnershipStamp({ objective }: { objective: ObjectiveAuthority }) {
  return (
    <div
      className="flex items-center gap-[9px] px-3 py-[9px]"
      style={{ background: "rgba(123, 231, 255, 0.055)", borderTop: `1px solid ${HAIRLINE}`, borderBottom: `1px solid ${HAIRLINE}` }}
    >
      <Dot tone="orbital" />
      <span className="font-grotesk text-[11.5px] font-medium uppercase leading-none tracking-[0.16em] text-orbital-blue">
        SwarmOS owns objective
      </span>
      <Mono size={10} tone="ash" className="ml-auto">{objective.label}</Mono>
    </div>
  );
}

function CoverageBlock({ objective }: { objective: ObjectiveAuthority }) {
  const coverage = roleCoverage(objective);
  const complete = coverage.held >= coverage.required;
  return (
    <div className="flex items-end justify-between gap-4 px-3 py-[11px]">
      <div className="flex flex-col gap-[6px]">
        <Label>objective coverage</Label>
        <Mono size={10} tone="ash">REQUIRED ROLES</Mono>
      </div>
      <div className="flex items-center gap-2">
        <Dot tone={complete ? "green" : "amber"} />
        <Mono size={18} tone={complete ? "green" : "amber"} data-testid="objective-role-coverage">
          {pad(coverage.held)} / {pad(coverage.required)}
        </Mono>
      </div>
    </div>
  );
}

function SwarmBlock({ swarm, objective }: { swarm: SwarmComposition; objective: ObjectiveAuthority }) {
  const slots = currentSubunits(swarm);
  const tone = swarmTone(swarm);
  const reinforcing = swarm.reinforcesGroupId != null;
  const targetSwarm = reinforcing
    ? objective.swarms.find((candidate) => candidate.groupId === swarm.reinforcesGroupId) ?? objective.swarms[0]
    : null;

  return (
    <section
      data-testid={`swarm-unit-${swarm.groupId}`}
      className="px-3 py-[11px]"
      style={{ borderTop: swarm.index > 1 ? `1px solid ${HAIRLINE}` : undefined }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-[9px]">
          <Dot tone={tone} className="mt-[4px]" />
          <div className="min-w-0">
            <div className="font-grotesk text-[14px] font-medium uppercase leading-none tracking-[0.16em] text-platinum">
              {swarmName(swarm)}
            </div>
            <div className="mt-[6px]">
              <Label tone={reinforcing ? "amber" : "silver"}>
                {reinforcing ? "reinforcement swarm" : "primary swarm"}
              </Label>
            </div>
            {targetSwarm ? (
              <div className="mt-[5px]">
                <Mono size={9.5} tone="ash">REINFORCES {swarmName(targetSwarm)}</Mono>
              </div>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-[5px]">
          <Mono size={13} tone={tone} data-testid={`swarm-subunits-${swarm.groupId}`}>
            {pad(slots.length)} SUBUNITS
          </Mono>
          <Mono size={10} tone={swarm.underStrength ? "amber" : "silver"}>
            {pad(swarm.heldMembers)} / {pad(swarm.requestedMembers)} STRENGTH
          </Mono>
        </div>
      </div>

      <div className="mt-[10px] flex flex-col gap-[7px] border-l border-white/10 pl-[11px]">
        {swarm.slots.map((slot) => (
          <SubunitRow key={`${slot.groupId}:${slot.role}:${slot.agentId ?? slot.index}`} slot={slot} />
        ))}
      </div>
    </section>
  );
}

function SubunitRow({ slot }: { slot: CompositionSlot }) {
  const failed = slot.memberState === "FAILED" || slot.phase === "FAILED";
  const replaced = slot.memberState === "REPLACED";
  const replacement = Boolean(slot.replacesAgentId);
  const tone = failed ? "amber" : replaced ? "ash" : "platinum";

  return (
    <div className="flex items-baseline gap-2">
      <Mono size={10} tone="ash">↳</Mono>
      {replacement ? (
        <>
          <Mono size={10} tone="ash" className="line-through">{slot.replacesAgentId}</Mono>
          <Mono size={10} tone="ash">→</Mono>
        </>
      ) : null}
      <Mono size={11.5} tone={tone} className={replaced ? "line-through" : ""}>
        {slot.agentId ?? "UNASSIGNED"}
      </Mono>
      <span className="min-w-0 flex-1 truncate font-grotesk text-[9.5px] font-medium uppercase leading-none tracking-[0.14em] text-muted-silver">
        {roleLabel(slot.role)}
      </span>
      <Mono size={9.5} tone={failed ? "amber" : "ash"}>
        {failed ? "LOST" : slot.phase ?? slot.memberState ?? "ASSIGNED"}
      </Mono>
    </div>
  );
}

function SingleSubunit({ objective }: { objective: ObjectiveAuthority }) {
  const slot = objective.slots[0];
  return (
    <div className="px-3 py-[11px]">
      <Label>single subunit</Label>
      <div className="mt-[8px] flex items-baseline gap-2">
        <Mono size={13} tone="platinum">{slot?.agentId ?? "UNASSIGNED"}</Mono>
        <Mono size={10} tone="ash">{roleLabel(slot?.role)}</Mono>
      </div>
    </div>
  );
}

function AdaptationBanner({
  beat,
  focused,
}: {
  beat: Exclude<AdaptationBeat, { phase: "idle" }>;
  focused: ObjectiveAuthority;
}) {
  const swarm = focused.swarms.find((candidate) =>
    candidate.slots.some((slot) => slot.role === beat.role)
  );
  const label = swarm ? swarmName(swarm) : "SWARM";

  if (beat.phase === "adapting") {
    return (
      <div
        className="mx-3 mb-[9px] px-[10px] py-[9px]"
        style={{ background: "rgba(255, 180, 92, 0.07)", border: "1px solid rgba(255, 180, 92, 0.34)", borderRadius: 4 }}
      >
        <Label tone="amber">subunit lost · {label} recomposing</Label>
        <div className="mt-[7px] flex items-baseline gap-2">
          <Mono size={12} tone="amber">{beat.lostAgent}</Mono>
          <Mono size={10} tone="ash">{roleLabel(beat.role)}</Mono>
        </div>
      </div>
    );
  }

  return (
    <div
      className="mx-3 mb-[9px] px-[10px] py-[9px]"
      style={{ background: "rgba(184, 255, 102, 0.06)", border: "1px solid rgba(184, 255, 102, 0.30)", borderRadius: 4 }}
    >
      <Label tone="green">subunit replaced · {label} restored</Label>
      <div className="mt-[7px] flex items-baseline gap-2">
        <Mono size={10} tone="ash" className="line-through">{beat.fromAgent}</Mono>
        <Mono size={10} tone="ash">→</Mono>
        <Mono size={12} tone="green">{beat.toAgent}</Mono>
      </div>
    </div>
  );
}
