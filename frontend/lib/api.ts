/**
 * Thin REST client to the SWARM OS backend.
 *
 * The dashboard reads the initial state via REST then transitions to live
 * updates over the WebSocket — see `lib/ws.ts`.
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
  | "export_report";

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
};

export type OperatorCommand = {
  id: string;
  action: OperatorAction;
  target: string;
  operator_id: string;
  submitted_at: string;
  status: CommandStatus;
  rejected_reason: RejectedReason | null;
  completed_at: string | null;
};

export type CommandResponse = {
  command_id: string;
  status: CommandStatus | "rejected";
  rejected_reason?: RejectedReason | null;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function post<T>(
  path: string,
  body: unknown,
  operatorId: string
): Promise<{ data: T; status: number }> {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-Operator-Id": operatorId,
    },
    body: JSON.stringify(body),
  });
  let data: T;
  try {
    data = (await res.json()) as T;
  } catch {
    data = {} as T;
  }
  return { data, status: res.status };
}

export const api = {
  health: () => get<{ status: string }>("/health"),

  // ── Phase 1 view-oriented endpoints ─────────────────────────────────────────
  session: () => get<{ session: Session }>("/session"),
  awareness: () => get<{ awareness: AwarenessBreakdown }>("/awareness"),
  docks: () => get<{ docks: DockState[] }>("/docks"),
  sectors: () => get<{ sectors: Sector[] }>("/sectors"),
  units: () => get<{ units: UnitState[] }>("/units"),
  missions: () => get<{ missions: MissionView[] }>("/missions"),
  anomalies: () => get<{ anomalies: AnomalyView[] }>("/anomalies"),
  events: (limit = 100, filter: { kind?: EventKind; sector?: string; agent?: string } = {}) => {
    const q = new URLSearchParams({ limit: String(limit) });
    if (filter.kind) q.set("kind", filter.kind);
    if (filter.sector) q.set("sector", filter.sector);
    if (filter.agent) q.set("agent", filter.agent);
    return get<{ events: TimelineEvent[] }>(`/events?${q.toString()}`);
  },

  // ── Operator intents ────────────────────────────────────────────────────────
  verify: (target: string, operatorId: string) =>
    post<CommandResponse>("/actions/verify", { target }, operatorId),
  holdPatrol: (target: string, operatorId: string) =>
    post<CommandResponse>("/actions/hold-patrol", { target }, operatorId),
  dismiss: (target: string, operatorId: string) =>
    post<CommandResponse>("/actions/dismiss", { target }, operatorId),
  returnUnit: (target: string, operatorId: string) =>
    post<CommandResponse>("/actions/return", { target }, operatorId),
};
