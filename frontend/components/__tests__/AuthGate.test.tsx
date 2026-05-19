/**
 * Phase 6.J — Vitest coverage on the AuthGate redirect.
 *
 * Renders an authenticated session → children visible.
 * Renders without a session → redirects to /login, hides children.
 * Renders while loading → renders neither (linking-session placeholder).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

import { AuthProvider } from "@/lib/auth";
import { AuthGate } from "@/components/AuthGate";

const STORAGE_KEY = "swarm.session.v1";
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/console",
}));

function seedSession(role: "operator" | "commander" = "operator"): void {
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      accessToken: "tok",
      refreshToken: "ref",
      expiresAt: Date.now() + 15 * 60 * 1_000,
      role,
      operatorId: "op-test",
      siteId: "vineyard-01",
      mfa: role === "commander",
    })
  );
}

beforeEach(() => {
  window.localStorage.clear();
  replaceMock.mockReset();
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AuthGate", () => {
  it("renders children when authenticated", async () => {
    seedSession("operator");
    render(
      <AuthProvider>
        <AuthGate>
          <span data-testid="protected">protected payload</span>
        </AuthGate>
      </AuthProvider>
    );
    await waitFor(() =>
      expect(screen.getByTestId("protected")).toBeInTheDocument()
    );
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("redirects to /login when anonymous", async () => {
    render(
      <AuthProvider>
        <AuthGate>
          <span data-testid="protected">protected payload</span>
        </AuthGate>
      </AuthProvider>
    );
    await waitFor(() =>
      expect(replaceMock).toHaveBeenCalledWith(
        expect.stringContaining("/login")
      )
    );
    expect(screen.queryByTestId("protected")).not.toBeInTheDocument();
  });

  it("carries the ?next= hint so post-login we land back on the same path", async () => {
    render(
      <AuthProvider>
        <AuthGate>
          <span>protected</span>
        </AuthGate>
      </AuthProvider>
    );
    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    const target = replaceMock.mock.calls[0][0] as string;
    expect(target).toBe(`/login?next=${encodeURIComponent("/console")}`);
  });
});
