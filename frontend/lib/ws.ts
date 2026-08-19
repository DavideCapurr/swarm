/**
 * WebSocket client to the backend's telemetry fan-out hub.
 *
 * Emits typed events; callers subscribe via `onMessage`. The union below
 * mirrors the kinds projected by `swarm_os.coordinator.SwarmCoordinator` plus
 * the orchestrator-owned allocation/group/disposition/runtime/payload truth
 * frames bridged by the backend.
 *
 * Phase 6.C: the upgrade carries an access token via the `?token=` query
 * parameter (the browser WebSocket API does not let JS set custom
 * headers). The token comes from `lib/auth.tsx` — the socket refuses to
 * dial without one.
 */

import type {
  AllocationDecision,
  AnomalyView,
  AwarenessBreakdown,
  DispositionDecision,
  DockState,
  ExecutionGroup,
  MissionRuntimeEvent,
  MissionView,
  OperatorCommand,
  PayloadEvent,
  Sector,
  Session,
  StreamDescriptor,
  TimelineEvent,
  UnitState,
} from "./api";

function defaultWsUrl(): string {
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.hostname}:8765/ws/telemetry`;
  }
  return "ws://localhost:8765/ws/telemetry";
}

function resolveWsUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_WS_URL;
  if (!envUrl) return defaultWsUrl();
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

const BASE_WS_URL = resolveWsUrl();

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
  | { kind: "stream"; data: StreamDescriptor }
  | { kind: "allocation"; data: AllocationDecision }
  | { kind: "execution_group"; data: ExecutionGroup }
  | { kind: "disposition"; data: DispositionDecision }
  | { kind: "mission_runtime"; data: MissionRuntimeEvent }
  | { kind: "payload"; data: PayloadEvent };

export type WSHandler = (msg: WSMessage) => void;

/**
 * `tokenProvider` returns the *current* access token at dial time.
 * Centralising it here means a refreshed token is picked up on the next
 * reconnect without surgery on every caller.
 */
export type TokenProvider = () => string | null;

export class SwarmSocket {
  private ws?: WebSocket;
  private handlers = new Set<WSHandler>();
  private retry = 0;
  private tokenProvider: TokenProvider;
  private closed = false;

  constructor(tokenProvider: TokenProvider) {
    this.tokenProvider = tokenProvider;
  }

  connect(): void {
    const token = this.tokenProvider();
    if (!token) {
      const delay = Math.min(10_000, 500 * 2 ** this.retry++);
      window.setTimeout(() => {
        if (!this.closed) this.connect();
      }, delay);
      return;
    }
    const url = `${BASE_WS_URL}?token=${encodeURIComponent(token)}`;
    this.ws = new WebSocket(url);
    this.ws.onopen = () => {
      this.retry = 0;
    };
    this.ws.onmessage = (ev) => {
      let msg: WSMessage;
      try {
        msg = JSON.parse(ev.data) as WSMessage;
      } catch {
        return;
      }
      this.handlers.forEach((h) => {
        try {
          h(msg);
        } catch (err) {
          console.error("ws message handler failed", err);
        }
      });
    };
    this.ws.onclose = () => {
      if (this.closed) return;
      const delay = Math.min(10_000, 500 * 2 ** this.retry++);
      window.setTimeout(() => {
        if (!this.closed) this.connect();
      }, delay);
    };
  }

  close(): void {
    this.closed = true;
    this.ws?.close();
    this.ws = undefined;
  }

  onMessage(h: WSHandler): () => void {
    this.handlers.add(h);
    return () => this.handlers.delete(h);
  }
}
