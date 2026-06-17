/**
 * CV-live video sub-step — LiveFeedFrame renders the simulated clip with an
 * unmistakable `SIMULATED FEED` stamp, the external live feed without it, and
 * fails closed to the honest placard otherwise (never a stock clip).
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { LiveFeedFrame } from "@/components/LiveFeedFrame";
import type { StreamDescriptor, UnitState } from "@/lib/api";

function makeUnit(overrides: Partial<UnitState> = {}): UnitState {
  return {
    agent_id: "unit-003",
    vendor: "sim",
    model: "sim",
    fsm_state: "ON_STATION",
    battery_pct: 80,
    geo: { lat: 0, lon: 0, alt_m: 0 },
    current_mission_id: null,
    current_sector_id: null,
    link_quality: 0.9,
    heading_deg: 90,
    altitude_agl_m: 120,
    dock_id: null,
    ts: new Date().toISOString(),
    ...overrides,
  };
}

function makeStream(overrides: Partial<StreamDescriptor> = {}): StreamDescriptor {
  return {
    agent_id: "unit-003",
    available: false,
    simulated: false,
    url: null,
    protocol: null,
    codec: null,
    ts: new Date().toISOString(),
    ...overrides,
  };
}

describe("LiveFeedFrame", () => {
  it("renders the simulated clip with a SIMULATED FEED stamp", () => {
    const stream = makeStream({
      available: true,
      simulated: true,
      url: "/sim-feed/unit-003-pov.mp4",
      codec: "h264",
    });
    render(<LiveFeedFrame unit={makeUnit()} linkOk stream={stream} />);

    const video = screen.getByLabelText(/simulated viewport unit 003/i);
    expect(video.getAttribute("src")).toBe("/sim-feed/unit-003-pov.mp4");
    expect(screen.getByTestId("simulated-feed-stamp")).toHaveTextContent(
      "SIMULATED FEED"
    );
  });

  it("renders an external live feed without the simulated stamp", () => {
    const stream = makeStream({
      available: true,
      simulated: false,
      url: "https://stream.example.com/hls/u3.m3u8",
      protocol: "https",
      codec: "h264",
    });
    render(<LiveFeedFrame unit={makeUnit()} linkOk stream={stream} />);

    expect(screen.getByLabelText(/live viewport unit 003/i)).toBeInTheDocument();
    expect(screen.queryByTestId("simulated-feed-stamp")).toBeNull();
  });

  it("falls back to the honest placard when no stream is present", () => {
    render(<LiveFeedFrame unit={makeUnit()} linkOk stream={null} />);
    expect(screen.getByText(/UNIT 003 VIEWPORT PENDING/i)).toBeInTheDocument();
    expect(screen.queryByTestId("simulated-feed-stamp")).toBeNull();
  });

  it("shows STREAM OFFLINE (no video) when the link is down, even with a sim clip", () => {
    const stream = makeStream({
      available: true,
      simulated: true,
      url: "/sim-feed/unit-003-pov.mp4",
    });
    render(<LiveFeedFrame unit={makeUnit()} linkOk={false} stream={stream} />);
    expect(screen.getByText(/UNIT 003 STREAM OFFLINE/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/viewport unit 003/i)).toBeNull();
  });

  it("fails closed when a simulated descriptor carries a non-sim-feed url", () => {
    const stream = makeStream({
      available: true,
      simulated: true,
      // Not under /sim-feed/ — the client allowlist must refuse it.
      url: "/api/secret",
    });
    render(<LiveFeedFrame unit={makeUnit()} linkOk stream={stream} />);
    expect(screen.getByText(/UNIT 003 VIEWPORT PENDING/i)).toBeInTheDocument();
    expect(screen.queryByTestId("simulated-feed-stamp")).toBeNull();
  });
});
