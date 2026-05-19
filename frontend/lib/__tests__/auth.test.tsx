/**
 * Phase 6.J — Vitest coverage on `lib/auth.tsx`.
 *
 * Targets the role-rank helper and the AuthProvider hydration path
 * (loading → authenticated on a fresh localStorage session; loading
 * → anonymous when nothing is persisted). The full login + silent
 * refresh path is exercised through the EmergencyStop test below,
 * which depends on `useRole`.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import {
  AuthProvider,
  canDo,
  useAuth,
  useRole,
  type Role,
  type Session,
} from "@/lib/auth";

const STORAGE_KEY = "swarm.session.v1";

function makeSession(overrides: Partial<Session> = {}): Session {
  return {
    accessToken: "access-token-abc",
    refreshToken: "refresh-token-def",
    expiresAt: Date.now() + 15 * 60 * 1_000,
    role: "operator",
    operatorId: "op-test",
    siteId: "vineyard-01",
    mfa: false,
    ...overrides,
  };
}

function RoleProbe() {
  const role = useRole();
  return <span data-testid="role">{role ?? "none"}</span>;
}

function StatusProbe() {
  const { state } = useAuth();
  return <span data-testid="status">{state.status}</span>;
}

describe("canDo (role rank)", () => {
  const cases: Array<[Role | null, Role, boolean]> = [
    [null, "viewer", false],
    ["viewer", "viewer", true],
    ["viewer", "operator", false],
    ["viewer", "commander", false],
    ["operator", "viewer", true],
    ["operator", "operator", true],
    ["operator", "commander", false],
    ["commander", "viewer", true],
    ["commander", "operator", true],
    ["commander", "commander", true],
  ];
  it.each(cases)(
    "canDo(%s, %s) === %s",
    (have, want, expected) => {
      expect(canDo(have, want)).toBe(expected);
    }
  );
});

describe("AuthProvider hydration", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("boots into 'anonymous' when nothing is persisted", async () => {
    render(
      <AuthProvider>
        <StatusProbe />
      </AuthProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anonymous")
    );
  });

  it("hydrates to 'authenticated' from a fresh localStorage session", async () => {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(makeSession()));
    render(
      <AuthProvider>
        <StatusProbe />
        <RoleProbe />
      </AuthProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("authenticated")
    );
    expect(screen.getByTestId("role").textContent).toBe("operator");
  });

  it("drops a malformed storage payload and lands anonymous", async () => {
    window.localStorage.setItem(STORAGE_KEY, "{not-json");
    render(
      <AuthProvider>
        <StatusProbe />
      </AuthProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anonymous")
    );
  });

  it("attempts silent refresh on an expired session and falls back to anonymous on 401", async () => {
    const expired = makeSession({ expiresAt: Date.now() - 60_000 });
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(expired));
    const fetchMock = vi.fn().mockResolvedValueOnce(
      new Response("", { status: 401 })
    );
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => {
      render(
        <AuthProvider>
          <StatusProbe />
        </AuthProvider>
      );
    });

    await waitFor(() =>
      expect(screen.getByTestId("status").textContent).toBe("anonymous")
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/refresh"),
      expect.objectContaining({ method: "POST" })
    );
    expect(window.localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
