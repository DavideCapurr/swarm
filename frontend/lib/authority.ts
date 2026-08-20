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
  /** The swarm holding this role — its `ExecutionGroup` id. Null when there is no group. */
  groupId: string | null;
  /** 1-based position of that swarm inside the objective. 1 on a single-executor objective. */
  swarmIndex: number;
  /**
   * True when SwarmOS committed this role as part of a *reinforcing* swarm.
   *
   * Read straight off `ExecutionGroup.reinforces_group_id`, so it is provenance
   * rather than a guess, and it is permanent for the life of the role in exactly
   * the way `replacesAgentId` is. `compositionDigest` treats it as notable for
   * that reason: at fleet scale the reinforcement is the beat, and a summary
   * that folded it away would delete the only thing that just changed.
   */
  reinforcement: boolean;
  /**
   * Set when the latest allocation naming this slot's mission carried
   * `mode: "diversion"`: the mission this agent was pulled off, not the one it
   * now holds. Read off the published allocation frame, never inferred from
   * flight state.
   */
  divertedFromMissionId: string | null;
};

/**
 * One swarm inside an objective.
 *
 * ADR-0012 made the swarm, not the member, the unit SwarmOS adds: an objective
 * that never reached strength is reinforced by dispatching a *second*
 * `ExecutionGroup` against it, carrying `reinforces_group_id`. One objective can
 * therefore hold several, and each one has its own composition, its own
 * lifecycle and its own `requested_members` — the strength *that* swarm was
 * asked to bring.
 *
 * So the strength of a swarm is stated here rather than left to the objective's
 * totals. "Swarm 01 is under strength" is a fact about one unit; summed into an
 * objective-wide count it becomes unreadable the moment there are two.
 */
