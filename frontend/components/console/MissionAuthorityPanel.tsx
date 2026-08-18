"use client";

/**
 * MissionAuthorityPanel — what SwarmOS decided, and what it is holding.
 *
 * This is the panel the product lives in. A conventional fleet console makes
 * the aircraft the hero; here the hero is the decision loop, so the reading
 * order is fixed and deliberate:
 *
 *   objective → ownership → composition → roles → executors → spare → evidence
 *
 * Every line is a server field. Roles are the roles SwarmOS assigned
 * (`PRIMARY_OBSERVER`, `SECONDARY_OBSERVER`, `OVERWATCH`); a replacement is
 * drawn from the runtime's own `replaces_agent_id`; an exclusion carries the
 * allocator's reason and the exact mission that made the agent unavailable.
 * Nothing here is composed by the Console.
 */

import type { CapacityRow, CompositionSlot, ObjectiveAuthority } from "@/lib/authority";
import { groupLabel, phaseLabel, roleLabel } from "@/lib/authority";

import { Divider, Dot, HAIRLINE, Label, Mono, Surface, SurfaceHeader } from "./Surface";
import { useAdaptationBeat, type AdaptationBeat } from "./useAdaptation";

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
  capacity,
  evidence,
  onSelectObjective,
}: {
  objectives: ObjectiveAuthority[];
  focused: ObjectiveAuthority | null;
  capacity: CapacityRow[];
  evidence: { label: string; proof: string; simulated: boolean } | null;
  onSelectObjective: (key: string) => void;
}) {
  const beat = useAdaptationBeat(focused);
  const spare = capacity.filter((row) => row.commitment === "SPARE");
  const excluded = capacity.filter((row) => row.excluded && row.commitment !== "SPARE");

  return (
    <Surface
      data-testid="mission-authority"
      /* The adaptation beat is presentation state, so it is published where a
         test — and a screen recording check — can see it without reaching into
         React internals. */
      data-beat={beat.phase}
      className="pointer-events-auto flex flex-col"
      style={{ width: AUTHORITY_WIDTH }}
    >
      <SurfaceHeader title="SwarmOS" sub="mission authority" />

      {!focused ? (
        <div className="px-3 py-6">
          <Mono size={11} tone="ash">
            NO OBJECTIVE HELD
          </Mono>
          <div className="mt-2">
            <Mono size={10} tone="ash">
              AWAITING ALLOCATOR FRAME
            </Mono>
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

          <Divider />

          <Composition objective={focused} beat={beat} />

          <Divider />

          <div className="flex items-start justify-between gap-3 px-3 py-[10px]">
            <Label>spare capacity</Label>
            <div className="flex flex-col items-end gap-[6px]">
              {spare.length === 0 ? (
                <Mono size={11} tone="ash">
                  NONE
                </Mono>
              ) : (
                spare.map((row) => (
                  <div key={row.agentId} className="flex items-center gap-2">
                    <Mono size={11} tone="silver">
                      {row.agentId}
                    </Mono>
                    <Mono size={10} tone="ash">
                      {row.batteryPct.toFixed(0)}%
                    </Mono>
                  </div>
                ))
              )}
            </div>
          </div>

          {excluded.length > 0 ? (
            <>
              <Divider />
              <div className="px-3 py-[10px]">
                <Label tone="amber">excluded from this objective</Label>
                <div className="mt-[7px] flex flex-col gap-[6px]">
                  {excluded.map((row) => (
                    <div key={row.agentId} className="flex items-baseline justify-between gap-3">
                      <Mono size={11} tone="silver">
                        {row.agentId}
                      </Mono>
                      <div className="flex items-baseline gap-2">
                        <Mono size={10} tone="amber">
                          {row.excluded?.reason}
                        </Mono>
                        {row.excluded?.activeMissionId ? (
                          <Mono size={10} tone="ash">
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

          <Divider />

          <div className="flex items-baseline justify-between gap-3 px-3 py-[10px]">
            <Label>mission owner</Label>
            <Mono size={12} tone="orbital">
              SWARMOS
            </Mono>
          </div>

          {evidence ? (
            <>
              <Divider />
              <div className="flex items-baseline justify-between gap-3 px-3 py-[10px]">
                <div className="flex flex-col gap-[6px]">
                  <Label>runtime evidence</Label>
                  <Mono size={11} tone="silver">
                    {evidence.label}
                  </Mono>
                </div>
                <div className="flex items-center gap-[6px]">
                  <Dot tone={evidence.simulated ? "amber" : "green"} />
                  <Mono size={10} tone={evidence.simulated ? "amber" : "green"}>
                    {evidence.proof}
                  </Mono>
                </div>
              </div>
            </>
          ) : null}
        </>
      )}
    </Surface>
  );
}

/**
 * Concurrent objectives.
 *
 * SwarmOS can hold more than one at a time, and the surface has to show that
 * without turning into a queue: the other objectives stay one quiet line, and
 * the focused one gets the panel.
 */
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
            <Mono size={10} tone="ash" className="truncate">
              {objective.kind}
            </Mono>
          </button>
        );
      })}
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
        <span className="font-grotesk text-[16px] font-medium uppercase leading-none tracking-[0.13em] text-platinum">
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
        <Mono size={12} tone="silver">
          {objective.label}
        </Mono>
      </div>

      <div className="mt-[11px] flex items-end justify-between gap-3">
        <div className="flex flex-col gap-[6px]">
          <Label>state</Label>
          <div className="flex items-center gap-2">
            <Dot tone={tone} />
            <Mono size={13} tone={tone} data-testid="objective-state">
              {objective.state}
            </Mono>
          </div>
        </div>
        <div className="flex flex-col items-end gap-[6px]">
          <Label>roles held</Label>
          {/* A role whose holder has failed is not held. The count has to drop
              while SwarmOS is recomposing, or the panel would report a full
              group at the exact moment one of them has gone. */}
          <Mono size={13} tone={held < objective.requestedMembers ? "amber" : "platinum"}>
            {String(held).padStart(2, "0")} /{" "}
            {String(objective.requestedMembers).padStart(2, "0")}
          </Mono>
        </div>
      </div>
    </div>
  );
}

function Composition({
  objective,
  beat,
}: {
  objective: ObjectiveAuthority;
  beat: AdaptationBeat;
}) {
  const composed = objective.groupId != null;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 px-3 pb-[8px] pt-[11px]">
        <Label tone="silver">{composed ? "execution group" : "mission assignment"}</Label>
        <Mono size={10} tone="ash">
          {composed ? groupLabel(objective.groupId) : "SINGLE EXECUTOR"}
        </Mono>
      </div>

      {beat.phase !== "idle" ? <AdaptationBanner beat={beat} /> : null}

      <div className="flex flex-col">
        {objective.slots.map((slot) => (
          <SlotRow key={`${slot.role}:${slot.index}`} slot={slot} beat={beat} />
        ))}
      </div>
    </div>
  );
}

