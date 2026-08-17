"use client";

/**
 * DecisionRail — the causal chain for the focused objective.
 *
 * Read top to bottom it is one sentence:
 *
 *   this objective arrived → SwarmOS evaluated the fleet → SwarmOS selected
 *   this agent → that agent owns this mission → the mission executed
 *   → this is the evidence.
 *
 * Not a stack of cards: numbered steps on a continuous rail, so the causality
 * is the layout. Every value is copied from a server frame.
 */

import type { ExecutionGroup } from "@/lib/api";
import {
  clock,
  decisionSummary,
  scoreText,
  serverPhaseLabel,
  shortId,
  type Candidate,
  type LadderSlot,
  type ObjectiveStory,
  type PayloadChannel,
} from "@/lib/mission-story";

import {
  Eyebrow,
  EvidenceStamp,
  LadderTick,
  Panel,
  StepNumber,
  TIER_TEXT,
  Value,
} from "./primitives";

export function DecisionRail({
  story,
  group,
  payloadChannels,
  className = "",
}: {
  story: ObjectiveStory | null;
  group: ExecutionGroup | undefined;
  payloadChannels: PayloadChannel[];
  className?: string;
}) {
  return (
    <Panel
      className={className}
      title="SwarmOS decision"
      right={
        story ? (
          <span className="font-mono text-[12px] tracking-[0.16em] text-orbital-blue">
            FOCUS {story.label}
          </span>
        ) : null
      }
      bodyClassName="overflow-y-auto"
      data-testid="decision-rail"
    >
      {!story ? (
        <div className="px-4 py-6">
          <Value size="md" tone="silver">
            No allocator frame yet.
          </Value>
          <p className="mt-2 font-mono text-[13px] leading-5 text-ash">
            No candidate, score, exclusion or owner is drawn until SwarmOS publishes it.
          </p>
        </div>
      ) : (
        <div className="flex flex-col">
          <Step n={1} title="Objective">
            <div className="flex items-baseline justify-between gap-4">
              <Value size="xl">{story.kind}</Value>
              <Value size="sm" tone="ash">
                {clock(story.detectedAt ?? story.decisionTs)}
              </Value>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1">
              <Field label="confidence">
                {story.confidence != null
                  ? `${(story.confidence * 100).toFixed(0)}%`
                  : "—"}
              </Field>
              <Field label="event">{shortId(story.objectiveId)}</Field>
              <Field label="reported by">{story.detectedBy ?? "swarm anomaly bus"}</Field>
              <Field label="position">
                {story.geo
                  ? `${story.geo.lat.toFixed(5)} ${story.geo.lon.toFixed(5)}`
                  : "—"}
              </Field>
            </div>
            {story.headline ? (
              <p className="mt-2 font-mono text-[13px] leading-5 text-muted-silver">
                {story.headline}
              </p>
            ) : null}
          </Step>

          <Step n={2} title="Fleet evaluated by SwarmOS">
            <div className="flex items-center justify-between">
              <Eyebrow>mode · {story.mode}</Eyebrow>
              {/* Literal in the markup, not only via text-transform: the
                  recording checklist looks for this exact string. */}
              <Eyebrow>SERVER REASONS</Eyebrow>
            </div>
            <div className="mt-2 flex flex-col">
              {story.candidates.map((candidate) => (
                <CandidateRow key={candidate.agentId} candidate={candidate} />
              ))}
            </div>
          </Step>

          <Step n={3} title="Selected by SwarmOS">
            <div className="flex items-baseline justify-between gap-4">
              <Value size="xl" tone="orbital" className="tracking-[0.04em]">
                {story.owner ?? "NO AWARD"}
              </Value>
              <div className="text-right">
                <Eyebrow>winner score</Eyebrow>
                <div>
                  <Value size="lg" tone="orbital">
                    {scoreText(story.ownerScore)}
                  </Value>
                </div>
              </div>
            </div>
            <ul data-testid="decision-summary" className="mt-2 flex flex-col gap-[3px]">
              {decisionSummary(story).map((line) => (
                <li
                  key={line}
                  className={`font-mono text-[13px] leading-5 tracking-[0.04em] ${
                    line.includes("excluded") ? "text-launch-amber" : "text-muted-silver"
                  }`}
                >
                  {line}
                </li>
              ))}
            </ul>
          </Step>

          <Step n={4} title="Mission ownership">
            <div className="flex items-baseline justify-between gap-4">
              <Value size="md">mission {shortId(story.missionId)}</Value>
              <Value size="sm" tone="silver">
                owned by {story.owner ?? "—"}
              </Value>
            </div>
            <p className="mt-2 font-mono text-[12px] leading-5 text-ash">
              Ownership is issued by SwarmOS. The physical agent executes it; it does not
              elect itself, choose peers, or create fleet actions.
            </p>
          </Step>

          <Step n={5} title="Physical execution">
            <Ladder ladder={story.ladder} />
            <div className="mt-3 flex items-center justify-between">
              <Eyebrow>server phase</Eyebrow>
              <Value size="sm" tone="platinum">
                {serverPhaseLabel(story.serverPhase)}
              </Value>
            </div>
          </Step>

          <Step n={6} title="Evidence" last={!group}>
            <div className="flex flex-col gap-[6px]">
              {story.evidence.length === 0 ? (
                <span className="font-mono text-[13px] text-ash">
                  NO EXECUTION EVIDENCE PUBLISHED
                </span>
              ) : (
                story.evidence.map((row) => (
                  <div
                    key={row.id}
                    data-testid={`evidence-${row.id}`}
                    className="flex items-center justify-between gap-3 border-l-2 border-gunmetal pl-2"
                    style={{
                      borderLeftColor:
                        row.tier === "verified"
                          ? "#B8FF66"
                          : row.tier === "simulated"
                            ? "#FFB45C"
                            : "#2A3138",
                    }}
                  >
                    <span className="flex items-baseline gap-2">
                      <Value size="sm" tone="ash">
                        {clock(row.ts)}
                      </Value>
                      <Value size="sm">{row.action}</Value>
                    </span>
                    <EvidenceStamp
                      tier={row.tier}
                      bound={row.tier === "verified" ? "PX4 SITL" : undefined}
                    >
                      {row.proof}
                    </EvidenceStamp>
                  </div>
                ))
              )}
            </div>

            <div className="mt-4">
              <div className="flex items-center justify-between">
                <Eyebrow>bounded physical response · fleet</Eyebrow>
                <Eyebrow>verified vs simulated</Eyebrow>
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {payloadChannels.map((channel) => (
                  <div
                    key={channel.channel}
                    data-testid={`payload-${channel.channel}`}
                    className={`border-l-2 border-y border-r border-y-gunmetal border-r-gunmetal px-2 py-2 ${
                      channel.tier === "verified"
                        ? "border-l-signal-green"
                        : channel.tier === "simulated"
                          ? "border-l-launch-amber"
                          : "border-l-graphite"
                    }`}
                  >
                    <div className="flex items-baseline justify-between">
                      <Eyebrow>{channel.channel}</Eyebrow>
                      <span className="font-mono text-[13px] tracking-[0.1em] text-ash">
                        {channel.agentId ?? "—"}
                      </span>
                    </div>
                    <div className="mt-1">
                      <Value size="md">{channel.state}</Value>
                    </div>
                    <div className={`mt-1 font-mono text-[13px] tracking-[0.12em] ${TIER_TEXT[channel.tier]}`}>
                      {channel.proof}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Step>

          {group ? <ExecutionGroupStep group={group} /> : null}
        </div>
      )}
    </Panel>
  );
}

// ── Rail structure ────────────────────────────────────────────────────────────

function Step({
  n,
  title,
  children,
  last = false,
}: {
  n: number;
  title: string;
  children: React.ReactNode;
  last?: boolean;
}) {
  return (
    <div className="relative grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 px-4 pb-4 pt-3">
      <div className="flex flex-col items-center">
        <StepNumber n={n} />
        {!last ? <div className="mt-2 w-px flex-1 bg-gunmetal" /> : null}
      </div>
      <div className="min-w-0">
        <div className="mb-2 flex items-center gap-3">
          <Eyebrow tone="platinum">{title}</Eyebrow>
          <div className="h-px flex-1 bg-gunmetal" />
        </div>
        {children}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-mono text-[13px] uppercase tracking-[0.14em] text-ash">{label}</span>
      <Value size="sm" tone="silver">
        {children}
      </Value>
    </div>
  );
}

// ── Candidates ────────────────────────────────────────────────────────────────

function CandidateRow({ candidate }: { candidate: Candidate }) {
  if (candidate.kind === "excluded") {
    return (
      <div
        data-testid={`candidate-${candidate.agentId}`}
        className="border-l-2 border-launch-amber bg-launch-amber/[0.04] px-2 py-2"
      >
        <div className="flex items-baseline justify-between gap-3">
          <Value size="md">{candidate.agentId}</Value>
          <span className="font-mono text-[15px] uppercase tracking-[0.16em] text-launch-amber">
            EXCLUDED · {candidate.reason}
          </span>
        </div>
        <div className="mt-1 font-mono text-[13px] tracking-[0.1em] text-ash">
          {candidate.fsmState} · batt {candidate.batteryPct.toFixed(0)}%
          {candidate.activeMissionId
            ? ` · holds active mission ${shortId(candidate.activeMissionId)}`
            : ""}
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid={`candidate-${candidate.agentId}`}
      className={`border-l-2 px-2 py-2 ${
        candidate.selected
          ? "border-orbital-blue bg-orbital-blue/[0.05]"
          : "border-graphite"
      }`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-baseline gap-3">
          <Value size="md">{candidate.agentId}</Value>
          <span
            className={`font-mono text-[15px] uppercase tracking-[0.16em] ${
              candidate.selected ? "text-orbital-blue" : "text-muted-silver"
            }`}
          >
            {candidate.selected ? "SELECTED" : "ELIGIBLE"}
          </span>
        </span>
        <Value size="lg" tone={candidate.selected ? "orbital" : "silver"}>
          {scoreText(candidate.score)}
        </Value>
      </div>
      <div className="mt-1 font-mono text-[13px] tracking-[0.08em] text-ash">
        {`${candidate.fsmState} · dist ${Math.round(candidate.breakdown.distance_m)}m +${candidate.breakdown.distance_score.toFixed(2)}`}
        {` · batt ${candidate.breakdown.battery_pct.toFixed(0)}% +${candidate.breakdown.battery_score.toFixed(2)}`}
        {` · priority +${candidate.breakdown.priority_score.toFixed(2)}`}
        {candidate.breakdown.busy_penalty
          ? ` · busy ${candidate.breakdown.busy_penalty.toFixed(2)}`
          : ""}
      </div>
    </div>
  );
}

// ── Ladder ────────────────────────────────────────────────────────────────────

export function Ladder({ ladder }: { ladder: LadderSlot[] }) {
  return (
    <div data-testid="execution-ladder" className="flex items-stretch">
      {ladder.map((slot, index) => (
        <div key={slot.step} className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center">
            <LadderTick
              source={slot.source}
              tone={slot.proof && slot.source === "observed" ? "green" : "orbital"}
            />
            {index < ladder.length - 1 ? (
              <div
                className={`h-px flex-1 ${
                  ladder[index + 1].source === "pending" ? "bg-graphite" : "bg-orbital-blue/60"
                }`}
              />
            ) : null}
          </div>
          <span
            className={`mt-2 font-mono text-[12px] uppercase leading-tight tracking-[0.08em] ${
              slot.source === "observed"
                ? "text-platinum"
                : slot.source === "implied"
                  ? "text-muted-silver"
                  : "text-ash"
            }`}
          >
            {slot.step}
          </span>
          <span className="mt-[2px] font-mono text-[11px] tabular-nums text-ash">
            {slot.source === "observed" ? clock(slot.ts) : slot.source === "implied" ? "seen later" : "pending"}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Execution group (TAKE B) ─────────────────────────────────────────────────

function ExecutionGroupStep({ group }: { group: ExecutionGroup }) {
  return (
    <Step n={7} title="Execution group" last>
      <div className="flex items-baseline justify-between gap-3">
        <Value size="lg">{group.objective_kind.replaceAll("_", " ")}</Value>
        <span className="text-right">
          <span
            className={`font-mono text-[15px] uppercase tracking-[0.16em] ${
              group.state === "FAILED" || group.state === "DEGRADED"
                ? "text-launch-amber"
                : "text-signal-green"
            }`}
          >
            {group.state}
          </span>
          <span className="ml-2 font-mono text-[12px] text-ash">
            {group.requested_members} REQUIRED ROLES
          </span>
        </span>
      </div>
      <div className="my-2 h-px w-full bg-gunmetal" />
      <div className="flex flex-col gap-[6px]">
        {group.members.map((member) => (
          <div
            key={member.mission_id}
            data-testid={`group-member-${member.mission_id}`}
            className={`border-l-2 px-2 py-[6px] ${
              member.state === "REPLACED" || member.state === "FAILED"
                ? "border-launch-amber"
                : "border-orbital-blue"
            }`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <Value size="sm">{member.role.replaceAll("_", " ")}</Value>
              <span className="flex items-baseline gap-3">
                <Value size="sm" tone="platinum">
                  {member.agent_id}
                </Value>
                <Value size="sm" tone="orbital">
                  {scoreText(member.score)}
                </Value>
              </span>
            </div>
            <div
              className={`mt-1 font-mono text-[12px] tracking-[0.12em] ${
                member.state === "REPLACED" || member.state === "FAILED"
                  ? "text-launch-amber"
                  : "text-ash"
              }`}
            >
              {member.state}
              {member.replaces_agent_id ? ` · REPLACES ${member.replaces_agent_id}` : ""}
              {` · mission ${shortId(member.mission_id)}`}
            </div>
          </div>
        ))}
      </div>
      {group.failure_reason ? (
        <div className="mt-2 font-mono text-[12px] text-launch-amber">{group.failure_reason}</div>
      ) : null}
      <p className="mt-2 font-mono text-[12px] leading-5 text-ash">
        Membership, roles, scores and replacements are published by SwarmOS. Physical agents
        do not choose peers or roles.
      </p>
    </Step>
  );
}