export type SwarmComposition = {
  /** 1-based order within the objective. 01 is always the originating swarm. */
  index: number;
  groupId: string;
  /** `EG-` plus the real short group id. */
  label: string;
  /** The swarm this one was dispatched to reinforce. Null on an originating swarm. */
  reinforcesGroupId: string | null;
  /** Strength SwarmOS asked this swarm for. */
  requestedMembers: number;
  /** This swarm's roles. The same objects the objective's flattened `slots` holds. */
  slots: CompositionSlot[];
  /**
   * Roles SwarmOS actually dispatched.
   *
   * Below `requestedMembers` this is ADR-0012 partial-strength composition: a
   * role with no eligible executor is left unfilled and the swarm proceeds
   * without it. No new field carries the shortfall — it is the difference
   * between what was asked for and what was committed, exactly as the ADR says.
   */
  composedMembers: number;
  /** Roles whose holder is present and has not failed. */
  heldMembers: number;
  /** Amber on the panel. Never red. */
  underStrength: boolean;
  /** The group's own published lifecycle state. */
  stateLabel: ExecutionGroupState;
  /** The same reading the objective gets, computed over this swarm alone. */
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

/**
 * A stage's state.
 *
 * `pending` and `not_required` look alike and are not: `pending` is a
 * milestone every objective will reach — the surface just has not seen the
 * frame yet. `not_required` is the honest reading of ADAPTED specifically,
 * which is the one stage in this ladder that is conditional rather than
 * guaranteed. A clean objective was never going to need it; saying `pending`
 * reads as a step SwarmOS forgot to finish, when nothing was owed here at all.
 */
export type TraceStageState = "done" | "active" | "pending" | "not_required";

export type TraceStage = {
  name: TraceStageName;
  state: TraceStageState;
  at: string | null;
};

/**
 * Where the objective came from.
 *
 * The surface has to answer "why is a fleet flying at this" before it answers
 * anything else, and the answer is a server frame: `AnomalyView.evidence`
 * carries the reporting source, the sensor, the label and score that triggered
 * it, and a confidence-bound headline SwarmOS composed. The Console renders
 * that headline; it never writes one.
 */
export type Detection = {
  /** `drone_cv`, `thermal_sat`, `fire_detector` or `unknown` — the server's own. */
  source: string;
  sensor: string;
  /** What the detector called it, when it produced a label. */
  label: string | null;
  /** The detector's own score for that label, when it produced one. */
  value: number | null;
  /** SwarmOS's confidence-bound one-liner. */
  headline: string | null;
  /** True when the triggering signal is simulated rather than a real sensor. */
  simulated: boolean;
  /** Who reported it. */
  reportedBy: string | null;
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
  /** Null until an anomaly frame with evidence has arrived. */
  detection: Detection | null;
  geo: { lat: number; lon: number } | null;
  /**
   * The *originating* swarm's group id. Set only when SwarmOS composed a
   * first-class ExecutionGroup for this objective.
   *
   * A reinforcement never becomes the objective's identity: it joined one that
   * already existed, and `key` is this id precisely so focus and selection
   * cannot move when it arrives.
   */
  groupId: string | null;
  groupStateLabel: string | null;
  /** Every swarm SwarmOS put on this objective, oldest first. Empty on a single-executor objective. */
  swarms: SwarmComposition[];
  /** Strength SwarmOS asked for across every swarm. 1 on a single-executor objective. */
  requestedMembers: number;
  /** Every role on the objective, swarm by swarm. `index` stays swarm-local. */
  slots: CompositionSlot[];
  /**
   * Units this objective's own allocation excluded, with the allocator's reason.
   * Empty on a group objective — reinforcement/replacement has its own reading
   * via `slots`, and grouping does not carry a single award to read this off.
   */
  excludedUnits: { agentId: string; reason: AllocationExclusionReason; activeMissionId: string | null }[];
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
  /** Dock the agent reports itself on. The server's own `UnitState.dock_id`. */
  dockId: string | null;
  /** Set when the newest allocation excluded this agent, with the server's reason. */
  excluded: { reason: string; activeMissionId: string | null } | null;
  /** True when SwarmOS replaced this agent out of a role. */
  replacedOut: boolean;
};

/**
 * A bucket of capacity, collapsed to the two facts that survive scale.
 *
 * With a handful of executors the panels list capacity row by row, and that is
 * the right reading: each machine is nameable. With a few dozen it stops being
 * a list anyone reads and starts being a column of identical lines that pushes
 * the rest of the panel out of the viewport — which a recorded surface cannot
 * scroll its way out of.
 *
 * What a reader actually needs from a bucket at that size is how much of it
 * there is and whether it is charged. That is all this returns. It aggregates;
 * it never decides what is committed or spare — `buildCapacity` already did
 * that from composition, and this only counts what it was handed.
 *
 * Null for an empty set, so the caller renders its own honest NONE rather than
 * a zero dressed up as a summary.
 */
export const CAPACITY_SUMMARY_THRESHOLD = 6;

export type CapacitySummary = {
  count: number;
  /** Lowest reported battery in the set, percent. */
  minBattery: number;
  /** Highest reported battery in the set, percent. */
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

/** One line for a summarised set: `27 AGENTS · BATTERY 088-096%`. */
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
  /** Objective the surface focuses by default — the newest one still running. */
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
    // Absent evidence is not a claim of a real sensor. A frame that never said
    // where it came from is treated as simulated, which is what it is on every
    // scenario path this Console serves.
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

/**
 * When SwarmOS decided this objective.
 *
 * Not when it last said anything about it. `ExecutionGroup.ts` is the timestamp
 * of the newest frame, so reading the decision off it made the composition time
 * walk forward for the life of the objective: the trace's COMPOSED stage
 * re-dated itself every time a member changed state, the objective indices could
 * swap places mid-take, and focus — which follows the newest objective — could
 * hand itself to an older one that happened to publish last.
 *
 * The members carry the real answer. SwarmOS stamps each one when it puts it in,
 * and it appends rather than rewrites, so the earliest member timestamp is when
 * the group was composed. The group's own `ts` is the fallback for a frame that
 * has no members yet.
 */
function composedAt(group: ExecutionGroup): string {
  let earliest: string | null = null;
  for (const member of group.members) {
    if (earliest == null || epoch(member.ts) < epoch(earliest)) earliest = member.ts;
  }
  return earliest ?? group.ts;
}

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
      groupId: group.id,
      swarmIndex,
      reinforcement: (group.reinforces_group_id ?? null) != null,
      divertedFromMissionId:
        allocation?.mode === "diversion" ? allocation.diverted_from_mission_id ?? null : null,
    };
  });
}

/**
 * The swarms of one objective, grouped by the relationship SwarmOS published.
 *
 * ADR-0012 is explicit that the link is `reinforces_group_id` and nothing else:
 * two groups can share an `anomaly_id` or an `objective_mission_id` for reasons
 * that are not reinforcement, and a reader that grouped on either would be
 * inventing an operational relationship out of a coincidence.
 *
 * So a group joins another only when it names it *and* the named group is real
 * and serves the same objective mission. A dangling or inconsistent reference
 * leaves the group standing on its own, which is the honest reading and which
 * heals itself the moment the missing frame arrives.
 */
