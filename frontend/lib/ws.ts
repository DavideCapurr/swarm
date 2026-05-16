/**
 * WebSocket client to the backend's telemetry fan-out hub.
 *
 * Emits typed events; callers subscribe via `onMessage`. The union below
 * mirrors the kinds projected by `swarm_os.coordinator.SwarmCoordinator`.
 */

import type {
  AnomalyView,
  AwarenessBreakdown,
  DockState,
  MissionView,
  OperatorCommand,
  Sector,
  Session,
  StreamDescriptor,
  TimelineEvent,
  UnitState,
} from "./api";

function defaultWsUrl(): string {
  // Derive from the current page so the dashboard works when opened over the
  // LAN (e.g. http://192.168.x.x:3000) without an explicit NEXT_PUBLIC_WS_URL.
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.hostname}:8765/ws/telemetry`;
  }
  return "ws://localhost:8765/ws/telemetry";
}

function resolveWsUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (!envUrl) return defaultWsUrl();
  // Ignore a baked-in localhost env value when the page itself is being
  // served from a different host (LAN access): the browser would otherwise
  // try to dial its own machine instead of the backend.
  if (typeof window !== "undefined") {
    try {
      const u = new URL(envUrl);
      const local = u.hostname === "localhost" || u.hostname === "127.0.0.1";
      const pageLocal =
        window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";
      if (local && !pageLocal) return defaultWsUrl();
    } catch {
      /* fall through */
    }
  }
  return envUrl;
}

const WS_URL = resolveWsUrl();

export type WSMessage =
  | { kind: "session"; data: Session }
  | { kind: "unit"; data: UnitState }
  | { kind: "dock"; data: DockState }
  | { kind: "sector"; data: Sector }
  | { kind: "awareness"; data: AwarenessBreakdown }
  | { kind: "mission"; data: MissionView }
  | { kind: "anomaly_view"; data: AnomalyView }
  | { kind: "event"; data: TimelineEvent }
  | { kind: "operator"; data: OperatorCommand }
  | { kind: "stream"; data: StreamDescriptor };

export type WSHandler = (msg: WSMessage) => void;

export class SwarmSocket {
  private ws?: WebSocket;
  private handlers = new Set<WSHandler>();
  private retry = 0;

  connect(): void {
    this.ws = new WebSocket(WS_URL);
    this.ws.onopen = () => {
      this.retry = 0;
    };
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WSMessage;
        this.handlers.forEach((h) => h(msg));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onclose = () => {
      // Backoff reconnect, capped at ~10 s.
      const delay = Math.min(10_000, 500 * 2 ** this.retry++);
      setTimeout(() => this.connect(), delay);
    };
  }

  close(): void {
    this.ws?.close();
    this.ws = undefined;
  }

  onMessage(h: WSHandler): () => void {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }
}
