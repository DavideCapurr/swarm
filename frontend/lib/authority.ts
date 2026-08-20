/**
 * authority.ts — the mission-level view model the redesigned Console renders.
 *
 * The Console's job on this surface is to make one architecture visible:
 *
 *   objective → required capabilities → allocation → ExecutionGroup → roles
 *             → physical executors → execution → adaptation → evidence
 *
 * Every field below is copied out of a frame SwarmOS published. This module
 * selects, groups, orders and labels. It never scores, elects, allocates,
 * replaces or completes anything — those are SwarmOS decisions and they arrive
 * already made. Where a value cannot be read from a frame, the field is null
 * and the surface renders an honest empty state rather than a plausible one.
 *
 * `lib/mission-story.ts` remains the narrative layer for the causal ladder and
 * evidence rows. This module is the composition layer: what the objective
 * requires, who SwarmOS put on it, in which role, and what remains as capacity.
 */

import type {
  AllocationDecision,
  AllocationExclusionReason,
  AnomalyView,
  ExecutionGroup,
  ExecutionGroupMember,
  ExecutionGroupMemberState,
  ExecutionGroupState,
  MissionRuntimeEvent,
  MissionView,
  PayloadEvent,
  UnitState,
} from "./api";
import { runtimeEvidenceLabel, shortId } from "./mission-story";

// ── Formatting ───────────────────────────────────────────────────────────────

export function missionLabel(missionId: string | null | undefined): string {
  return missionId ? `M-${shortId(missionId)}` : "M-—";
}

export function groupLabel(groupId: string | null | undefined): string {
  return groupId ? `EG-${shortId(groupId)}` : "EG-—";
}

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "—";
  return role.replaceAll("_", " ").toUpperCase();
}

export function capabilityLabel(capability: string | null | undefined): string {
  if (!capability) return "—";
  return capability.replaceAll("_", " ").toUpperCase();
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

export type CompositionSlot = {
  index: number;
  role: string;
  roleIsAssigned: boolean;
  agentId: string | null;
  missionId: string | null;
  memberState: ExecutionGroupMemberState | null;
  phase: string | null;
  proof: string | null;
  score: number | null;
  replacesAgentId: string | null;
  replacedAgentId: string | null;
  adapting: boolean;
  groupId: string | null;
  swarmIndex: number;
  reinforcement: boolean;
  divertedFromMissionId: string | null;
};

export type SwarmComposition = {
  index: number;
  groupId: string;
  label: string;
  reinforcesGroupId: string | null;
  requestedMembers: number;
  slots: CompositionSlot[];
  composedMembers: number;
  heldMembers: number;
  underStrength: boolean;
  stateLabel: ExecutionGroupState;
  state: ObjectiveState;
  composedAt: string;
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

export type TraceStageState = "done" | "active" | "pending" | "not_required";

export type TraceStage = {
  name: TraceStageName;
  state: TraceStageState;
  at: string | null;
};

export type Detection = {
  source: string;
  sensor: string;
  label: string | null;
  value: number | null;
  headline: string | null;
  simulated: boolean;
  reportedBy: string | null;
  at: string | null;
};

export type ObjectiveRoute = {
  agentId: string;
  missionId: string;
  points: { lat: number; lon: number }[];
};

export type ObjectiveAuthority = {
  key: string;
  index: number;
  kind: string;
  label: string;
  missionId: string;
  anomalyId: string | null;
  confidence: number | null;
  detectedAt: string | null;
  detection: Detection | null;
  geo: { lat: number; lon: number } | null;
  /** Generic requirements published by SwarmOS for this objective. */
  requiredCapabilities: string[];
  groupId: string | null;
  groupStateLabel: string | null;
  swarms: SwarmComposition[];
  requestedMembers: number;
  slots: CompositionSlot[];
  excludedUnits: {
    agentId: string;
    reason: AllocationExclusionReason;
    activeMissionId: string | null;
  }[];
  activeMembers: number;
  state: ObjectiveState;
  active: boolean;
  trace: TraceStage[];
  routes: ObjectiveRoute[];
  latestProof: string | null;
  decisionAt: string;
};

// ── Physical capacity ────────────────────────────────────────────────────────

export type Commitment =
  | "ASSIGNED"
  | "COMMITTED"
  | "SPARE"
  | "UNAVAILABLE";

export type CapacityRow = {
  agentId: string;
  commitment: Commitment;
  role: string | null;
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
  dockId: string | null;
  /** Canonical planning capabilities projected from SwarmOS UnitState. */
  capabilities: string[];
  excluded: { reason: string; activeMissionId: string | null } | null;
  replacedOut: boolean;
};

export const CAPACITY_SUMMARY_THRESHOLD = 6;

export type CapacitySummary = {
  count: number;
  minBattery: number;
  maxBattery: number;
};

export function capacitySummary(rows: readonly CapacityRow[]): CapacitySummary | null {
  if (rows.length === 0) return null;
  let minBattery = Number.POSITIVE_INFINITY;
  let maxBattery = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    if (row.batteryPct < minBattery) minBattery = row.batteryPct;
    if (row.batteryPct > maxBattery) maxBattery = row.batteryPct;
  }
  return { count: rows.length, minBattery, maxBattery };
}

export function capacitySummaryLabel(summary: CapacitySummary): string {
  const lo = summary.minBattery.toFixed(0).padStart(3, "0");
  const hi = summary.maxBattery.toFixed(0).padStart(3, "0");
  return lo === hi
    ? `${String(summary.count).padStart(2, "0")} AGENTS · BATTERY ${lo}%`
    : `${String(summary.count).padStart(2, "0")} AGENTS · BATTERY ${lo}-${hi}%`;
}

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
  defaultFocusKey: string | null;
};

