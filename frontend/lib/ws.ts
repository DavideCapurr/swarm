/**
 * WebSocket client to the backend's telemetry fan-out hub.
 *
 * Emits typed events; callers subscribe via `onMessage`.
 */

function defaultWsUrl(): string {
  // Derive from the current page so the dashboard works when opened over the
  // LAN (e.g. http://192.168.x.x:3000) without an explicit NEXT_PUBLIC_WS_URL.
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.hostname}:8000/ws/telemetry`;
  }
  return "ws://localhost:8000/ws/telemetry";
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? defaultWsUrl();

export type WSMessage =
  | { kind: "telemetry"; data: import("./api").Telemetry }
  | { kind: "fleet"; data: import("./api").FleetMember }
  | { kind: "anomaly"; data: import("./api").Anomaly }
  | { kind: "progress"; data: { mission_id: string; phase: string; progress_pct: number } };

export type WSHandler = (msg: WSMessage) => void;

export type WSLifecycle = "open" | "close";
export type WSLifeHandler = (ev: WSLifecycle) => void;

export class SwarmSocket {
  private ws?: WebSocket;
  private handlers = new Set<WSHandler>();
  private lifeHandlers = new Set<WSLifeHandler>();
  private retry = 0;
  private closed = false;

  connect(): void {
    if (typeof window === "undefined") return; // SSR safety
    // eslint-disable-next-line no-console
    console.info("[swarm] ws connecting", WS_URL);
    this.ws = new WebSocket(WS_URL);
    this.ws.onopen = () => {
      this.retry = 0;
      // eslint-disable-next-line no-console
      console.info("[swarm] ws open");
      this.lifeHandlers.forEach((h) => h("open"));
    };
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WSMessage;
        this.handlers.forEach((h) => h(msg));
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onerror = (e) => {
      // eslint-disable-next-line no-console
      console.warn("[swarm] ws error", e);
    };
    this.ws.onclose = () => {
      // eslint-disable-next-line no-console
      console.info("[swarm] ws closed");
      this.lifeHandlers.forEach((h) => h("close"));
      if (this.closed) return;
      const delay = Math.min(10_000, 500 * 2 ** this.retry++);
      setTimeout(() => this.connect(), delay);
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

  onLifecycle(h: WSLifeHandler): () => void {
    this.lifeHandlers.add(h);
    return () => this.lifeHandlers.delete(h);
  }
}