/**
 * The adaptation announcement.
 *
 * Amber, not red — escalation and failure are amber across this product, which
 * is the one palette rule that never bends. It is a two-line statement inside
 * the panel, not an overlay, not a modal and not a screen flash: SwarmOS
 * handled it, and the surface should read as a system that expected this.
 */
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
          <Mono size={13} tone="amber">
            {beat.lostAgent}
          </Mono>
          <Mono size={10} tone="ash">
            {roleLabel(beat.role)}
          </Mono>
        </div>
        <div className="mt-[7px]">
          <Mono size={10} tone="amber">
            ADAPTING EXECUTION GROUP…
          </Mono>
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
        <Mono size={11} tone="ash">
          {roleLabel(beat.role)}
        </Mono>
      </div>
      <div className="mt-[6px] flex items-baseline gap-2">
        <Mono size={12} tone="ash" className="line-through">
          {beat.fromAgent}
        </Mono>
        <Mono size={11} tone="ash">
          →
        </Mono>
        <Mono size={13} tone="green">
          {beat.toAgent}
        </Mono>
      </div>
      <div className="mt-[7px]">
        <Mono size={10} tone="green">
          {String(beat.active).padStart(2, "0")} / {String(beat.required).padStart(2, "0")} ACTIVE
        </Mono>
      </div>
    </div>
  );
}

function SlotRow({ slot, beat }: { slot: CompositionSlot; beat: AdaptationBeat }) {
  const failing = slot.adapting || slot.memberState === "FAILED";
  const done = slot.memberState === "COMPLETED" || slot.phase === "DONE";
  const highlighted =
    (beat.phase === "restored" && beat.role === slot.role) ||
    (beat.phase === "adapting" && beat.role === slot.role);

  const tone = failing ? "amber" : done ? "green" : "orbital";

  return (
    <div
      className="flex items-start gap-3 px-3 py-[9px]"
      data-testid={`slot-${slot.role}`}
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
          <span className="truncate font-grotesk text-[11px] font-medium uppercase leading-none tracking-[0.16em] text-platinum">
            {slot.roleIsAssigned ? roleLabel(slot.role) : slot.role}
          </span>
          <Mono size={10} tone={tone}>
            {phaseLabel(slot.phase ?? slot.memberState)}
          </Mono>
        </div>

        <div className="mt-[7px] flex items-baseline gap-2">
          {slot.replacesAgentId ? (
            <>
              <Mono size={10} tone="ash" className="line-through">
                {slot.replacesAgentId}
              </Mono>
              <Mono size={10} tone="ash">
                →
              </Mono>
            </>
          ) : null}
          <Mono size={12} tone={failing ? "amber" : "platinum"} className="value-swap">
            {slot.agentId ?? "UNASSIGNED"}
          </Mono>
          {slot.replacesAgentId ? (
            <Mono size={9} tone="ash" className="uppercase">
              replaced by swarmos
            </Mono>
          ) : null}
        </div>
      </div>
    </div>
  );
}
