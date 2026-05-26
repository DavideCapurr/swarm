/**
 * HeadBar — slim head bar surface (post-redesign).
 *
 * The autonomy chip is gone from the head bar after the redesign; the
 * baseline-on signal lives as a ghost row inside QuietPanel's Performance
 * section. The head bar itself shows the wordmark, console nav, session
 * label, link badge, clock, online ring, and operator badge.
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

import { useSwarm } from "@/lib/state";

const useSwarmMock = vi.mocked(useSwarm);

describe("HeadBar", () => {
  it("renders the wordmark and online ring", () => {
    useSwarmMock.mockReturnValue(
      makeSwarmState({
        autonomyEnabled: true,
        session: {
          id: "s-1",
          label: "vineyard-01-04",
          site_id: "vineyard-01",
          autonomy_enabled: true,
          started_at: new Date(0).toISOString(),
          ts: new Date(0).toISOString(),
        },
      })
    );

    render(<HeadBar />);

    expect(screen.getByText("SWARM")).toBeInTheDocument();
    expect(screen.getByText("/ vineyard-01-04")).toBeInTheDocument();
  });

  it("does not render the autonomy baseline chip", () => {
    useSwarmMock.mockReturnValue(makeSwarmState({ autonomyEnabled: true }));
    render(<HeadBar />);
    expect(screen.queryByTestId("autonomy-chip")).not.toBeInTheDocument();
  });
});
