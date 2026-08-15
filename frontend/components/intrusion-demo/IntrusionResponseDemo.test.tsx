import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntrusionResponseDemo } from "./IntrusionResponseDemo";

const mockUseSwarm = vi.fn();

vi.mock("@/lib/state", () => ({
  useSwarm: () => mockUseSwarm(),
}));

const decisionOne = {
  mission_id: "mission-one",
  mission_kind: "VERIFY",
  anomaly_id: "anomaly-one",
  mode: "auction" as const,
  eligible_units: [
    {
      agent_id: "mav-001",
      fsm_state: "DOCKED" as const,
      battery_pct: 82,
      score: 2.14,
      score_breakdown: {
        distance_m: 190,
        distance_score: 0.77,
        battery_pct: 82,
        battery_score: 0.82,
        priority: 98,
        priority_score: 0.49,
        busy_penalty: 0,
      },
    },
    {
      agent_id: "mav-002",
      fsm_state: "DOCKED" as const,
      battery_pct: 91,
      score: 2.64,
      score_breakdown: {
        distance_m: 74,
        distance_score: 0.93,
        battery_pct: 91,
        battery_score: 0.91,
        priority: 98,
        priority_score: 0.49,
        busy_penalty: 0,
      },
    },
  ],
  excluded_units: [],
  winner_agent_id: "mav-002",
  winner_score: 2.64,
  ts: "2026-08-15T12:00:00Z",
};

const decisionTwo = {
  mission_id: "mission-two",
  mission_kind: "VERIFY",
  anomaly_id: "anomaly-two",
  mode: "auction" as const,
  eligible_units: [
    {
      agent_id: "mav-001",
      fsm_state: "DOCKED" as const,
      battery_pct: 80,
      score: 2.71,
      score_breakdown: {
        distance_m: 48,
        distance_score: 0.95,
        battery_pct: 80,
        battery_score: 0.8,
        priority: 99,
        priority_score: 0.495,
        busy_penalty: 0,
      },
    },
  ],
  excluded_units: [
    {
      agent_id: "mav-002",
      fsm_state: "EN_ROUTE" as const,
      battery_pct: 89,
      reason: "BUSY" as const,
      active_mission_id: "mission-one",
    },
  ],
  winner_agent_id: "mav-001",
  winner_score: 2.71,
  ts: "2026-08-15T12:00:08Z",
};

const anomalies = [
  {
    id: "anomaly-one",
    kind: "INTRUSION" as const,
    geo: { lat: 45, lon: 10, alt_m: 0 },
    sector_id: "north",
    confidence: 0.96,
    band: "verified" as const,
    state: "verifying" as const,
    detected_at: "2026-08-15T12:00:00Z",
    detected_by: "cam-04",
    verifying_agent: "mav-002",
    ts: "2026-08-15T12:00:00Z",
  },
  {
    id: "anomaly-two",
    kind: "HEAT_SPOT" as const,
    geo: { lat: 45.02, lon: 10.02, alt_m: 0 },
    sector_id: "east",
    confidence: 0.99,
    band: "verified" as const,
    state: "verifying" as const,
    detected_at: "2026-08-15T12:00:08Z",
    detected_by: "sensor-02",
    verifying_agent: "mav-001",
    ts: "2026-08-15T12:00:08Z",
  },
];

const units = [
  {
    agent_id: "mav-001",
    vendor: "mavlink",
    model: "px4-x500",
    fsm_state: "EN_ROUTE" as const,
    battery_pct: 80,
    geo: { lat: 45, lon: 10, alt_m: 20 },
    current_mission_id: null,
    current_sector_id: "east",
    link_quality: 1,
    heading_deg: 0,
    altitude_agl_m: 20,
    dock_id: "dock-01",
    ts: "2026-08-15T12:00:09Z",
  },
  {
    agent_id: "mav-002",
    vendor: "mavlink",
    model: "px4-x500",
    fsm_state: "ON_STATION" as const,
    battery_pct: 89,
    geo: { lat: 45, lon: 10, alt_m: 40 },
    current_mission_id: null,
    current_sector_id: "north",
    link_quality: 1,
    heading_deg: 0,
    altitude_agl_m: 40,
    dock_id: "dock-01",
    ts: "2026-08-15T12:00:09Z",
  },
];

