/**
 * Phase 6.J — Vitest coverage on the SwarmSocket WS client.
 *
 * Targets the token plumbing (no dial when the auth provider hasn't
 * hydrated yet), the message-router fan-out, and the malformed-frame
 * guard. WebSocket is faked at the global level so the test never
 * touches a real socket.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SwarmSocket, type WSMessage } from "@/lib/ws";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  static readonly OPEN = 1;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  close = vi.fn();

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  vi.useFakeTimers();
  vi.stubGlobal("WebSocket", FakeWebSocket as unknown as typeof WebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("SwarmSocket", () => {
  it("does not dial when no token is available yet", () => {
    const socket = new SwarmSocket(() => null);
    socket.connect();
    expect(FakeWebSocket.instances).toHaveLength(0);
    socket.close();
  });

  it("dials with ?token= when a token is available", () => {
    const socket = new SwarmSocket(() => "abc.def.ghi");
    socket.connect();
    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain("token=abc.def.ghi");
    socket.close();
  });

  it("routes parsed messages to every registered handler", () => {
    const socket = new SwarmSocket(() => "tok");
    socket.connect();
    const seen: WSMessage[] = [];
    const off = socket.onMessage((msg) => seen.push(msg));

    FakeWebSocket.instances[0].onmessage?.({
      data: JSON.stringify({
        kind: "awareness",
        data: { score: 70, factors: {}, blind_spot_sectors: [], stale_sectors: [], risk_state: "rest", mode: "rest", verifying_agent: null, ts: "x" },
      }),
    });
    expect(seen).toHaveLength(1);
    expect(seen[0].kind).toBe("awareness");

    off();
    FakeWebSocket.instances[0].onmessage?.({
      data: JSON.stringify({ kind: "awareness", data: {} }),
    });
    expect(seen).toHaveLength(1); // handler was unregistered

    socket.close();
  });

  it("ignores malformed frames silently (no throw)", () => {
    const socket = new SwarmSocket(() => "tok");
    socket.connect();
    expect(() => {
      FakeWebSocket.instances[0].onmessage?.({ data: "{not-json" });
    }).not.toThrow();
    socket.close();
  });

  it("close() prevents the auto-reconnect onclose loop", () => {
    const socket = new SwarmSocket(() => "tok");
    socket.connect();
    socket.close();
    // The onclose callback after a manual close must not schedule a reconnect.
    FakeWebSocket.instances[0].onclose?.();
    vi.runOnlyPendingTimers();
    expect(FakeWebSocket.instances).toHaveLength(1); // no new dial
  });
});
