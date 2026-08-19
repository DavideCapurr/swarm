"use client";

import type { CompositionSlot, ObjectiveAuthority, SwarmComposition } from "@/lib/authority";

import { Dot, HAIRLINE, Mono } from "./Surface";

const pad = (value: number) => String(value).padStart(2, "0");

function liveSlot(slot: CompositionSlot): boolean {
  return Boolean(
    slot.agentId &&
      slot.memberState !== "FAILED" &&
      slot.memberState !== "REPLACED" &&
      slot.phase !== "FAILED"
  );
}

function subunitCount(swarm: SwarmComposition): number {
  return swarm.slots.filter(liveSlot).length;
}

function tone(swarm: SwarmComposition): "amber" | "orbital" | "green" {
  if (swarm.state === "VERIFIED") return "green";
  if (swarm.state === "ADAPTING" || swarm.underStrength) return "amber";
  return "orbital";
}

function reinforcementOnStation(swarm: SwarmComposition | undefined): boolean {
  if (!swarm) return false;
  return swarm.slots.some(
    (slot) => liveSlot(slot) && (slot.phase === "ON_STATION" || slot.phase === "DONE")
  );
}

export function SwarmMapKey({ focused }: { focused: ObjectiveAuthority | null }) {
  if (!focused || focused.swarms.length === 0) return null;

  const reinforcement = focused.swarms.find((swarm) => swarm.reinforcesGroupId != null);
  const coordinated = focused.swarms.length > 1 && reinforcementOnStation(reinforcement);

  return (
    <div
      data-testid="swarm-map-key"
      className="flex items-center gap-3 px-[11px] py-[8px]"
      style={{
        background: "rgba(8, 11, 14, 0.84)",
        border: `1px solid ${HAIRLINE}`,
        borderRadius: 4,
        backdropFilter: "blur(12px) saturate(0.85)",
        WebkitBackdropFilter: "blur(12px) saturate(0.85)",
      }}
    >
      {focused.swarms.map((swarm, index) => (
        <div key={swarm.groupId} className="flex items-center gap-2">
          {index > 0 ? <Mono size={10} tone="ash">+</Mono> : null}
          <Dot tone={tone(swarm)} />
          <div className="flex items-baseline gap-2">
            <Mono size={11.5} tone="platinum">SWARM {pad(swarm.index)}</Mono>
            <Mono size={9.5} tone={swarm.reinforcesGroupId ? "amber" : "ash"}>
              {pad(subunitCount(swarm))} SUBUNITS
            </Mono>
          </div>
        </div>
      ))}

      {focused.swarms.length > 1 ? (
        <>
          <span className="h-[14px] w-px" style={{ background: HAIRLINE }} aria-hidden="true" />
          <Mono size={9.5} tone={coordinated ? "orbital" : "amber"}>
            {coordinated ? "COORDINATED FORMATION" : "REINFORCEMENT INBOUND"}
          </Mono>
        </>
      ) : null}
    </div>
  );
}
