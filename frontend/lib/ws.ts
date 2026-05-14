/**
 * WebSocket client to the backend's telemetry fan-out hub.
 *
 * Emits typed events; callers subscribe via `onMessage`.
 */

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/telemetry";

export type WSMessage =
  | { kind: "telemetry"; data: import("./api").Telemetry }
  | { kind: "fleet"; data: import("./api").FleetMember }
  | { kind: "anomaly"; data: import("./api").Anomaly }
  | { kind: "progress"; data: { mission_id: string; phase: string; progress_pct: number } };

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
