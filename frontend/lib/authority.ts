/**
 * authority.ts — the mission-level view model the redesigned Console renders.
 *
 * The Console's job on this surface is to make one architecture visible:
 *
 *   objective → allocation → ExecutionGroup → roles → physical executors
 *             → execution → adaptation → evidence
 *
 * Every field below is copied out of a frame SwarmOS published. This module
 * selects, groups, orders and labels. It never scores, elects, allocates,
 * replaces or completes anything — those are SwarmOS decisions and they arrive
 * already made. Where a value cannot be read from a frame, the field is null
 * and the surface renders an honest empty state rather than a plausible one.
 *
 * `lib/mission-story.ts` remains the narrative layer for the causal ladder and
 * evidence rows. This module is the composition layer: who SwarmOS put on the
 * objective, in which role, and what is left as spare capacity.
 */

import type {
  AllocationDecision,
  AnomalyView,
  ExecutionGroup,
  ExecutionGroupMember,
  ExecutionGroupMemberState,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "./api";
import { runtimeEvidenceLabel, shortId } from "./mission-story";

// ── Formatting ───────────────────────────────────────────────────────────────

/** Mission label — the `M-` prefix plus the real short mission id. */
export function missionLabel(missionId: string | null | undefined): string {
  return missionId ? `M-${shortId(missionId)}` : "M-—";
}

/** Group label — `EG-` plus the real short group id. */
export function groupLabel(groupId: string | null | undefined): string {
  return groupId ? `EG-${shortId(groupId)}` : "EG-—";
}

/** Role as an operator reads it: PRIMARY_OBSERVER → PRIMARY OBSERVER. */
export function roleLabel(role: string | null | undefined): string {
  if (!role) return "—";
  return role.replaceAll("_", " ").toUpperCase();
}

export function phaseLabel(phase: string | null | undefined): string {
  if (!phase) return "PENDING";
  return phase.replaceAll("_", " ").toUpperCase();
}

function epoch(ts: string | null | undefined): number {
  if (!ts) return Number.NaN;
  const value = new Date(ts).getTime();
  return Number.isNaN(value) ? Number.NaN : value;
}

// ── Composition ──────────────────────────────────────────────────────────────

/**
 * One logical role inside an objective.
 *
 * A role outlives the machine holding it — that is the whole point of the
 * architecture, and it is why the slot carries `replacesAgentId` and the
 * displaced holder rather than simply swapping an id.
 */
export type CompositionSlot = {
  /** 1-based display order. Stable across a replacement. */
  index: number;
  /** SwarmOS-assigned role, or the child mission kind on a single-executor objective. */
  role: string;
  /** Whether `role` is a real ExecutionGroup role or the mission kind standing in for one. */
  roleIsAssigned: boolean;
  agentId: string | null;
  missionId: string | null;
  memberState: ExecutionGroupMemberState | null;
  /** Latest runtime phase SwarmOS published for this slot's child mission. */
  phase: string | null;
  /** Adapter-established proof behind the latest runtime frame, when there is one. */
  proof: string | null;
  score: number | null;
  /** Set when SwarmOS put this agent in as a replacement — real provenance. */
  replacesAgentId: string | null;
  /** The displaced holder of this role, when SwarmOS replaced one. */
  replacedAgentId: string | null;
  /** True between observed failure and an observed replacement for this role. */
  adapting: boolean;
};

export type ObjectiveState =
  | "COMPOSING"
  | "EXECUTING"
  | "ADAPTING"
  | "VERIFIED"
  | "FAILED";

export type TraceStageName =
  | "OBJECTIVE"
  | "COMPOSED"
  | "EXECUTING"
  | "ADAPTED"
  | "VERIFIED";

export type TraceStage = {
  name: TraceStageName;
  state: "done" | "active" | "pending";
  at: string | null;
};

export type ObjectiveRoute = {
  agentId: string;
  missionId: string;
  points: { lat: number; lon: number }[];
};

export type ObjectiveAuthority = {
  /** Stable identity for selection — the group id, else the mission id. */
  key: string;
  /** 1-based order of arrival. */
  index: number;
  /** What the objective is: the anomaly kind SwarmOS responded to. */
  kind: string;
  /** Real short mission id, `M-` prefixed. */
  label: string;
  missionId: string;
  anomalyId: string | null;
  confidence: number | null;
  detectedAt: string | null;
  geo: { lat: number; lon: number } | null;
  /** Set only when SwarmOS composed a first-class ExecutionGroup for this objective. */
  groupId: string | null;
  groupStateLabel: string | null;
  /** Roles SwarmOS required. 1 on a single-executor objective. */
  requestedMembers: number;
  slots: CompositionSlot[];
  activeMembers: number;
  state: ObjectiveState;
  /** True while the objective has not reached a terminal state. */
  active: boolean;
  trace: TraceStage[];
  routes: ObjectiveRoute[];
  /** Latest runtime proof SwarmOS published anywhere in this objective. */
  latestProof: string | null;
  decisionAt: string;
};

// ── Physical capacity ────────────────────────────────────────────────────────

export type Commitment =
  | "ASSIGNED"   // serving the focused objective
  | "COMMITTED"  // serving another objective
  | "SPARE"      // available capacity SwarmOS did not need
  | "UNAVAILABLE"; // failed or offline

export type CapacityRow = {
  agentId: string;
  commitment: Commitment;
  /** Role, when the agent holds one in an ExecutionGroup. */
  role: string | null;
  /** Objective key this agent serves, when it serves one. */
  objectiveKey: string | null;
  objectiveLabel: string | null;
  missionId: string | null;
  fsmState: string;
  phase: string | null;
  batteryPct: number;
  linkQuality: number;
  altitudeAglM: number;
  headingDeg: number;
  geo: { lat: number; lon: number };
  /** Set when the newest allocation excluded this agent, with the server's reason. */
  excluded: { reason: string; activeMissionId: string | null } | null;
  /** True when SwarmOS replaced this agent out of a role. */
  replacedOut: boolean;
};

// ── Build ────────────────────────────────────────────────────────────────────

export type AuthorityInput = {
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: AllocationDecision[];
  executionGroups: ExecutionGroup[];
  missions: MissionView[];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: PayloadEvent[];
};

export type AuthorityView = {
  objectives: ObjectiveAuthority[];
  capacity: CapacityRow[];
  /** Objective the surface focuses by default — the newest one still running. */
  defaultFocusKey: string | null;
};

const TERMINAL_MEMBER_STATES: ReadonlySet<ExecutionGroupMemberState> = new Set([
  "COMPLETED",
  "FAILED",
  "REPLACED",
]);

/** Latest runtime frame per mission, from the append-only log plus the projection. */
function latestRuntimeByMission(
  input: AuthorityInput
): Map<string, MissionRuntimeEvent> {
  const latest = new Map<string, MissionRuntimeEvent>();
  const consider = (frame: MissionRuntimeEvent) => {
    const held = latest.get(frame.mission_id);
    if (!held || epoch(frame.ts) >= epoch(held.ts)) latest.set(frame.mission_id, frame);
  };
  for (const frame of input.missionRuntimeLog) consider(frame);
  for (const frame of input.missionRuntime) consider(frame);
  return latest;
}

/**
 * Group the members of an ExecutionGroup by the role they hold.
 *
 * SwarmOS appends a replacement rather than editing the failed member, so a
 * role can carry several rows. The live holder is the one SwarmOS has not
 * marked `REPLACED`; the displaced holder stays visible because the
 * replacement is the thing this surface exists to show.
 */
function slotsFromGroup(
  group: ExecutionGroup,
  runtime: Map<string, MissionRuntimeEvent>
): CompositionSlot[] {
  const byRole = new Map<string, ExecutionGroupMember[]>();
  const order: string[] = [];
  for (const member of group.members) {
    const bucket = byRole.get(member.role);
    if (bucket) bucket.push(member);
    else {
      byRole.set(member.role, [member]);
      order.push(member.role);
    }
  }

  return order.map((role, i) => {
    const members = (byRole.get(role) ?? [])
      .slice()
      .sort((a, b) => epoch(a.ts) - epoch(b.ts));
    const live = members.filter((m) => m.state !== "REPLACED").at(-1) ?? null;
    const replaced = members.filter((m) => m.state === "REPLACED").at(-1) ?? null;
    const frame = live?.mission_id ? runtime.get(live.mission_id) ?? null : null;
    // A role is adapting while its live holder has failed and SwarmOS has not
    // yet put a replacement in. Both halves are read off member state.
    const adapting = Boolean(live && live.state === "FAILED");

    return {
      index: i + 1,
      role,
      roleIsAssigned: true,
      agentId: live?.agent_id ?? null,
      missionId: live?.mission_id ?? null,
      memberState: live?.state ?? null,
      phase: frame?.phase ?? null,
      proof: runtimeEvidenceLabel(frame),
      score: live?.score ?? null,
      replacesAgentId: live?.replaces_agent_id ?? null,
      replacedAgentId: replaced?.agent_id ?? null,
      adapting,
    };
  });
}

/** The single-executor case: the allocation itself is the whole composition. */
function slotFromDecision(
  decision: AllocationDecision,
  runtime: Map<string, MissionRuntimeEvent>
): CompositionSlot[] {
  const frame = runtime.get(decision.mission_id) ?? null;
  return [
    {
      index: 1,
      // SwarmOS assigned no role on a single-executor objective, so the surface
      // says what it actually awarded: the child mission kind.
      role: decision.mission_kind,
      roleIsAssigned: false,
      agentId: decision.winner_agent_id,
      missionId: decision.mission_id,
      memberState: null,
      phase: frame?.phase ?? null,
      proof: runtimeEvidenceLabel(frame),
      score: decision.winner_score,
      replacesAgentId: null,
      replacedAgentId: null,
      adapting: false,
    },
  ];
}

function objectiveState(
  slots: CompositionSlot[],
  group: ExecutionGroup | null
): ObjectiveState {
  if (group) {
    if (group.state === "FAILED") return "FAILED";
    if (group.state === "COMPLETED") return "VERIFIED";
    if (group.state === "DEGRADED" || slots.some((s) => s.adapting)) return "ADAPTING";
    if (group.state === "FORMING") return "COMPOSING";
  }
  if (slots.some((s) => s.adapting)) return "ADAPTING";
  const phases = slots.map((s) => s.phase);
  if (phases.every((p) => p === "DONE") && phases.length > 0) return "VERIFIED";
  if (phases.some((p) => p === "FAILED") && phases.every((p) => p === "FAILED")) return "FAILED";
  if (phases.some((p) => p != null)) return "EXECUTING";
  return slots.some((s) => s.agentId) ? "EXECUTING" : "COMPOSING";
}

function buildTrace(
  slots: CompositionSlot[],
  state: ObjectiveState,
  detectedAt: string | null,
  decisionAt: string,
  frames: MissionRuntimeEvent[]
): TraceStage[] {
  const ordered = frames.slice().sort((a, b) => epoch(a.ts) - epoch(b.ts));
  const composed = slots.some((s) => s.agentId);
  const firstFrame = ordered[0] ?? null;
  const replacement = slots.find((s) => s.replacesAgentId);
  const adapted = Boolean(replacement) || slots.some((s) => s.adapting);
  const verified = state === "VERIFIED";

  // The replacement's own first frame is what dates the adaptation. Falling back
  // to the failure frame keeps the stage honest while a replacement is pending.
  const adaptedAt =
    ordered.find((f) => replacement?.agentId && f.agent_id === replacement.agentId)?.ts ??
    ordered.find((f) => f.phase === "FAILED")?.ts ??
    null;
  const verifiedAt = ordered.filter((f) => f.phase === "DONE").at(-1)?.ts ?? null;

  return [
    { name: "OBJECTIVE", state: "done", at: detectedAt ?? decisionAt },
    {
      name: "COMPOSED",
      state: composed ? "done" : "active",
      at: composed ? decisionAt : null,
    },
    {
      name: "EXECUTING",
      state: !firstFrame ? "pending" : verified ? "done" : "active",
      at: firstFrame?.ts ?? null,
    },
    {
      name: "ADAPTED",
      state: !adapted ? "pending" : state === "ADAPTING" ? "active" : "done",
      at: adaptedAt,
    },
    {
      name: "VERIFIED",
      state: verified ? "done" : "pending",
      at: verifiedAt,
    },
  ];
}

export function buildAuthorityView(input: AuthorityInput): AuthorityView {
  const runtime = latestRuntimeByMission(input);
  const anomalies = new Map(input.anomalies.map((a) => [a.id, a]));
  const missions = new Map(input.missions.map((m) => [m.id, m]));

  const framesByMission = new Map<string, MissionRuntimeEvent[]>();
  for (const frame of [...input.missionRuntimeLog, ...input.missionRuntime]) {
    const bucket = framesByMission.get(frame.mission_id);
    if (bucket) {
      if (!bucket.some((f) => f.id === frame.id)) bucket.push(frame);
    } else framesByMission.set(frame.mission_id, [frame]);
  }

  // Child missions of a group are awarded too, so their allocations would
  // otherwise read as objectives in their own right. They are not: the group is
  // the objective.
  const childMissionIds = new Set<string>();
  for (const group of input.executionGroups) {
    for (const member of group.members) childMissionIds.add(member.mission_id);
  }

  const decisions = input.allocations
    .filter((d) => !childMissionIds.has(d.mission_id))
    .filter((d) => d.winner_agent_id || d.excluded_units.length > 0)
    .slice()
    .sort((a, b) => epoch(a.ts) - epoch(b.ts));

  const groupObjectives: ObjectiveAuthority[] = input.executionGroups.map((group) => {
    const slots = slotsFromGroup(group, runtime);
    const anomaly = group.anomaly_id ? anomalies.get(group.anomaly_id) ?? null : null;
    const frames = slots.flatMap((s) =>
      s.missionId ? framesByMission.get(s.missionId) ?? [] : []
    );
    const state = objectiveState(slots, group);
    return {
      key: group.id,
      index: 0,
      kind: anomaly?.kind ?? group.objective_kind,
      label: missionLabel(group.objective_mission_id),
      missionId: group.objective_mission_id,
      anomalyId: group.anomaly_id,
      confidence: anomaly?.confidence ?? null,
      detectedAt: anomaly?.detected_at ?? null,
      geo: anomaly ? { lat: anomaly.geo.lat, lon: anomaly.geo.lon } : null,
      groupId: group.id,
      groupStateLabel: group.state,
      requestedMembers: group.requested_members,
      slots,
      activeMembers: slots.filter(
        (s) => s.memberState === "ACTIVE" || s.memberState === "ASSIGNED"
      ).length,
      state,
      active: state !== "VERIFIED" && state !== "FAILED",
      trace: buildTrace(slots, state, anomaly?.detected_at ?? null, group.ts, frames),
      routes: slots
        .filter((s) => s.agentId && s.missionId)
        .map((s) => ({
          agentId: s.agentId as string,
          missionId: s.missionId as string,
          points: (missions.get(s.missionId as string)?.track ?? []).map((p) => ({
            lat: p.lat,
            lon: p.lon,
          })),
        })),
      latestProof: slots.map((s) => s.proof).filter(Boolean).at(-1) ?? null,
      decisionAt: group.ts,
    };
  });

  const singleObjectives: ObjectiveAuthority[] = decisions.map((decision) => {
    const slots = slotFromDecision(decision, runtime);
    const anomaly = decision.anomaly_id ? anomalies.get(decision.anomaly_id) ?? null : null;
    const frames = framesByMission.get(decision.mission_id) ?? [];
    const state = objectiveState(slots, null);
    return {
      key: decision.mission_id,
      index: 0,
      kind: anomaly?.kind ?? decision.mission_kind,
      label: missionLabel(decision.mission_id),
      missionId: decision.mission_id,
      anomalyId: decision.anomaly_id,
      confidence: anomaly?.confidence ?? null,
      detectedAt: anomaly?.detected_at ?? null,
      geo: anomaly ? { lat: anomaly.geo.lat, lon: anomaly.geo.lon } : null,
      groupId: null,
      groupStateLabel: null,
      requestedMembers: 1,
      slots,
      activeMembers: slots.filter((s) => s.agentId).length,
      state,
      active: state !== "VERIFIED" && state !== "FAILED",
      trace: buildTrace(slots, state, anomaly?.detected_at ?? null, decision.ts, frames),
      routes: slots
        .filter((s) => s.agentId && s.missionId)
        .map((s) => ({
          agentId: s.agentId as string,
          missionId: s.missionId as string,
          points: (missions.get(s.missionId as string)?.track ?? []).map((p) => ({
            lat: p.lat,
            lon: p.lon,
          })),
        })),
      latestProof: slots.map((s) => s.proof).filter(Boolean).at(-1) ?? null,
      decisionAt: decision.ts,
    };
  });

  const objectives = [...groupObjectives, ...singleObjectives]
    .sort((a, b) => epoch(a.decisionAt) - epoch(b.decisionAt))
    .map((objective, i) => ({ ...objective, index: i + 1 }));

  // Focus follows the newest objective that is still running, so the surface
  // lands on the thing that is happening rather than on history.
  const defaultFocusKey =
    objectives.filter((o) => o.active).at(-1)?.key ?? objectives.at(-1)?.key ?? null;

  return {
    objectives,
    capacity: buildCapacity(input, objectives),
    defaultFocusKey,
  };
}

/**
 * Physical capacity — every executor SwarmOS can see, and what it is doing.
 *
 * Commitment is read from composition, not guessed from flight state: an agent
 * is ASSIGNED because SwarmOS put it in a role, and SPARE because SwarmOS left
 * it out. That distinction is the product.
 */
function buildCapacity(
  input: AuthorityInput,
  objectives: ObjectiveAuthority[]
): CapacityRow[] {
  type Commitmentish = {
    objective: ObjectiveAuthority;
    slot: CompositionSlot;
  };
  const held = new Map<string, Commitmentish>();
  const replacedOut = new Set<string>();

  for (const objective of objectives) {
    for (const slot of objective.slots) {
      if (slot.replacedAgentId) replacedOut.add(slot.replacedAgentId);
      if (!slot.agentId) continue;
      const current = held.get(slot.agentId);
      // An agent serving several objectives shows the newest — the same rule
      // the focus uses.
      if (!current || epoch(objective.decisionAt) >= epoch(current.objective.decisionAt)) {
        held.set(slot.agentId, { objective, slot });
      }
    }
  }

  const newest = input.allocations
    .slice()
    .sort((a, b) => epoch(a.ts) - epoch(b.ts))
    .at(-1);
  const exclusions = new Map(
    (newest?.excluded_units ?? []).map((unit) => [
      unit.agent_id,
      { reason: unit.reason as string, activeMissionId: unit.active_mission_id },
    ])
  );

  return input.units
    .slice()
    .sort((a, b) => a.agent_id.localeCompare(b.agent_id))
    .map((unit) => {
      const commitment = held.get(unit.agent_id) ?? null;
      const wasReplaced = replacedOut.has(unit.agent_id);
      const failedInRole = commitment?.slot.memberState === "FAILED";
      const stillServing =
        commitment != null &&
        commitment.objective.active &&
        !TERMINAL_MEMBER_STATES.has(
          (commitment.slot.memberState ?? "ASSIGNED") as ExecutionGroupMemberState
        );

      let state: Commitment;
      if (unit.fsm_state === "ERROR" || unit.fsm_state === "OFFLINE" || failedInRole || wasReplaced) {
        state = "UNAVAILABLE";
      } else if (stillServing) {
        state = "ASSIGNED";
      } else if (commitment && commitment.objective.active) {
        state = "COMMITTED";
      } else {
        state = "SPARE";
      }

      return {
        agentId: unit.agent_id,
        commitment: state,
        role: commitment?.slot.roleIsAssigned ? commitment.slot.role : null,
        objectiveKey: state === "SPARE" ? null : commitment?.objective.key ?? null,
        objectiveLabel: state === "SPARE" ? null : commitment?.objective.label ?? null,
        missionId: commitment?.slot.missionId ?? unit.current_mission_id,
        fsmState: unit.fsm_state,
        phase: commitment?.slot.phase ?? null,
        batteryPct: unit.battery_pct,
        linkQuality: unit.link_quality,
        altitudeAglM: unit.altitude_agl_m,
        headingDeg: unit.heading_deg,
        geo: { lat: unit.geo.lat, lon: unit.geo.lon },
        excluded: exclusions.get(unit.agent_id) ?? null,
        replacedOut: wasReplaced,
      };
    });
}

/** Latest payload channel truth, kept for the evidence line on the authority panel. */
export function latestPayloadProof(
  events: PayloadEvent[],
  missionIds: ReadonlySet<string>
): { label: string; proof: string; simulated: boolean } | null {
  const scoped = events
    .filter((event) => missionIds.has(event.mission_id))
    .sort((a, b) => epoch(a.ts) - epoch(b.ts));
  const latest = scoped.at(-1);
  if (!latest) return null;
  const label =
    latest.kind === "light_on"
      ? "PRESENCE LIGHT ON"
      : latest.kind === "light_off"
        ? "PRESENCE LIGHT OFF"
        : latest.kind === "play_message"
          ? "SPEAKER ACTIVE"
          : "SPEAKER STOPPED";
  const proof =
    latest.execution_mode === "mavlink_output_confirmed"
      ? "PX4 OUTPUT CONFIRMED"
      : latest.execution_mode === "mavlink_ack"
        ? "MAVLINK ACK"
        : latest.execution_mode === "simulated"
          ? "SIMULATED"
          : latest.status.toUpperCase();
  return { label, proof, simulated: latest.execution_mode === "simulated" };
}
