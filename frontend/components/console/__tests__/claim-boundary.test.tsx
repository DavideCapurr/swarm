import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ObjectiveAuthority } from "@/lib/authority";
import type { PayloadChannel } from "@/lib/mission-story";

import { DetectionPanel } from "../DetectionPanel";
import { MissionAuthorityPanel } from "../MissionAuthorityPanel";

/**
 * The claim boundary.
 *
 * This surface renders two kinds of thing that look alike and are not: what the
 * PX4 runtime actually confirmed, and what is only simulated. Every way the two
 * could be merged into one reassuring line is a defect, so the separation is
 * gated here rather than left to review.
 */

const OBJECTIVE: ObjectiveAuthority = {
  key: "group-1",
  index: 1,
  kind: "INTRUSION",
  label: "M-8582edb3",
  missionId: "8582edb3f2984289ab756602ac03aad5",
  anomalyId: "anom-1",
  confidence: 0.99,
  detectedAt: "2026-08-15T17:28:51.000Z",
  detection: {
    source: "drone_cv",
    sensor: "RGB",
    label: "person",
    value: 0.99,
    headline: "Elevated anomaly — onboard CV classified a person at 0.99 confidence.",
    simulated: true,
    reportedBy: "mav-004",
    at: "2026-08-15T17:28:51.000Z",
  },
  geo: { lat: 47.398, lon: 8.546 },
  groupId: "group-1",
  groupStateLabel: "ACTIVE",
  swarms: [],
  requestedMembers: 3,
  slots: [],
  activeMembers: 0,
  state: "EXECUTING",
  active: true,
  trace: [],
  routes: [],
  latestProof: null,
  decisionAt: "2026-08-15T17:28:52.000Z",
};

const CHANNELS: PayloadChannel[] = [
  {
    channel: "LIGHT",
    state: "LIGHT ON",
    proof: "PX4 OUTPUT CONFIRMED",
    tier: "verified",
    agentId: "mav-004",
    ts: "2026-08-15T17:29:33.000Z",
  },
  {
    channel: "SPEAKER",
    state: "SPEAKER ACTIVE",
    proof: "SIMULATED",
    tier: "simulated",
    agentId: "mav-004",
    ts: "2026-08-15T17:29:34.000Z",
  },
];

describe("bounded response", () => {
  it("keeps the confirmed channel and the simulated one apart", () => {
    render(
      <MissionAuthorityPanel
        objectives={[OBJECTIVE]}
        focused={OBJECTIVE}
        beat={{ phase: "idle" }}
        capacity={[]}
        channels={CHANNELS}
        onSelectObjective={() => {}}
      />
    );

    // Both claims are present, and each keeps its own proof. A single merged
    // "evidence" line would let the speaker inherit the light's confirmation.
    expect(screen.getByText("PX4 OUTPUT CONFIRMED")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED")).toBeInTheDocument();
    expect(screen.getByText("LIGHT ON")).toBeInTheDocument();
    expect(screen.getByText("SPEAKER ACTIVE")).toBeInTheDocument();
  });

  it("says nothing at all before a payload frame arrives", () => {
    const empty: PayloadChannel[] = CHANNELS.map((channel) => ({
      ...channel,
      ts: null,
      proof: "NO PAYLOAD FRAME",
    }));
    render(
      <MissionAuthorityPanel
        objectives={[OBJECTIVE]}
        focused={OBJECTIVE}
        beat={{ phase: "idle" }}
        capacity={[]}
        channels={empty}
        onSelectObjective={() => {}}
      />
    );

    expect(screen.queryByText("NO PAYLOAD FRAME")).not.toBeInTheDocument();
  });
});

describe("detection provenance", () => {
  it("stamps a simulated triggering signal as simulated", () => {
    render(<DetectionPanel objective={OBJECTIVE} />);

    expect(screen.getByText("SIMULATED SIGNAL")).toBeInTheDocument();
    // Provenance is compressed onto one line: source, reporter, time.
    expect(screen.getByText("ONBOARD CV · mav-004 · 17:28:51 UTC")).toBeInTheDocument();
    // The raw classifier reading stays on the panel, demoted rather than
    // dropped, on its own quieter line.
    expect(screen.getByText("RGB · PERSON 0.99")).toBeInTheDocument();
  });

  it("renders no camera surface, because the runtime publishes none", () => {
    const { container } = render(<DetectionPanel objective={OBJECTIVE} />);

    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("falls back to simulated when a frame never said where it came from", () => {
    const unattributed: ObjectiveAuthority = {
      ...OBJECTIVE,
      detection: {
        source: "unknown",
        sensor: "UNKNOWN",
        label: null,
        value: null,
        headline: null,
        simulated: true,
        reportedBy: null,
        at: null,
      },
    };
    render(<DetectionPanel objective={unattributed} />);

    expect(screen.getByText("SIMULATED SIGNAL")).toBeInTheDocument();
    expect(screen.getByText("UNATTRIBUTED · — UTC")).toBeInTheDocument();
  });
});
