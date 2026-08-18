import { describe, expect, it } from "vitest";

import { TAKE_A, foldTakeA, takeAFrames } from "../demo-frames";
import {
  buildFleetRows,
  buildPayloadChannels,
  buildStories,
  buildTimeline,
  decisionSummary,
  selectStoryDecisions,
  type ObjectiveStory,
} from "../mission-story";

const FRAMES = takeAFrames();

function storiesAt(atS: number): ObjectiveStory[] {
  const slice = foldTakeA(atS * 1000, FRAMES);
  return buildStories({
    allocations: slice.allocations,
    anomalies: slice.anomalies,
    missionRuntime: slice.missionRuntime,
    missionRuntimeLog: slice.missionRuntimeLog,
    payloadEvents: slice.payloadEvents,
    missions: slice.missions,
  });
}

describe("execution ladder", () => {
  it("marks nothing reached before SwarmOS publishes a decision", () => {
    expect(storiesAt(1.5)).toHaveLength(0);
  });

  it("reaches ALLOCATED on the allocator frame alone", () => {
    const [story] = storiesAt(2.5);
    const byStep = new Map(story.ladder.map((slot) => [slot.step, slot]));
    expect(byStep.get("ALLOCATED")?.source).toBe("observed");
    expect(byStep.get("ALLOCATED")?.proof).toBe("ALLOCATOR DECISION");
    expect(byStep.get("EN ROUTE")?.source).toBe("pending");
    expect(byStep.get("DONE")?.source).toBe("pending");
  });

  it("attaches MISSION_ITEM_REACHED to ON STATION, never to an earlier step", () => {
    const [story] = storiesAt(20);
    const byStep = new Map(story.ladder.map((slot) => [slot.step, slot]));
    expect(byStep.get("ON STATION")?.proof).toBe("MISSION_ITEM_REACHED");
    expect(byStep.get("EN ROUTE")?.proof).toBeNull();
    expect(byStep.get("RTL")?.source).toBe("pending");
  });

  it("closes only on an acknowledged RTL", () => {
    const [story] = storiesAt(45);
    const byStep = new Map(story.ladder.map((slot) => [slot.step, slot]));
    expect(byStep.get("RTL")?.proof).toBe("RTL COMMAND ACKNOWLEDGED");
    expect(byStep.get("DONE")?.source).toBe("observed");
    expect(story.active).toBe(false);
  });

  it("marks a step implied — never observed — when the Console booted mid-mission", () => {
    const slice = foldTakeA(45_000, FRAMES);
    const late = buildStories({
      allocations: slice.allocations,
      anomalies: slice.anomalies,
      // A REST-booted Console only ever sees the latest frame per mission.
      missionRuntime: slice.missionRuntime,
      missionRuntimeLog: [],
      payloadEvents: slice.payloadEvents,
      missions: slice.missions,
    });
    const byStep = new Map(late[0].ladder.map((slot) => [slot.step, slot]));
    expect(byStep.get("EN ROUTE")?.source).toBe("implied");
    expect(byStep.get("EN ROUTE")?.ts).toBeNull();
    expect(byStep.get("EN ROUTE")?.proof).toBeNull();
  });
});

describe("candidates and the decision restatement", () => {
  it("puts the exclusion first — on the second objective it is the decision", () => {
    const stories = storiesAt(26);
    const second = stories[1].candidates;
    expect(second[0]).toMatchObject({ kind: "excluded", agentId: "mav-002", reason: "BUSY" });
    expect(second[1]).toMatchObject({ kind: "eligible", agentId: "mav-001", selected: true });
  });

  it("carries the blocking mission id through to the restatement", () => {
    const stories = storiesAt(26);
    const lines = decisionSummary(stories[1]);
    expect(lines[0]).toContain("BUSY");
    expect(lines[0]).toContain(TAKE_A.missionOne.slice(0, 8));
    expect(lines[1]).toBe("mav-001 selected · highest score of 1 eligible agent");
  });

  it("does not report a diverted unit as the winner of an auction", () => {
    // Continuous patrol leaves nothing eligible, so SwarmOS diverts an airborne
    // unit. Reporting that as "highest score of 0 eligible agents" would claim
    // a competition that never ran.
    const [story] = storiesAt(2.5);
    const diverted: ObjectiveStory = {
      ...story,
      mode: "diversion",
      owner: "sim-1",
      ownerScore: null,
      divertedFrom: "830a0ce8f1d94b1fa0f3ce7f4a1c9d22",
      candidates: [],
    };

    const lines = decisionSummary(diverted);

    expect(lines).toEqual([
      "sim-1 diverted by SwarmOS · no agent was eligible · pulled off mission 830a0ce8",
    ]);
    expect(lines.join(" ")).not.toContain("highest score");
  });

  it("orders eligible candidates by the server score", () => {
    const [first] = storiesAt(2.5);
    const eligible = first.candidates.filter((c) => c.kind === "eligible");
    expect(eligible[0].agentId).toBe("mav-002");
    expect(eligible.map((c) => c.kind === "eligible" && c.selected)).toEqual([true, false]);
  });
});