function detectionOf(anomaly: AnomalyView | null): Detection | null {
  if (!anomaly) return null;
  const evidence = anomaly.evidence ?? null;
  return {
    source: evidence?.source ?? "unknown",
    sensor: evidence?.sensor ?? "UNKNOWN",
    label: evidence?.label ?? null,
    value: evidence?.value ?? null,
    headline: evidence?.headline ?? null,
    simulated: evidence?.simulated ?? true,
    reportedBy: anomaly.detected_by,
    at: anomaly.detected_at,
  };
}

const TERMINAL_MEMBER_STATES: ReadonlySet<ExecutionGroupMemberState> = new Set([
  "COMPLETED",
  "FAILED",
  "REPLACED",
]);

function composedAt(group: ExecutionGroup): string {
  let earliest: string | null = null;
  for (const member of group.members) {
    if (earliest == null || epoch(member.ts) < epoch(earliest)) earliest = member.ts;
  }
  return earliest ?? group.ts;
}

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

function slotsFromGroup(
  group: ExecutionGroup,
  runtime: Map<string, MissionRuntimeEvent>,
  swarmIndex: number,
  allocationsByMission: Map<string, AllocationDecision>
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
    const allocation = live?.mission_id ? allocationsByMission.get(live.mission_id) ?? null : null;
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
      groupId: group.id,
      swarmIndex,
      reinforcement: (group.reinforces_group_id ?? null) != null,
      divertedFromMissionId:
        allocation?.mode === "diversion" ? allocation.diverted_from_mission_id ?? null : null,
    };
  });
}

