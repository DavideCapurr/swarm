/**
 * Phase 7.C — HeadBar shows the inline `autonomy baseline` chip.
 *
 * Reads `autonomyEnabled` from `useSwarm()`; the chip rides
 * `StatusPill state="connected"` so it inherits the Orbital Blue halo
 * already vetted by the design system. We also assert it's absent
 * when the gate is off, so we don't fail open.
 */

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { HeadBar } from "@/components/HeadBar";
import { makeSwarmState } from "./_swarmState";

vi.mock("@/lib/state", () => ({
  useSwarm: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

// EmergencyStop reads its own auth context; stub the component out so
// the HeadBar render stays focused on the autonomy chip surface.
vi.mock("@/components/EmergencyStop", () => ({
  EmergencyStop: () => null,
}));

import { useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);

describe("HeadBar", () => {
  it("renders the `autonomy baseline` chip when the gate is on", () => {
    useSwarmMock.mockReturnValue(
      makeSwarmState({
        autonomyEnabled: true,
        session: {
          id: "s-1",
          label: "session 014",
          site_id: "vineyard-01",
          autonomy_enabled: true,
          started_at: new Date(0).toISOString(),
          ts: new Date(0).toISOString(),
        },
      })
    );

    render(<HeadBar />);

    const chip = screen.getByTestId("autonomy-chip");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveTextContent("autonomy baseline");
  });

  it("hides the autonomy chip when the gate is off", () => {
    useSwarmMock.mockReturnValue(makeSwarmState({ autonomyEnabled: false }));
    render(<HeadBar />);
    expect(screen.queryByTestId("autonomy-chip")).not.toBeInTheDocument();
  });
});
