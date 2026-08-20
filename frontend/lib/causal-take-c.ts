import type {
  AnomalyView,
  DispositionDecision,
  ExecutionGroup,
  MissionRuntimeEvent,
  UnitState,
} from "./api";

export const TAKE_C_PLAYBACK_SCALE = 4;

export type CausalTakeCFrame =
  | { at: number; kind: "unit"; data: UnitState }
  | { at: number; kind: "anomaly"; data: AnomalyView }
  | { at: number; kind: "group"; data: ExecutionGroup }
  | { at: number; kind: "disposition"; data: DispositionDecision }
  | { at: number; kind: "runtime"; data: MissionRuntimeEvent };

export type CausalTakeCCapture = {
  schema_version: 1;
  provenance: "causal-simulator-runtime";
  proof_scope: {
    swarmos_decisions: string;
    physical_positions: string;
    disposition_execution: "simulator only";
    px4_disposition_claim: false;
    anomaly_lifecycle?: string;
  };
  started_at: string;
  duration_ms: number;
  world_facts: string[];
  milestones: Record<string, string | number>;
  frames: CausalTakeCFrame[];
};

export type CausalTakeCSlice = {
  units: UnitState[];
  anomalies: AnomalyView[];
  allocations: [];
  executionGroups: ExecutionGroup[];
  dispositions: DispositionDecision[];
  missions: [];
  missionRuntime: MissionRuntimeEvent[];
  missionRuntimeLog: MissionRuntimeEvent[];
  payloadEvents: [];
  now: number;
};

export function isCausalTakeCCapture(value: unknown): value is CausalTakeCCapture {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<CausalTakeCCapture>;
  return (
    candidate.schema_version === 1 &&
    candidate.provenance === "causal-simulator-runtime" &&
    candidate.proof_scope?.disposition_execution === "simulator only" &&
    candidate.proof_scope?.px4_disposition_claim === false &&
    typeof candidate.started_at === "string" &&
    typeof candidate.duration_ms === "number" &&
    Array.isArray(candidate.frames)
  );
}

export function causalTakeCDurationMs(capture: CausalTakeCCapture): number {
  return Math.ceil(capture.duration_ms * TAKE_C_PLAYBACK_SCALE);
}

/**
 * Fold a generated causal capture exactly like the live state provider.
 *
 * Playback is uniformly time-dilated for human legibility. That changes only
 * presentation time: identities, decisions, ordering, physical coordinates and
 * server-issued disposition geometry are never interpolated or recomputed.
 */
export function foldCausalTakeC(
  playbackAtMs: number,
  capture: CausalTakeCCapture
): CausalTakeCSlice {
  const captureAtMs = Math.max(
    0,
    Math.min(capture.duration_ms, playbackAtMs / TAKE_C_PLAYBACK_SCALE)
  );
  const units = new Map<string, UnitState>();
  const anomalies = new Map<string, AnomalyView>();
  const groups = new Map<string, ExecutionGroup>();
  const dispositions = new Map<string, DispositionDecision>();
  const runtimeLatest = new Map<string, MissionRuntimeEvent>();
  const runtimeLog: MissionRuntimeEvent[] = [];

  for (const frame of capture.frames) {
    if (frame.at > captureAtMs) break;
    switch (frame.kind) {
      case "unit":
        units.set(frame.data.agent_id, frame.data);
        break;
      case "anomaly":
        anomalies.set(frame.data.id, frame.data);
        break;
      case "group":
        groups.set(frame.data.id, frame.data);
        break;
      case "disposition":
        dispositions.set(frame.data.objective_mission_id, frame.data);
        break;
      case "runtime":
        runtimeLatest.set(frame.data.mission_id, frame.data);
        if (!runtimeLog.some((event) => event.id === frame.data.id)) {
          runtimeLog.push(frame.data);
        }
        break;
    }
  }

  return {
    units: [...units.values()],
    anomalies: [...anomalies.values()],
    allocations: [],
    executionGroups: [...groups.values()],
    dispositions: [...dispositions.values()],
    missions: [],
    missionRuntime: [...runtimeLatest.values()],
    missionRuntimeLog: runtimeLog,
    payloadEvents: [],
    now: Date.parse(capture.started_at) + captureAtMs,
  };
}
