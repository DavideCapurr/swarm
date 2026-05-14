/**
 * Thin REST client to the SWARM OS backend.
 *
 * The dashboard reads the initial state via REST then transitions to live
 * updates over the WebSocket — see `lib/ws.ts`.
 */

function defaultApiUrl(): string {
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
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

export type Geo = { lat: number; lon: number; alt_m: number };

export type FleetMember = {
  agent_id: string;
  vendor: string;
  model: string;
  fsm_state: string;
  battery_pct: number;
  geo: Geo;
  current_mission_id?: string | null;
  link_quality?: number;
};

export type Anomaly = {
  id: string;
  kind: string;
  geo: Geo;
  confidence: number;
  verified: boolean;
  ts: string;
};

export type Telemetry = {
  agent_id: string;
  ts: string;
  geo: Geo;
  velocity_mps: number;
  battery_pct: number;
  link_quality: number;
};

export type EventLog = {
  kind: string;
  [k: string]: unknown;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const api = {
  health: () => get<{ status: string }>("/health"),
  fleet: () => get<{ fleet: FleetMember[] }>("/fleet"),
  anomalies: () => get<{ anomalies: Anomaly[] }>("/anomalies"),
  telemetryLatest: () =>
    get<{ telemetry: Record<string, Telemetry> }>("/telemetry/latest"),
  events: (limit = 100) => get<{ events: EventLog[] }>(`/events?limit=${limit}`),
};
