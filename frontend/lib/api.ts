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

// Evidence layer — provenance of the triggering signal. Mirrors
// core/swarm_core/messages.py::AnomalySource.
export type AnomalySource =
  | "drone_cv"
  | "thermal_sat"
  | "fire_detector"
  | "unknown";

export type SensorKind = "RGB" | "THERMAL" | "MULTISPECTRAL" | "LIDAR";

// The *why* behind an anomaly. `headline` is the server-built, confidence-bound
// one-liner — the Console renders it; it never composes operational truth.
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
  // Phase 7.C — boot-time gate on the deterministic autonomy baseline.
  // True when SWARM_AUTONOMY_BASELINE=1 or a scenario YAML opted in.
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
  // Evidence layer — the *why* (source + triggering signal + server headline).
  // Nullable: pre-evidence anomalies and existing fixtures leave it undefined.
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
  // Phase 7.C — mirrors OperatorCommand.source; the EventFeed renders an
  // "auto" kind label (Orbital Blue) when this is "autonomy".
  source: "operator" | "autonomy";
};

export type OperatorCommand = {
  id: string;
  action: OperatorAction;
  target: string;
  operator_id: string;
  // Phase 7.B — "operator" or "autonomy". Defaults to "operator" on every
  // existing API surface; Phase 7.C renders the AUTO eyebrow off this field.
  source: "operator" | "autonomy";
  // Phase 7.C — autonomy rule label ("R1" / "R2" / "R3") when the command
  // came from the deterministic baseline. Null for every operator command.
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

// ── Phase 5 stream descriptors (mirror core/swarm_core/streams.py) ───────────

export type StreamProtocol = "rtsps" | "https";

export type StreamDescriptor = {
  agent_id: string;
  available: boolean;
  url: string | null;
  protocol: StreamProtocol | null;
  codec: string | null;
  ts: string;
};

/** Client-side allowlist — same set as the backend's `ALLOWED_STREAM_SCHEMES`. */
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

// ── Auth hooks (installed by lib/auth.tsx) ─────────────────────────────────────

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
  if (res.status === 401) {
    _authHooks?.onUnauthorized();
  }
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

  // ── Phase 1 view-oriented endpoints ─────────────────────────────────────────
  session: () => get<{ session: Session }>("/session"),
  awareness: () => get<{ awareness: AwarenessBreakdown }>("/awareness"),
  docks: () => get<{ docks: DockState[] }>("/docks"),
  sectors: () => get<{ sectors: Sector[] }>("/sectors"),
  units: () => get<{ units: UnitState[] }>("/units"),
  missions: () => get<{ missions: MissionView[] }>("/missions"),
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

  // ── Operator intents (auth header now carries identity + role) ─────────────
  verify: (target: string) =>
    post<CommandResponse>("/actions/verify", { target }),
  holdPatrol: (target: string) =>
    post<CommandResponse>("/actions/hold-patrol", { target }),
  dismiss: (target: string) =>
    post<CommandResponse>("/actions/dismiss", { target }),
  returnUnit: (target: string) =>
    post<CommandResponse>("/actions/return", { target }),
  // Phase 6.G — fleet-wide stop. Commander-only. The backend requires
  // both fields; the modal that calls this passes them after the
  // operator types the confirmation phrase.
  emergencyRtlAll: (confirmationPhrase: string) =>
    post<CommandResponse>("/actions/emergency-rtl-all", {
      confirm: true,
      confirmation_phrase: confirmationPhrase,
    }),
};

// Phase 6.G — exported so the EmergencyStop modal and the dispatcher can
// share the canonical phrase. Mirrors backend ``EMERGENCY_CONFIRMATION``.
export const EMERGENCY_CONFIRMATION_PHRASE = "RETURN ALL UNITS";