function groupSwarms(groups: readonly ExecutionGroup[]): ExecutionGroup[][] {
  const byId = new Map(groups.map((group) => [group.id, group]));

  const rootOf = (group: ExecutionGroup): ExecutionGroup => {
    let held = group;
    for (let hop = 0; hop < groups.length; hop += 1) {
      const parentId = held.reinforces_group_id ?? null;
      if (!parentId || parentId === held.id) return held;
      const parent = byId.get(parentId);
      if (!parent) return held;
      if (parent.objective_mission_id !== held.objective_mission_id) return held;
      held = parent;
    }
    return held;
  };

  const buckets = new Map<string, ExecutionGroup[]>();
  const order: string[] = [];
  for (const group of groups) {
    const rootId = rootOf(group).id;
    const bucket = buckets.get(rootId);
    if (bucket) bucket.push(group);
    else {
      buckets.set(rootId, [group]);
      order.push(rootId);
    }
  }

  return order.map((rootId) =>
    (buckets.get(rootId) ?? [])
      .slice()
      .sort((a, b) => epoch(composedAt(a)) - epoch(composedAt(b)))
  );
}

function slotFromDecision(
  decision: AllocationDecision,
  runtime: Map<string, MissionRuntimeEvent>
): CompositionSlot[] {
  const frame = runtime.get(decision.mission_id) ?? null;
  return [
    {
      index: 1,
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
      groupId: null,
      swarmIndex: 1,
      reinforcement: false,
      divertedFromMissionId:
        decision.mode === "diversion" ? decision.diverted_from_mission_id ?? null : null,
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

function foldObjectiveState(states: readonly ObjectiveState[]): ObjectiveState {
  if (states.length === 0) return "COMPOSING";
  if (states.length === 1) return states[0];
  if (states.includes("ADAPTING")) return "ADAPTING";
  if (states.includes("EXECUTING")) return "EXECUTING";
  if (states.includes("COMPOSING")) return "COMPOSING";
  return states.includes("VERIFIED") ? "VERIFIED" : "FAILED";
}

function heldIn(slots: readonly CompositionSlot[]): number {
  return slots.filter(
    (slot) => slot.agentId && slot.memberState !== "FAILED" && slot.phase !== "FAILED"
  ).length;
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
      state: !adapted ? "not_required" : state === "ADAPTING" ? "active" : "done",
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

  const childMissionIds = new Set<string>();
  for (const group of input.executionGroups) {
    for (const member of group.members) childMissionIds.add(member.mission_id);
  }

  const allocationsByMission = new Map<string, AllocationDecision>();
  for (const decision of input.allocations) {
    const held = allocationsByMission.get(decision.mission_id);
    if (!held || epoch(decision.ts) >= epoch(held.ts)) {
      allocationsByMission.set(decision.mission_id, decision);
    }
  }

  const decisions = input.allocations
    .filter((d) => !childMissionIds.has(d.mission_id))
    .filter((d) => d.winner_agent_id || d.excluded_units.length > 0)
    .slice()
    .sort((a, b) => epoch(a.ts) - epoch(b.ts));

  const groupObjectives: ObjectiveAuthority[] = groupSwarms(input.executionGroups).map(
    (groups) => {
      const origin = groups[0];
      const swarms: SwarmComposition[] = groups.map((group, i) => {
        const swarmSlots = slotsFromGroup(group, runtime, i + 1, allocationsByMission);
        const held = heldIn(swarmSlots);
        return {
          index: i + 1,
          groupId: group.id,
          label: groupLabel(group.id),
          reinforcesGroupId: group.reinforces_group_id ?? null,
          requestedMembers: group.requested_members,
          slots: swarmSlots,
          composedMembers: swarmSlots.length,
          heldMembers: held,
          underStrength: held < group.requested_members,
          stateLabel: group.state,
          state: objectiveState(swarmSlots, group),
          composedAt: composedAt(group),
        };
      });

      const slots = swarms.flatMap((swarm) => swarm.slots);
      const anomaly = origin.anomaly_id ? anomalies.get(origin.anomaly_id) ?? null : null;
      const frames = slots.flatMap((s) =>
        s.missionId ? framesByMission.get(s.missionId) ?? [] : []
      );
      const state = foldObjectiveState(swarms.map((swarm) => swarm.state));
      const decisionAt = swarms[0].composedAt;
      const capabilityGroup = origin as ExecutionGroup & {
        required_capabilities?: string[];
      };
      return {
        key: origin.id,
        index: 0,
        kind: anomaly?.kind ?? origin.objective_kind,
        label: missionLabel(origin.objective_mission_id),
        missionId: origin.objective_mission_id,
        anomalyId: origin.anomaly_id,
        confidence: anomaly?.confidence ?? null,
        detectedAt: anomaly?.detected_at ?? null,
        detection: detectionOf(anomaly),
        geo: anomaly ? { lat: anomaly.geo.lat, lon: anomaly.geo.lon } : null,
        requiredCapabilities: [...(capabilityGroup.required_capabilities ?? [])],
        groupId: origin.id,
        groupStateLabel: origin.state,
        swarms,
        requestedMembers: swarms.reduce((total, swarm) => total + swarm.requestedMembers, 0),
        slots,
        excludedUnits: [],
        activeMembers: slots.filter(
          (s) => s.memberState === "ACTIVE" || s.memberState === "ASSIGNED"
        ).length,
        state,
        active: state !== "VERIFIED" && state !== "FAILED",
        trace: buildTrace(slots, state, anomaly?.detected_at ?? null, decisionAt, frames),
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
        decisionAt,
      };
    }
  );

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
      detection: detectionOf(anomaly),
      geo: anomaly ? { lat: anomaly.geo.lat, lon: anomaly.geo.lon } : null,
      requiredCapabilities: [...(decision.required_capabilities ?? [])],
      groupId: null,
      groupStateLabel: null,
      swarms: [],
      requestedMembers: 1,
      slots,
      excludedUnits: decision.excluded_units.map((unit) => ({
        agentId: unit.agent_id,
        reason: unit.reason,
        activeMissionId: unit.active_mission_id,
      })),
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

  const defaultFocusKey =
    objectives.filter((o) => o.active).at(-1)?.key ?? objectives.at(-1)?.key ?? null;

  return {
    objectives,
    capacity: buildCapacity(input, objectives),
    defaultFocusKey,
  };
}

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
        dockId: unit.dock_id,
        capabilities: [...(unit.capabilities ?? [])],
        excluded: exclusions.get(unit.agent_id) ?? null,
        replacedOut: wasReplaced,
      };
    });
}

