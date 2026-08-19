/**
 * Thin REST client to the SWARM OS backend.
 *
 * The dashboard reads the initial state via REST then transitions to live
 * updates over the WebSocket — see `lib/ws.ts`.
 *
 * Phase 6.C: every protected route carries `Authorization: Bearer <jwt>`.
 * The auth hooks below are installed by `lib/auth.tsx`; the API client
 * stays React-free so server-rendered code can still build without
 * blowing up at import time.
 */

function defaultApiUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8765`;
  }
  return "http://localhost:8765";
}

function resolveApiUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!envUrl) return defaultApiUrl();
  if (typeof window !== "undefined") {
    try {
      const u = new URL(envUrl);
      const local = u.hostname === "localhost" || u.hostname === "127.0.0.1";
      const pageLocal =
        window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      if (local && !pageLocal) return defaultApiUrl();
    } catch {
      /* fall through */
    }
  }
  return envUrl;
}

const API_URL = resolveApiUrl();
export const AUTH_API_URL = API_URL;

// ── Primitives ─────────────────────────────────────────────────────────────────

export type Geo = { lat: number; lon: number; alt_m: number };

// ── Enums (mirror core/swarm_core/messages.py) ────────────────────────────────

export type AgentState =
  | "DOCKED"
  | "TAKEOFF"
  | "EN_ROUTE"
  | "ON_STATION"
  | "RTL"
  | "LANDING"
  | "DOCKING"
  | "OFFLINE"
  | "ERROR";

export type AnomalyKind = "SMOKE" | "FIRE" | "HEAT_SPOT" | "INTRUSION" | "UNKNOWN";

export type AnomalySource =
  | "drone_cv"
  | "thermal_sat"
  | "fire_detector"
  | "unknown";

export type SensorKind = "RGB" | "THERMAL" | "MULTISPECTRAL" | "LIDAR";

export type AnomalyEvidence = {
  source: AnomalySource;
  sensor: SensorKind;
  label: string | null;
  metric: string | null;
  value: number | null;
  baseline: number | null;
  unit: string | null;
  headline: string;
  simulated: boolean;
};

export type OperatingMode =
  | "rest"
  | "patrol"
  | "verification"
  | "escalation"
  | "maintenance";

export type RiskBand = "low" | "elevated" | "high";
export type ConfidenceBand = "low-confidence" | "elevated" | "verified";
export type DockStatus = "online" | "degraded" | "offline" | "maintenance";
export type PowerStatus = "online" | "degraded" | "offline";
export type SectorState = "idle" | "covered" | "stale" | "blind" | "anomaly";
export type RiskState = "rest" | "aware" | "elevated";
export type AnomalyState =
  | "pending"
  | "verifying"
  | "verified"
  | "dismissed"
  | "escalated"
  | "marked_known";
export type MissionPhase =
  | "pending"
  | "bidding"
  | "accepted"
  | "en_route"
  | "on_station"
  | "returning"
  | "done"
  | "failed";

export type EventKind =
  | "patrol"
  | "anomaly"
  | "verify"
  | "operator"
  | "dock"
  | "link"
  | "sector"
  | "mission"
  | "system";

export type OperatorAction =
  | "verify"
  | "hold_patrol"
  | "dismiss"
  | "return"
  | "increase_scan_freq"
  | "mark_known"
  | "escalate"
  | "export_report"
  | "emergency_rtl_all";

export type CommandStatus =
  | "submitted"
  | "accepted"
  | "rejected"
  | "in_flight"
  | "completed"
  | "timed_out";

export type RejectedReason =
  | "target_not_found"
  | "invalid_target_kind"
  | "unauthorized"
  | "outside_geofence"
  | "battery_too_low"
  | "link_too_weak"
  | "weather_lock"
  | "mission_conflict"
  | "policy_deny"
  | "rate_limited"
  | "internal_error";

// ── Phase 1 Console-facing aggregates ─────────────────────────────────────────

export type Session = {
  id: string;
  label: string;
  site_id: string;
  autonomy_enabled: boolean;
  started_at: string;
  ts: string;
};

export type UnitState = {
  agent_id: string;
  vendor: string;
  model: string;
  fsm_state: AgentState;
  battery_pct: number;
  geo: Geo;
  current_mission_id: string | null;
  current_sector_id: string | null;
  link_quality: number;
  heading_deg: number;
  altitude_agl_m: number;
  dock_id: string | null;
  ts: string;
};

export type DockState = {
  dock_id: string;
  status: DockStatus;
  units_docked: number;
  units_total: number;
  slots_available: number;
  slots_charging: number;
  power_status: PowerStatus;
  weather_lock: boolean;
  wind_mps: number | null;
  visibility_km: number | null;
  temp_c: number | null;
  next_patrol_at: string | null;
  primary: boolean;
  ts: string;
};

export type Sector = {
  id: string;
  label: string;
  polygon: Geo[];
  centroid: Geo;
  state: SectorState;
  last_visited_at: string | null;
  last_visited_by: string | null;
  pending_anomaly_ids: string[];
  confidence: number;
  risk_band: RiskBand;
  ts: string;
};

export type AwarenessBreakdown = {
  score: number;
  factors: Record<string, number>;
  blind_spot_sectors: string[];
  stale_sectors: string[];
  risk_state: RiskState;
  mode: OperatingMode;
  verifying_agent: string | null;
  ts: string;
};

export type MissionView = {
  id: string;
  kind: string;
  assigned_agent: string | null;
  sector_id: string | null;
  phase: MissionPhase;
  progress_pct: number;
  eta_s: number | null;
  waypoints: Geo[];
  track: Geo[];
  ts: string;
};

export type AnomalyView = {
  id: string;
  kind: AnomalyKind;
  geo: Geo;
  sector_id: string | null;
  confidence: number;
  band: ConfidenceBand;
  state: AnomalyState;
  detected_at: string;
  detected_by: string | null;
  verifying_agent: string | null;
  evidence?: AnomalyEvidence | null;
  ts: string;
};

export type TimelineEvent = {
  id: string;
  kind: EventKind;
  ts: string;
  sector_id: string | null;
  agent_id: string | null;
  mission_id: string | null;
  anomaly_id: string | null;
  dock_id: string | null;
  confidence: number | null;
  body: string;
  action_label: string | null;
  source: "operator" | "autonomy";
};

export type OperatorCommand = {
  id: string;
  action: OperatorAction;
  target: string;
  operator_id: string;
  source: "operator" | "autonomy";
  rule?: string | null;
  submitted_at: string;
  accepted_at: string | null;
  in_flight_at: string | null;
  status: CommandStatus;
  rejected_reason: RejectedReason | null;
  completed_at: string | null;
  mission_id: string | null;
  ts: string;
};

export type CommandResponse = {
  command_id: string;
  status: CommandStatus | "rejected";
  rejected_reason?: RejectedReason | null;
  mission_id?: string | null;
};

// ── Allocator / orchestration / runtime / payload truth frames ───────────────

export type AllocationExclusionReason = "BUSY" | "LOW_BATTERY" | "UNAVAILABLE";

export type AllocationScoreBreakdown = {
  distance_m: number;
  distance_score: number;
  battery_pct: number;
  battery_score: number;
  priority: number;
  priority_score: number;
  busy_penalty: number;
};

export type AllocationEligibleUnit = {
  agent_id: string;
  fsm_state: AgentState;
  battery_pct: number;
  score: number;
  score_breakdown: AllocationScoreBreakdown;
};

export type AllocationExcludedUnit = {
  agent_id: string;
  fsm_state: AgentState;
  battery_pct: number;
  reason: AllocationExclusionReason;
  active_mission_id: string | null;
};

export type AllocationDecision = {
  mission_id: string;
  mission_kind: string;
  anomaly_id: string | null;
  mode: "auction" | "diversion" | "no_award";
  eligible_units: AllocationEligibleUnit[];
  excluded_units: AllocationExcludedUnit[];
  winner_agent_id: string | null;
  winner_score: number | null;
  diverted_from_mission_id?: string | null;
  ts: string;
};

export type MissionRuntimeEvidence =
  | "mavlink_mission_item_reached"
  | "mavlink_rtl_command_acknowledged";

export type MissionRuntimeEvent = {
  id: string;
  mission_id: string;
  agent_id: string;
  phase: string;
  progress_pct: number;
  evidence: MissionRuntimeEvidence | null;
  error: string | null;
  ts: string;
};

export type PayloadActionKind =
  | "light_on"
  | "light_off"
  | "play_message"
  | "stop_message";
export type PayloadActionStatus =
  | "acknowledged"
  | "confirmed"
  | "simulated"
  | "unsupported"
  | "failed";
export type PayloadExecutionMode =
  | "simulated"
  | "mavlink_ack"
  | "mavlink_output_confirmed";
export type PayloadMessage = "restricted_area";

export type PayloadEvent = {
  id: string;
  mission_id: string;
  anomaly_id: string | null;
  action_id: string;
  agent_id: string;
  kind: PayloadActionKind;
  status: PayloadActionStatus;
  execution_mode: PayloadExecutionMode | null;
  light_on: boolean | null;
  speaker_active: boolean | null;
  message: PayloadMessage | null;
  error_code: string | null;
  ts: string;
};

export type ExecutionGroupState =
  | "FORMING"
  | "ACTIVE"
  | "DEGRADED"
  | "COMPLETED"
  | "FAILED";

export type ExecutionGroupMemberState =
  | "ASSIGNED"
  | "ACTIVE"
  | "COMPLETED"
  | "FAILED"
  | "REPLACED"
  | "DIVERTED";

export type ExecutionGroupMember = {
  agent_id: string;
  role: string;
  mission_id: string;
  state: ExecutionGroupMemberState;
  score: number;
  score_breakdown: Record<string, number>;
  replaces_agent_id: string | null;
  diverted_from_mission_id?: string | null;
  diverted_from_objective_id?: string | null;
  ts: string;
};

export type ExecutionGroup = {
  id: string;
  objective_mission_id: string;
  objective_kind: string;
  anomaly_id: string | null;
  reinforces_group_id?: string | null;
  requested_members: number;
  members: ExecutionGroupMember[];
  state: ExecutionGroupState;
  failure_reason: string | null;
  ts: string;
};

export type DispositionAssignment = {
  group_id: string;
  agent_id: string;
  role: string;
  mission_id: string;
  geo: Geo;
};

/** SwarmOS-owned station geometry. The Console must not recompute these slots. */
export type DispositionDecision = {
  objective_mission_id: string;
  revision: number;
  reason: string;
  center: Geo;
  active_members: number;
  radius_m: number;
  assignments: DispositionAssignment[];
  ts: string;
};

// ── Phase 5 stream descriptors ────────────────────────────────────────────────

export type StreamProtocol = "rtsps" | "https";

export type StreamDescriptor = {
  agent_id: string;
  available: boolean;
  simulated: boolean;
  url: string | null;
  protocol: StreamProtocol | null;
  codec: string | null;
  ts: string;
};

export const ALLOWED_STREAM_SCHEMES: ReadonlySet<string> = new Set([
  "rtsps",
  "https",
]);

export function isAllowedStreamUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    const scheme = parsed.protocol.replace(/:$/, "").toLowerCase();
    return ALLOWED_STREAM_SCHEMES.has(scheme);
  } catch {
    return false;
  }
}

export const SIM_FEED_PREFIX = "/sim-feed/";

export function isAllowedSimFeedPath(path: string): boolean {
  if (typeof path !== "string" || path.length === 0) return false;
  if (/[\r\n\0\\]/.test(path)) return false;
  let resolved: URL;
  try {
    resolved = new URL(path, "https://console.invalid");
  } catch {
    return false;
  }
  if (resolved.origin !== "https://console.invalid") return false;
  if (!path.startsWith(SIM_FEED_PREFIX)) return false;
  if (path.split("/").includes("..")) return false;
  return true;
}

// ── Auth hooks ────────────────────────────────────────────────────────────────

type AuthHooks = {
  getAccessToken: () => string | null;
  onUnauthorized: () => void;
};

let _authHooks: AuthHooks | null = null;

function authHeaders(): Record<string, string> {
  const token = _authHooks?.getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (res.status === 401) {
    _authHooks?.onUnauthorized();
    throw new Error("401");
  }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function post<T>(
  path: string,
  body: unknown
): Promise<{ data: T; status: number }> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
    },
    body: JSON.stringify(body),
  });
  if (res.status === 401) _authHooks?.onUnauthorized();
  let data: T;
  try {
    data = (await res.json()) as T;
  } catch {
    data = {} as T;
  }
  return { data, status: res.status };
}

export const api = {
  setAuthHooks: (hooks: AuthHooks | null): void => {
    _authHooks = hooks;
  },

  health: () => get<{ status: string }>("/health"),
  session: () => get<{ session: Session }>("/session"),
  awareness: () => get<{ awareness: AwarenessBreakdown }>("/awareness"),
  docks: () => get<{ docks: DockState[] }>("/docks"),
  sectors: () => get<{ sectors: Sector[] }>("/sectors"),
  units: () => get<{ units: UnitState[] }>("/units"),
  missions: () => get<{ missions: MissionView[] }>("/missions"),
  allocations: () => get<{ allocations: AllocationDecision[] }>("/allocations"),
  executionGroups: () =>
    get<{ execution_groups: ExecutionGroup[] }>("/execution-groups"),
  dispositions: () =>
    get<{ dispositions: DispositionDecision[] }>("/dispositions"),
  missionRuntime: () =>
    get<{ mission_runtime: MissionRuntimeEvent[] }>("/mission-runtime"),
  payloadEvents: (limit = 200) =>
    get<{ payload_events: PayloadEvent[] }>(`/payload-events?limit=${limit}`),
  commands: (limit = 100) =>
    get<{ commands: OperatorCommand[] }>(`/commands?limit=${limit}`),
  anomalies: () => get<{ anomalies: AnomalyView[] }>("/anomalies"),
  events: (limit = 100, filter: { kind?: EventKind; sector?: string; agent?: string } = {}) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (filter.kind) q.set("kind", filter.kind);
    if (filter.sector) q.set("sector", filter.sector);
    if (filter.agent) q.set("agent", filter.agent);
    return get<{ events: TimelineEvent[] }>(`/events?${q.toString()}`);
  },

  verify: (target: string) => post<CommandResponse>("/actions/verify", { target }),
  holdPatrol: (target: string) => post<CommandResponse>("/actions/hold-patrol", { target }),
  dismiss: (target: string) => post<CommandResponse>("/actions/dismiss", { target }),
  returnUnit: (target: string) => post<CommandResponse>("/actions/return", { target }),
  emergencyRtlAll: (confirmationPhrase: string) =>
    post<CommandResponse>("/actions/emergency-rtl-all", {
      confirm: true,
      confirmation_phrase: confirmationPhrase,
    }),
};

export const EMERGENCY_CONFIRMATION_PHRASE = "RETURN ALL UNITS";