describe("evidence tiers", () => {
  it("never promotes a simulated payload to verified", () => {
    const [first] = storiesAt(21);
    const speaker = first.evidence.find((row) => row.action === "SPEAKER ACTIVE");
    expect(speaker?.tier).toBe("simulated");
    expect(speaker?.proof).toBe("SIMULATED");
  });

  it("keeps the confirmed PX4 output in the verified tier", () => {
    const [first] = storiesAt(21);
    const light = first.evidence.find((row) => row.action === "LIGHT ON");
    expect(light?.tier).toBe("verified");
    expect(light?.proof).toBe("PX4 OUTPUT CONFIRMED");
  });

  it("reports the latest state of each bounded channel", () => {
    const stories = storiesAt(42);
    const channels = buildPayloadChannels(stories.flatMap((s) => s.payloadEvents));
    expect(channels).toEqual([
      expect.objectContaining({ channel: "LIGHT", state: "LIGHT OFF", tier: "verified" }),
      expect.objectContaining({ channel: "SPEAKER", state: "SPEAKER STOPPED", tier: "simulated" }),
    ]);
  });

  it("says so plainly when nothing has been published", () => {
    expect(buildPayloadChannels([])).toEqual([
      expect.objectContaining({ channel: "LIGHT", state: "IDLE", proof: "NO PAYLOAD FRAME" }),
      expect.objectContaining({ channel: "SPEAKER", state: "IDLE", proof: "NO PAYLOAD FRAME" }),
    ]);
  });
});

describe("fleet rows", () => {
  it("shows ownership and the exclusion on the same agent", () => {
    const stories = storiesAt(30);
    const slice = foldTakeA(30_000, FRAMES);
    const rows = buildFleetRows(slice.units, stories, []);
    const busy = rows.find((row) => row.agentId === "mav-002")!;
    expect(busy.missionId).toBe(TAKE_A.missionOne);
    expect(busy.objectiveLabel).toBe("OBJ 01");
    expect(busy.excludedFrom).toMatchObject({ label: "OBJ 02", reason: "BUSY" });

    const other = rows.find((row) => row.agentId === "mav-001")!;
    expect(other.missionId).toBe(TAKE_A.missionTwo);
    expect(other.excludedFrom).toBeNull();
  });
});

describe("timeline", () => {
  it("reports concurrency only while more than one mission is non-terminal", () => {
    expect(buildTimeline(storiesAt(20), TAKE_A.t0 + 20_000).concurrent).toBe(false);
    expect(buildTimeline(storiesAt(30), TAKE_A.t0 + 30_000).concurrent).toBe(true);
    expect(buildTimeline(storiesAt(61), TAKE_A.t0 + 61_000).concurrent).toBe(false);
  });

  it("gives each mission its own lane, owner and ticks", () => {
    const timeline = buildTimeline(storiesAt(30), TAKE_A.t0 + 30_000);
    expect(timeline.lanes.map((lane) => lane.owner)).toEqual(["mav-002", "mav-001"]);
    expect(timeline.lanes[0].ticks.map((tick) => tick.label)).toContain("ON STATION");
    expect(timeline.lanes[0].ticks.map((tick) => tick.label)).toContain("LIGHT ON");
  });

  it("places every tick at the timestamp of the frame that produced it", () => {
    const timeline = buildTimeline(storiesAt(30), TAKE_A.t0 + 30_000);
    for (const lane of timeline.lanes) {
      for (const tick of lane.ticks) {
        expect(tick.at).toBeGreaterThanOrEqual(timeline.from);
        expect(tick.at).toBeLessThanOrEqual(timeline.to);
      }
    }
  });
});

describe("selectStoryDecisions", () => {
  it("keeps the two-objective story visible after a long bench session", () => {
    const older = {
      mission_id: "old",
      mission_kind: "VERIFY",
      anomaly_id: "a-old",
      mode: "auction" as const,
      eligible_units: [],
      excluded_units: [],
      winner_agent_id: null,
      winner_score: null,
      ts: "2026-08-15T11:00:00Z",
    };
    const slice = foldTakeA(30_000, FRAMES);
    const anomalies = new Map(slice.anomalies.map((a) => [a.id, a]));
    const picked = selectStoryDecisions([older, ...slice.allocations], anomalies);
    expect(picked.map((d) => d.mission_id)).toEqual([TAKE_A.missionOne, TAKE_A.missionTwo]);
  });
});