// ── Composition at scale ─────────────────────────────────────────────────────

export const COMPOSITION_ROWS_MAX = 5;

export type CompositionDigest = {
  rows: CompositionSlot[];
  hidden: {
    count: number;
    byPhase: { label: string; count: number }[];
  } | null;
};

export function compositionDigest(
  slots: readonly CompositionSlot[],
  maxRows: number = COMPOSITION_ROWS_MAX
): CompositionDigest {
  if (slots.length <= maxRows) return { rows: [...slots], hidden: null };

  const notable = new Set(
    slots.filter(
      (slot) =>
        slot.adapting ||
        slot.memberState === "FAILED" ||
        slot.phase === "FAILED" ||
        slot.replacesAgentId != null ||
        slot.reinforcement
    )
  );
  const shown = new Set(notable);
  for (const slot of slots) {
    if (shown.size >= Math.max(maxRows, notable.size)) break;
    shown.add(slot);
  }

  const hidden = slots.filter((slot) => !shown.has(slot));
  if (hidden.length === 0) return { rows: [...slots], hidden: null };

  const counts = new Map<string, number>();
  for (const slot of hidden) {
    const label = phaseLabel(slot.phase ?? slot.memberState);
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }

  return {
    rows: slots.filter((slot) => shown.has(slot)),
    hidden: {
      count: hidden.length,
      byPhase: [...counts.entries()]
        .map(([label, count]) => ({ label, count }))
        .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label)),
    },
  };
}

export function compositionDigestLabel(
  hidden: NonNullable<CompositionDigest["hidden"]>
): string {
  const phases = hidden.byPhase
    .map((entry) => `${String(entry.count).padStart(2, "0")} ${entry.label}`)
    .join(" · ");
  return `+${String(hidden.count).padStart(2, "0")} ROLES · ${phases}`;
}
