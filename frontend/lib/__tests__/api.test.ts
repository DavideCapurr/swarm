/**
 * Phase 6.J — Vitest coverage on `lib/api.ts` critical-path surface.
 *
 * Targets the auth-hook plumbing (token attachment + 401 forced
 * logout), the stream-URL allowlist (security boundary), and the
 * emergency intent helper so the gate stays meaningful even if the
 * REST surface grows.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  api,
  EMERGENCY_CONFIRMATION_PHRASE,
  isAllowedSimFeedPath,
  isAllowedStreamUrl,
} from "@/lib/api";

type FetchMock = ReturnType<typeof vi.fn>;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("isAllowedStreamUrl", () => {
  it("accepts rtsps + https schemes", () => {
    expect(isAllowedStreamUrl("rtsps://cam.local/stream")).toBe(true);
    expect(isAllowedStreamUrl("https://media.example/stream.m3u8")).toBe(true);
  });

  it("rejects every other scheme (defense in depth alongside backend)", () => {
    expect(isAllowedStreamUrl("rtsp://cam.local/stream")).toBe(false);
    expect(isAllowedStreamUrl("http://cam.local/stream")).toBe(false);
    expect(isAllowedStreamUrl("javascript:alert(1)")).toBe(false);
    expect(isAllowedStreamUrl("file:///etc/passwd")).toBe(false);
  });

  it("returns false on malformed input", () => {
    expect(isAllowedStreamUrl("not a url")).toBe(false);
    expect(isAllowedStreamUrl("")).toBe(false);
  });
});

describe("isAllowedSimFeedPath", () => {
  it("accepts a same-origin /sim-feed/ path", () => {
    expect(isAllowedSimFeedPath("/sim-feed/unit-003-pov.mp4")).toBe(true);
  });

  it("rejects absolute and protocol-relative URLs (no external origin)", () => {
    expect(isAllowedSimFeedPath("https://evil.example/sim-feed/x.mp4")).toBe(false);
    expect(isAllowedSimFeedPath("//evil.example/sim-feed/x.mp4")).toBe(false);
  });

  it("rejects same-origin paths outside the /sim-feed/ prefix", () => {
    expect(isAllowedSimFeedPath("/api/secret")).toBe(false);
    expect(isAllowedSimFeedPath("/")).toBe(false);
  });

  it("rejects traversal and control characters", () => {
    expect(isAllowedSimFeedPath("/sim-feed/../../etc/passwd")).toBe(false);
    expect(isAllowedSimFeedPath("/sim-feed/x.mp4\r\nX-Inject: 1")).toBe(false);
    expect(isAllowedSimFeedPath("/sim-feed/..\\x.mp4")).toBe(false);
  });

  it("returns false on empty input", () => {
    expect(isAllowedSimFeedPath("")).toBe(false);
  });
});

describe("api auth-hook plumbing", () => {
  let fetchMock: FetchMock;
  let onUnauthorized: () => void;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    onUnauthorized = vi.fn();
    api.setAuthHooks({
      getAccessToken: () => "test-token",
      onUnauthorized,
    });
  });

  afterEach(() => {
    api.setAuthHooks(null);
    vi.unstubAllGlobals();
  });

  it("attaches Bearer header on every protected GET", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ units: [] }));
    await api.units();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer test-token"
    );
  });

  it("forces logout on a hard 401 (GET)", async () => {
    fetchMock.mockResolvedValueOnce(new Response("", { status: 401 }));
    await expect(api.awareness()).rejects.toThrow("401");
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("forces logout on a hard 401 (POST)", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response("", { status: 401, headers: { "Content-Type": "text/plain" } })
    );
    const res = await api.verify("anomaly:abc");
    expect(res.status).toBe(401);
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("posts emergencyRtlAll with the canonical phrase", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse({ command_id: "c-1", status: "accepted" }, 202)
    );
    const res = await api.emergencyRtlAll(EMERGENCY_CONFIRMATION_PHRASE);
    expect(res.status).toBe(202);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      confirm: true,
      confirmation_phrase: EMERGENCY_CONFIRMATION_PHRASE,
    });
  });

  it("omits Authorization when no auth hook is registered", async () => {
    api.setAuthHooks(null);
    fetchMock.mockResolvedValueOnce(jsonResponse({ status: "ok" }));
    await api.health();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });
});