function groupSwarms(groups: readonly ExecutionGroup[]): ExecutionGroup[][] {
  const byId = new Map(groups.map((group) => [group.id, group]));

  const rootOf = (group: ExecutionGroup): ExecutionGroup => {
    let held = group;
    // Bounded rather than `while (true)`: ADR-0012 says a reinforcing group
    // never reinforces in turn, but a frame that said otherwise must not spin
    // this reader.
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

  // Oldest first, so swarm 01 is the swarm that took the objective.
  return order.map((rootId) =>
    (buckets.get(rootId) ?? [])
      .slice()
      .sort((a, b) => epoch(composedAt(a)) - epoch(composedAt(b)))
  );
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

/**
 * One objective's state, read from the swarms serving it.
 *
 * With one swarm this is exactly `objectiveState` and nothing else, which is
 * what keeps every existing take reading as it did. With two it has to answer
 * for both, and the order below is the reading order the surface owes: what is
 * being recomposed outranks what is merely running, and what is running
 * outranks what is still forming — a second swarm still composing does not make
 * an objective with aircraft over the target read as COMPOSING.
 *
 * Only once nothing is live do the terminal states get a say. A mixed terminal
 * result — one swarm verified, one failed — reads VERIFIED, because verification
 * did happen; the swarm rows carry which swarm failed and the counts carry the
 * strength it was served at. ADR-0012 is explicit that a partly served
 * objective is an honest outcome stated by its counts, not a failure.
 */
function foldObjectiveState(states: readonly ObjectiveState[]): ObjectiveState {
  if (states.length === 0) return "COMPOSING";
  if (states.length === 1) return states[0];
  if (states.includes("ADAPTING")) return "ADAPTING";
  if (states.includes("EXECUTING")) return "EXECUTING";
  if (states.includes("COMPOSING")) return "COMPOSING";
  return states.includes("VERIFIED") ? "VERIFIED" : "FAILED";
}

/** The strength readings for one swarm, over the roles it actually holds. */
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
      // Never "pending": ADAPTED does not sit in a queue waiting its turn the
      // way COMPOSED/EXECUTING/VERIFIED do. It is either actively resolving a
      // failure, closed because it resolved one, or not required because none
      // has occurred — and the surface can say that last one as a fact of the
      // present, live-updating the instant it stops being true.
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

  // Child missions of a group are awarded too, so their allocations would
  // otherwise read as objectives in their own right. They are not: the group is
  // the objective.
  const childMissionIds = new Set<string>();
  for (const group of input.executionGroups) {
    for (const member of group.members) childMissionIds.add(member.mission_id);
  }

  // Keyed by mission id regardless of whether that mission belongs to a group
  // or stands alone — a group child's own allocation still carries `mode` and
  // `diverted_from_mission_id`, which `slotsFromGroup` reads for its slot.
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

  // One objective per *set* of related groups, never one per group. A
  // reinforcement joins the objective it was dispatched to serve; giving it its
  // own would put a second tab in the switch, a second mark on the map, and —
  // because focus follows the newest active objective — take the surface off
  // the beat at the exact moment the beat lands.
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
      // The originating swarm's composition time. A reinforcement is a later
      // frame about an objective SwarmOS already decided, and dating the
      // objective from it would re-order the switch and move focus.
      const decisionAt = swarms[0].composedAt;
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
      groupId: null,
      groupStateLabel: null,
      // No ExecutionGroup, so no swarm. The panel says "single executor" in as
      // many words rather than dressing one award up as a unit.
      swarms: [],
      requestedMembers: 1,
      slots,
      // The single award this objective ever gets. Reading it straight off
      // `decision` rather than the capacity-wide "newest allocation" trick
      // `buildCapacity` uses ties the exclusion to the objective whose award
      // actually produced it, not to whichever decision happened most recently.
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
        dockId: unit.dock_id,
        excluded: exclusions.get(unit.agent_id) ?? null,
        replacedOut: wasReplaced,
      };
    });
}

// ── Composition at scale ─────────────────────────────────────────────────────

/** Roles listed individually before the composition starts summarising. */
export const COMPOSITION_ROWS_MAX = 5;

export type CompositionDigest = {
  /** Slots to render as rows, in their own index order. */
  rows: CompositionSlot[];
  /** What was left out, and what state it is in. Null when nothing was. */
  hidden: {
    count: number;
    byPhase: { label: string; count: number }[];
  } | null;
};

/**
 * What a composition shows when SwarmOS put thirty executors on one objective.
 *
 * A cooperative verify has three roles and the panel lists all three. A fleet
 * sweep has thirty, and thirty identical rows is not a composition anyone
 * reads — it is a scrollbar, and it buries the evidence section underneath it.
 *
 * Two rules keep the summary honest. A slot that needs attention is never
 * summarised away: anything failing, adapting, holding a role by replacement,
 * or newly committed as reinforcement is listed whatever the count, because
 * those are the rows the surface exists to show. And what is left out is still
 * stated — how many, and in which phase — rather than silently dropped.
 *
 * Reinforcement earns its place on the same grounds as replacement. A second
 * swarm arriving on an objective that never reached strength is the one thing
 * that just changed, and at the scale where this function starts summarising it
 * is also the thing most easily folded into `+25 ROLES · 25 ON STATION` — which
 * would delete the beat exactly where it matters most.
 */
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

/** One line for the summarised remainder: `+25 ROLES · 25 ON STATION`. */
export function compositionDigestLabel(
  hidden: NonNullable<CompositionDigest["hidden"]>
): string {
  const phases = hidden.byPhase
    .map((entry) => `${String(entry.count).padStart(2, "0")} ${entry.label}`)
    .join(" · ");
  return `+${String(hidden.count).padStart(2, "0")} ROLES · ${phases}`;
}
