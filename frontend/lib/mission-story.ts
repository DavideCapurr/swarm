/**
 * mission-story.ts — assembles the operator-facing narrative from server frames.
 *
 * The narrative the Console has to make legible is fixed:
 *
 *   objective → fleet state → SwarmOS decision → mission ownership
 *             → physical execution → verified evidence → adaptation
 *
 * Every value below is copied out of a frame SwarmOS published. This module
 * selects, orders and labels; it never scores, elects, allocates or completes
 * anything. The only thing it computes is presentation ordering.
 */

import type {
  AllocationDecision,
  AllocationExcludedUnit,
  AllocationScoreBreakdown,
  AnomalyView,
  ExecutionGroup,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "./api";

// ── Formatting ────────────────────────────────────────────────────────────────

export function shortId(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length <= 10 ? value : value.slice(0, 8);
}

export function clock(ts: string | null | undefined): string {
  if (!ts) return "—";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function scoreText(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(3);
}

function epoch(ts: string | null | undefined): number {
  if (!ts) return Number.NaN;
  const value = new Date(ts).getTime();
  return Number.isNaN(value) ? Number.NaN : value;
}

// ── Execution ladder ─────────────────────────────────────────────────────────

export const LADDER_STEPS = [
  "ALLOCATED",
  "DISPATCHED",
  "EN ROUTE",
  "ON STATION",
  "RTL",
  "DONE",
] as const;

export type LadderStep = (typeof LADDER_STEPS)[number];

/**
 * `observed` — a frame proving this step arrived at the Console.
 * `implied`  — a strictly later step was observed, so this one happened, but
 *              this Console session never saw its frame (it booted mid-mission).
 *              Rendered hollow, without a timestamp. Never claimed as evidence.
 * `pending`  — SwarmOS has not published it.
 */
export type LadderSource = "observed" | "implied" | "pending";

export type LadderSlot = {
  step: LadderStep;
  source: LadderSource;
  ts: string | null;
  /** Adapter-established proof behind the step, when SwarmOS published one. */
  proof: string | null;
};

const RUNTIME_EVIDENCE_LABEL: Record<string, string> = {
  mavlink_mission_item_reached: "MISSION_ITEM_REACHED",
  mavlink_rtl_command_acknowledged: "RTL COMMAND ACKNOWLEDGED",
};

export function runtimeEvidenceLabel(
  event: Pick<MissionRuntimeEvent, "evidence"> | undefined | null
): string | null {
  if (!event?.evidence) return null;
  return RUNTIME_EVIDENCE_LABEL[event.evidence] ?? null;
}

export function serverPhaseLabel(phase: string | null | undefined): string {
  if (!phase) return "NO RUNTIME FRAME";
  return phase.replaceAll("_", " ").toUpperCase();
}

function buildLadder(
  decision: AllocationDecision,
  frames: MissionRuntimeEvent[]
): LadderSlot[] {
  const ordered = frames
    .slice()
    .sort((a, b) => epoch(a.ts) - epoch(b.ts));

  const firstWithPhase = (phase: string): MissionRuntimeEvent | undefined =>
    ordered.find((frame) => frame.phase === phase);
  const firstWithEvidence = (evidence: string): MissionRuntimeEvent | undefined =>
    ordered.find((frame) => frame.evidence === evidence);

  const allocated: LadderSlot = decision.winner_agent_id
    ? { step: "ALLOCATED", source: "observed", ts: decision.ts, proof: "ALLOCATOR DECISION" }
    : { step: "ALLOCATED", source: "pending", ts: null, proof: null };

  // The adapter opening its execution stream is what proves the award reached
  // a physical agent. Its first frame is the dispatch fact.
  const dispatch = ordered[0];
  const enRoute = firstWithPhase("EN_ROUTE");
  const onStation = firstWithPhase("ON_STATION");
  const rtl = firstWithEvidence("mavlink_rtl_command_acknowledged");
  const done = firstWithPhase("DONE");
  const failed = firstWithPhase("FAILED");

  const slots: LadderSlot[] = [
    allocated,
    dispatch
      ? { step: "DISPATCHED", source: "observed", ts: dispatch.ts, proof: "EXECUTION STREAM OPEN" }
      : { step: "DISPATCHED", source: "pending", ts: null, proof: null },
    enRoute
      ? { step: "EN ROUTE", source: "observed", ts: enRoute.ts, proof: null }
      : { step: "EN ROUTE", source: "pending", ts: null, proof: null },
    onStation
      ? {
          step: "ON STATION",
          source: "observed",
          ts: onStation.ts,
          proof: runtimeEvidenceLabel(onStation),
        }
      : { step: "ON STATION", source: "pending", ts: null, proof: null },
    rtl
      ? { step: "RTL", source: "observed", ts: rtl.ts, proof: runtimeEvidenceLabel(rtl) }
      : { step: "RTL", source: "pending", ts: null, proof: null },
    done
      ? { step: "DONE", source: "observed", ts: done.ts, proof: null }
      : { step: "DONE", source: "pending", ts: null, proof: null },
  ];

  // A Console that booted mid-mission never saw the earlier frames. Mark those
  // steps as implied rather than pretending they are pending — but never give
  // them a timestamp or an evidence claim. A FAILED mission stops the ladder
  // where it is: nothing later may be implied from a failure.
  if (!failed) {
    let seenLater = false;
    for (let i = slots.length - 1; i >= 0; i -= 1) {
      if (slots[i].source === "observed") {
        seenLater = true;
        continue;
      }
      if (seenLater && slots[i].source === "pending") {
        slots[i] = { ...slots[i], source: "implied" };
      }
    }
  }

  return slots;
}

// ── Candidates ───────────────────────────────────────────────────────────────

export type EligibleCandidate = {
  kind: "eligible";
  agentId: string;
  fsmState: string;
  batteryPct: number;
  score: number;
  breakdown: AllocationScoreBreakdown;
  selected: boolean;
};

export type ExcludedCandidate = {
  kind: "excluded";
  agentId: string;
  fsmState: string;
  batteryPct: number;
  reason: AllocationExcludedUnit["reason"];
  activeMissionId: string | null;
};

export type Candidate = EligibleCandidate | ExcludedCandidate;

function buildCandidates(decision: AllocationDecision): Candidate[] {
  const eligible: Candidate[] = decision.eligible_units
    .slice()
    .sort((a, b) => b.score - a.score)
    .map((unit) => ({
      kind: "eligible" as const,
      agentId: unit.agent_id,
      fsmState: unit.fsm_state,
      batteryPct: unit.battery_pct,
      score: unit.score,
      breakdown: unit.score_breakdown,
      selected: unit.agent_id === decision.winner_agent_id,
    }));
  const excluded: Candidate[] = decision.excluded_units.map((unit) => ({
    kind: "excluded" as const,
    agentId: unit.agent_id,
    fsmState: unit.fsm_state,
    batteryPct: unit.battery_pct,
    reason: unit.reason,
    activeMissionId: unit.active_mission_id,
  }));
  // Exclusions first: on the second objective the exclusion *is* the decision.
  return [...excluded, ...eligible];
}

// ── Evidence ─────────────────────────────────────────────────────────────────

export type EvidenceTier = "verified" | "reported" | "simulated";

export type EvidenceRow = {
  id: string;
  ts: string;
  /** What happened. */
  action: string;
  /** What proves it. */
  proof: string;
  tier: EvidenceTier;
  agentId: string | null;
};

const PAYLOAD_ACTION_LABEL: Record<PayloadEvent["kind"], string> = {
  light_on: "LIGHT ON",
  light_off: "LIGHT OFF",
  play_message: "SPEAKER ACTIVE",
  stop_message: "SPEAKER STOPPED",
};

export function payloadActionLabel(event: PayloadEvent): string {
  return PAYLOAD_ACTION_LABEL[event.kind];
}

export function payloadProofLabel(event: PayloadEvent): string {
  if (event.execution_mode === "mavlink_output_confirmed") return "PX4 OUTPUT CONFIRMED";
  if (event.execution_mode === "mavlink_ack") return "MAVLINK ACK";
  if (event.execution_mode === "simulated") return "SIMULATED";
  return event.status.toUpperCase();
}

export function payloadTier(event: PayloadEvent): EvidenceTier {
  if (event.execution_mode === "mavlink_output_confirmed") return "verified";
  if (event.execution_mode === "simulated") return "simulated";
  return "reported";
}

function buildEvidence(
  frames: MissionRuntimeEvent[],
  payloads: PayloadEvent[]
): EvidenceRow[] {
  const rows: EvidenceRow[] = [];
  for (const frame of frames) {
    const proof = runtimeEvidenceLabel(frame);
    if (!proof) continue;
    rows.push({
      id: frame.id,
      ts: frame.ts,
      action: serverPhaseLabel(frame.phase),
      proof,
      tier: "verified",
      agentId: frame.agent_id,
    });
  }
  for (const event of payloads) {
    rows.push({
      id: event.id,
      ts: event.ts,
      action: payloadActionLabel(event),
      proof: payloadProofLabel(event),
      tier: payloadTier(event),
      agentId: event.agent_id,
    });
  }
  return rows.sort((a, b) => epoch(a.ts) - epoch(b.ts));
}

// ── Objective story ──────────────────────────────────────────────────────────

export type ObjectiveStory = {
  /** 1-based order of arrival within the rendered story. */
  index: number;
  label: string;
  objectiveId: string | null;
  kind: string;
  confidence: number | null;
  geo: { lat: number; lon: number } | null;
  detectedAt: string | null;
  detectedBy: string | null;
  headline: string | null;
  imagerySimulated: boolean;
  missionId: string;
  missionKind: string;
  mode: AllocationDecision["mode"];
  decisionTs: string;
  owner: string | null;
  ownerScore: number | null;
  candidates: Candidate[];
  ladder: LadderSlot[];
  /** Raw server phase of the latest runtime frame, unmodified. */
  serverPhase: string | null;
  latestStep: LadderStep | null;
  active: boolean;
  evidence: EvidenceRow[];
  payloadEvents: PayloadEvent[];
  track: { lat: number; lon: number }[];
};

export type StoryInput = {
  allocations: AllocationDecision[];
  anomalies: AnomalyView[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
  missions: MissionView[];
};

/**
 * Pick the frames to narrate.
 *
 * The demo is a two-objective story. After a long bench session the Console may
 * hold many allocations; prefer the most recent INTRUSION that has a following
 * allocation so the adaptation beat stays visible. This chooses which server
 * frames are on screen — it never recomputes a decision.
 */
export function selectStoryDecisions(
  allocations: AllocationDecision[],
  anomalies: Map<string, AnomalyView>
): AllocationDecision[] {
  const ordered = allocations
    .filter((decision) => decision.mission_kind === "VERIFY")
    .slice()
    .sort((a, b) => epoch(a.ts) - epoch(b.ts));

  if (ordered.length <= 2) return ordered;

  for (let index = ordered.length - 2; index >= 0; index -= 1) {
    const anomalyId = ordered[index].anomaly_id;
    if (anomalyId && anomalies.get(anomalyId)?.kind === "INTRUSION") {
      return [ordered[index], ordered[index + 1]];
    }
  }
  return ordered.slice(-2);
}

function latestReachedStep(ladder: LadderSlot[]): LadderStep | null {
  let latest: LadderStep | null = null;
  for (const slot of ladder) {
    if (slot.source !== "pending") latest = slot.step;
  }
  return latest;
}

export function buildStories(input: StoryInput): ObjectiveStory[] {
  const anomalyMap = new Map(input.anomalies.map((anomaly) => [anomaly.id, anomaly]));
  const decisions = selectStoryDecisions(input.allocations, anomalyMap);

  const logByMission = new Map<string, MissionRuntimeEvent[]>();
  for (const frame of input.missionRuntimeLog) {
    const bucket = logByMission.get(frame.mission_id);
    if (bucket) bucket.push(frame);
    else logByMission.set(frame.mission_id, [frame]);
  }
  const latestByMission = new Map(
    input.missionRuntime.map((frame) => [frame.mission_id, frame])
  );
  const missionsById = new Map(input.missions.map((mission) => [mission.id, mission]));

  return decisions.map((decision, index) => {
    const anomaly = decision.anomaly_id ? anomalyMap.get(decision.anomaly_id) : undefined;
    const latest = latestByMission.get(decision.mission_id);
    const logged = logByMission.get(decision.mission_id) ?? [];
    // The append-only log is the observation record; the latest-per-mission
    // frame is folded in so a REST-booted Console still shows the current step.
    const frames = latest && !logged.some((frame) => frame.id === latest.id)
      ? [...logged, latest]
      : logged;
    const payloads = input.payloadEvents
      .filter((event) => event.mission_id === decision.mission_id)
      .sort((a, b) => epoch(a.ts) - epoch(b.ts));
    const ladder = buildLadder(decision, frames);
    const latestStep = latestReachedStep(ladder);
    const mission = missionsById.get(decision.mission_id);

    return {
      index: index + 1,
      label: `OBJ ${String(index + 1).padStart(2, "0")}`,
      objectiveId: decision.anomaly_id,
      kind: anomaly?.kind ?? decision.mission_kind,
      confidence: anomaly?.confidence ?? null,
      geo: anomaly ? { lat: anomaly.geo.lat, lon: anomaly.geo.lon } : null,
      detectedAt: anomaly?.detected_at ?? null,
      detectedBy: anomaly?.detected_by ?? null,
      headline: anomaly?.evidence?.headline ?? null,
      imagerySimulated: anomaly?.evidence?.simulated ?? true,
      missionId: decision.mission_id,
      missionKind: decision.mission_kind,
      mode: decision.mode,
      decisionTs: decision.ts,
      owner: decision.winner_agent_id,
      ownerScore: decision.winner_score,
      candidates: buildCandidates(decision),
      ladder,
      serverPhase: latest?.phase ?? null,
      latestStep,
      active: latestStep !== "DONE" && latest?.phase !== "FAILED",
      evidence: buildEvidence(frames, payloads),
      payloadEvents: payloads,
      track: (mission?.track ?? []).map((point) => ({ lat: point.lat, lon: point.lon })),
    };
  });
}

/**
 * One-line restatement of the decision, in plain words.
 *
 * Every clause is a field the allocator published — the winner, the exclusion
 * reason, the blocking mission id, the candidate count. Nothing is inferred and
 * no reason is invented: this only says out loud what the rows above show.
 */
export function decisionSummary(story: ObjectiveStory): string[] {
  const lines: string[] = [];
  for (const candidate of story.candidates) {
    if (candidate.kind !== "excluded") continue;
    lines.push(
      candidate.activeMissionId
        ? `${candidate.agentId} excluded · ${candidate.reason} · already owns mission ${shortId(candidate.activeMissionId)}`
        : `${candidate.agentId} excluded · ${candidate.reason}`
    );
  }
  const eligible = story.candidates.filter((c) => c.kind === "eligible").length;
  if (story.owner) {
    lines.push(
      `${story.owner} selected · highest score of ${eligible} eligible agent${eligible === 1 ? "" : "s"}`
    );
  } else {
    lines.push("no agent awarded");
  }
  return lines;
}

// ── Fleet ────────────────────────────────────────────────────────────────────

export type FleetRow = {
  agentId: string;
  fsmState: string;
  batteryPct: number;
  linkQuality: number;
  altitudeAglM: number;
  headingDeg: number;
  geo: { lat: number; lon: number };
  /** Mission this agent owns inside the rendered story, if any. */
  missionId: string | null;
  objectiveLabel: string | null;
  step: LadderStep | null;
  /** Set when this agent was excluded from the newest objective. */
  excludedFrom: { label: string; reason: string; activeMissionId: string | null } | null;
  /** Execution-group role, when SwarmOS assigned one. */
  role: string | null;
};

export function buildFleetRows(
  units: UnitState[],
  stories: ObjectiveStory[],
  groups: ExecutionGroup[]
): FleetRow[] {
  const ownership = new Map<string, ObjectiveStory>();
  for (const story of stories) {
    if (story.owner) ownership.set(story.owner, story);
  }
  const roles = new Map<string, string>();
  for (const group of groups) {
    for (const member of group.members) {
      if (member.state !== "REPLACED") roles.set(member.agent_id, member.role);
    }
  }
  const newest = stories[stories.length - 1];
  const exclusions = new Map<string, ExcludedCandidate>();
  for (const candidate of newest?.candidates ?? []) {
    if (candidate.kind === "excluded") exclusions.set(candidate.agentId, candidate);
  }

  return units
    .slice()
    .sort((a, b) => a.agent_id.localeCompare(b.agent_id))
    .map((unit) => {
      const story = ownership.get(unit.agent_id);
      const excluded = exclusions.get(unit.agent_id);
      return {
        agentId: unit.agent_id,
        fsmState: unit.fsm_state,
        batteryPct: unit.battery_pct,
        linkQuality: unit.link_quality,
        altitudeAglM: unit.altitude_agl_m,
        headingDeg: unit.heading_deg,
        geo: { lat: unit.geo.lat, lon: unit.geo.lon },
        missionId: story?.missionId ?? null,
        objectiveLabel: story?.label ?? null,
        step: story?.latestStep ?? null,
        excludedFrom: excluded
          ? {
              label: newest?.label ?? "",
              reason: excluded.reason,
              activeMissionId: excluded.activeMissionId,
            }
          : null,
        role: roles.get(unit.agent_id) ?? null,
      };
    });
}

// ── Timeline ─────────────────────────────────────────────────────────────────

export type TimelineTick = {
  at: number;
  label: string;
  tier: EvidenceTier | "step";
  proof: string | null;
};

export type TimelineLane = {
  missionId: string;
  objectiveLabel: string;
  objectiveKind: string;
  owner: string | null;
  active: boolean;
  startedAt: number;
  ticks: TimelineTick[];
};

export type Timeline = {
  from: number;
  to: number;
  spanS: number;
  lanes: TimelineLane[];
  /** True while more than one lane is non-terminal — the concurrency proof. */
  concurrent: boolean;
};

export function buildTimeline(stories: ObjectiveStory[], now: number): Timeline {
  const lanes: TimelineLane[] = stories.map((story) => {
    const ticks: TimelineTick[] = [];
    for (const slot of story.ladder) {
      if (slot.source !== "observed" || !slot.ts) continue;
      ticks.push({
        at: epoch(slot.ts),
        label: slot.step,
        tier: "step",
        proof: slot.proof,
      });
    }
    for (const event of story.payloadEvents) {
      ticks.push({
        at: epoch(event.ts),
        label: payloadActionLabel(event),
        tier: payloadTier(event),
        proof: payloadProofLabel(event),
      });
    }
    ticks.sort((a, b) => a.at - b.at);
    return {
      missionId: story.missionId,
      objectiveLabel: story.label,
      objectiveKind: story.kind,
      owner: story.owner,
      active: story.active,
      startedAt: epoch(story.decisionTs),
      ticks,
    };
  });

  const stamps = lanes.flatMap((lane) => [lane.startedAt, ...lane.ticks.map((t) => t.at)]);
  const valid = stamps.filter((value) => Number.isFinite(value));
  const from = valid.length > 0 ? Math.min(...valid) : now;
  // Always keep a live right edge so a running mission reads as running.
  const to = Math.max(valid.length > 0 ? Math.max(...valid) : now, now);
  const spanS = Math.max(1, (to - from) / 1000);

  return {
    from,
    to,
    spanS,
    lanes,
    concurrent: lanes.filter((lane) => lane.active).length > 1,
  };
}

// ── Payload snapshot ─────────────────────────────────────────────────────────

export type PayloadChannel = {
  channel: "LIGHT" | "SPEAKER";
  state: string;
  proof: string;
  tier: EvidenceTier;
  agentId: string | null;
  ts: string | null;
};

/** Current state of each bounded-response channel, latest frame wins. */
export function buildPayloadChannels(events: PayloadEvent[]): PayloadChannel[] {
  const ordered = events.slice().sort((a, b) => epoch(a.ts) - epoch(b.ts));
  const light = ordered.filter((e) => e.kind === "light_on" || e.kind === "light_off").at(-1);
  const speaker = ordered
    .filter((e) => e.kind === "play_message" || e.kind === "stop_message")
    .at(-1);

  return [
    {
      channel: "LIGHT",
      state: light ? payloadActionLabel(light) : "IDLE",
      proof: light ? payloadProofLabel(light) : "NO PAYLOAD FRAME",
      tier: light ? payloadTier(light) : "reported",
      agentId: light?.agent_id ?? null,
      ts: light?.ts ?? null,
    },
    {
      channel: "SPEAKER",
      state: speaker ? payloadActionLabel(speaker) : "IDLE",
      proof: speaker ? payloadProofLabel(speaker) : "NO PAYLOAD FRAME",
      tier: speaker ? payloadTier(speaker) : "reported",
      agentId: speaker?.agent_id ?? null,
      ts: speaker?.ts ?? null,
    },
  ];
}
