/**
 * Phase 6.J — Vitest coverage on the EmergencyStop component.
 *
 * Safety-critical surface: only commander can fire the intent, the
 * confirmation phrase must match `RETURN ALL UNITS` exactly, the
 * Confirm button stays disabled until the typed phrase matches, and
 * Esc closes the modal. The actual REST call is intercepted at the
 * api module boundary — we own that contract.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AuthProvider } from "@/lib/auth";
import { EmergencyStop } from "@/components/EmergencyStop";
import { EMERGENCY_CONFIRMATION_PHRASE } from "@/lib/api";

const STORAGE_KEY = "swarm.session.v1";

function seedSession(role: "viewer" | "operator" | "commander"): void {
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      accessToken: "access-token",
      refreshToken: "refresh-token",
      expiresAt: Date.now() + 15 * 60 * 1_000,
      role,
      operatorId: "op-test",
      siteId: "vineyard-01",
      mfa: role === "commander",
    })
  );
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  window.localStorage.clear();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

async function renderWithRole(role: "viewer" | "operator" | "commander") {
  seedSession(role);
  const result = render(
    <AuthProvider>
      <EmergencyStop />
    </AuthProvider>
  );
  // Let the AuthProvider hydrate so useRole returns the seeded role.
  await screen.findByTestId("emergency-stop-trigger");
  return result;
}

describe("EmergencyStop", () => {
  it("disables the trigger for a viewer", async () => {
    await renderWithRole("viewer");
    const button = screen.getByTestId("emergency-stop-trigger");
    expect(button).toBeDisabled();
  });

  it("disables the trigger for an operator (commander required)", async () => {
    await renderWithRole("operator");
    expect(screen.getByTestId("emergency-stop-trigger")).toBeDisabled();
  });

  it("opens the confirm dialog when a commander clicks the trigger", async () => {
    const user = userEvent.setup();
    await renderWithRole("commander");
    await user.click(screen.getByTestId("emergency-stop-trigger"));
    expect(screen.getByTestId("emergency-stop-dialog")).toBeInTheDocument();
    expect(screen.getByTestId("emergency-stop-confirm")).toBeDisabled();
  });

  it("keeps the Confirm button disabled until the phrase matches", async () => {
    const user = userEvent.setup();
    await renderWithRole("commander");
    await user.click(screen.getByTestId("emergency-stop-trigger"));

    const input = screen.getByTestId("emergency-stop-input") as HTMLInputElement;
    const confirm = screen.getByTestId("emergency-stop-confirm");

    await user.type(input, "return all units");
    expect(confirm).toBeDisabled();

    await user.clear(input);
    await user.type(input, EMERGENCY_CONFIRMATION_PHRASE);
    expect(confirm).not.toBeDisabled();
  });

  it("fires POST /actions/emergency-rtl-all with the canonical phrase on confirm", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ command_id: "c-1", status: "accepted" }),
        {
          status: 202,
          headers: { "Content-Type": "application/json" },
        }
      )
    );
    await renderWithRole("commander");
    await user.click(screen.getByTestId("emergency-stop-trigger"));
    const input = screen.getByTestId("emergency-stop-input");
    await user.type(input, EMERGENCY_CONFIRMATION_PHRASE);
    await user.click(screen.getByTestId("emergency-stop-confirm"));

    const call = fetchMock.mock.calls.find(([url]) =>
      String(url).includes("/actions/emergency-rtl-all")
    );
    expect(call).toBeDefined();
    const init = call![1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({
      confirm: true,
      confirmation_phrase: EMERGENCY_CONFIRMATION_PHRASE,
    });
  });

  it("Esc closes the modal", async () => {
    const user = userEvent.setup();
    await renderWithRole("commander");
    await user.click(screen.getByTestId("emergency-stop-trigger"));
    expect(screen.getByTestId("emergency-stop-dialog")).toBeInTheDocument();
    await act(async () => {
      await user.keyboard("{Escape}");
    });
    expect(screen.queryByTestId("emergency-stop-dialog")).not.toBeInTheDocument();
  });
});