function liveState() {
  return {
    allocations: [decisionOne, decisionTwo],
    anomalies,
    missionRuntime: [
      {
        id: "runtime-one",
        mission_id: "mission-one",
        agent_id: "mav-002",
        phase: "ON_STATION",
        progress_pct: 95,
        evidence: "mavlink_mission_item_reached" as const,
        error: null,
        ts: "2026-08-15T12:00:07Z",
      },
      {
        id: "runtime-two",
        mission_id: "mission-two",
        agent_id: "mav-001",
        phase: "EN_ROUTE",
        progress_pct: 5,
        evidence: null,
        error: null,
        ts: "2026-08-15T12:00:09Z",
      },
    ],
    payloadEvents: [
      {
        id: "payload-light",
        mission_id: "mission-one",
        anomaly_id: "anomaly-one",
        action_id: "action-light",
        agent_id: "mav-002",
        kind: "light_on" as const,
        status: "confirmed" as const,
        execution_mode: "mavlink_output_confirmed" as const,
        light_on: true,
        speaker_active: false,
        message: null,
        error_code: null,
        ts: "2026-08-15T12:00:07Z",
      },
      {
        id: "payload-speaker",
        mission_id: "mission-one",
        anomaly_id: "anomaly-one",
        action_id: "action-speaker",
        agent_id: "mav-002",
        kind: "play_message" as const,
        status: "simulated" as const,
        execution_mode: "simulated" as const,
        light_on: true,
        speaker_active: true,
        message: "restricted_area" as const,
        error_code: null,
        ts: "2026-08-15T12:00:07Z",
      },
    ],
    units,
    link: "connected" as const,
  };
}

describe("IntrusionResponseDemo", () => {
  beforeEach(() => {
    mockUseSwarm.mockReturnValue({
      allocations: [],
      anomalies: [],
      missionRuntime: [],
      payloadEvents: [],
      units: [],
      link: "lost",
    });
  });

  it("renders no operational claim before backend truth exists", () => {
    render(<IntrusionResponseDemo />);

    expect(screen.getByText("Waiting for allocator frame.")).toBeInTheDocument();
    expect(screen.getByText("WAITING FOR BACKEND INTRUSION EVENT")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED STOCK FOOTAGE")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED DRONE VIEW")).toBeInTheDocument();
    expect(screen.queryByText("REPLAY")).not.toBeInTheDocument();
  });

  it("renders the second real allocation including BUSY exclusion and score", () => {
    mockUseSwarm.mockReturnValue(liveState());
    render(<IntrusionResponseDemo />);

    expect(screen.getAllByText("2.710").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/BUSY · mission mission-one/i)).toBeInTheDocument();
    expect(screen.getAllByText("mav-001").length).toBeGreaterThan(0);
    expect(screen.getAllByText("mav-002").length).toBeGreaterThan(0);
    expect(screen.getByText(/48m · batt 80%/i)).toBeInTheDocument();
  });

  it("keeps both mission owners visible while the second mission is active", () => {
    mockUseSwarm.mockReturnValue(liveState());
    render(<IntrusionResponseDemo />);

    expect(screen.getByText(/INTRUSION · mission-o…/i)).toBeInTheDocument();
    expect(screen.getByText(/HEAT_SPOT · mission-t…/i)).toBeInTheDocument();
    expect(screen.getByText("MISSION_ITEM_REACHED")).toBeInTheDocument();
    expect(screen.getAllByText("EN ROUTE").length).toBeGreaterThan(0);
  });

  it("renders payload execution modes without upgrading simulated effects", () => {
    mockUseSwarm.mockReturnValue(liveState());
    render(<IntrusionResponseDemo />);

    expect(screen.getByText("LIGHT ON")).toBeInTheDocument();
    expect(screen.getByText("PX4 OUTPUT CONFIRMED")).toBeInTheDocument();
    expect(screen.getByText("SPEAKER ACTIVE")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED")).toBeInTheDocument();
  });
});
