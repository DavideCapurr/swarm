/**
 * TAKE A comprehension test.
 *
 * The acceptance bar for the operational console is not "it renders" — it is
 * that a person who has never seen SWARM can follow the recorded take from the
 * screen alone (`docs/design/operational-console-ia.md` §8). Each block below
 * is one of those ten beats, asserted at the point in the take where a viewer
 * would be looking for it.
 *
 * The frames come from the recorded-take script, so the ids, owners, scores,
 * exclusion and evidence kinds under test are the ones the bench actually
 * produced.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TAKE_A, foldTakeA, takeAFrames } from "@/lib/demo-frames";
import { shortId } from "@/lib/mission-story";

import { OperationalConsole, type ConsoleFrame } from "./OperationalConsole";

const FRAMES = takeAFrames();

function renderAt(atS: number) {
  const slice = foldTakeA(atS * 1000, FRAMES);
  const frame: ConsoleFrame = {
    link: "connected",
    sessionLabel: "take a",
    operatorId: "op-demo",
    role: "viewer",
    clockText: "12:00:00 UTC",
    executionGroups: [],
    ...slice,
  };
  return render(<OperationalConsole frame={frame} />);
}

describe("TAKE A — readable without a voice-over", () => {
  it("1 · starts clean: fleet docked, no objective claimed", () => {
    renderAt(0.5);

    expect(screen.getByTestId("link-state")).toHaveTextContent("CONNECTED");
    expect(screen.getByText("NO OBJECTIVE PUBLISHED BY SWARMOS")).toBeInTheDocument();
    expect(within(screen.getByTestId("fleet-mav-001")).getByText("DOCKED")).toBeInTheDocument();
    expect(within(screen.getByTestId("fleet-mav-002")).getByText("DOCKED")).toBeInTheDocument();
    expect(screen.getAllByText("no mission · available")).toHaveLength(2);
  });

  it("2 · the objective arrives with its confidence", () => {
    renderAt(2.5);

    const queued = screen.getByTestId(`objective-${TAKE_A.missionOne}`);
    expect(queued).toHaveTextContent("OBJ 01");
    expect(queued).toHaveTextContent("INTRUSION");
    expect(queued).toHaveTextContent("95%");

    const rail = screen.getByTestId("decision-rail");
    expect(within(rail).getByText("INTRUSION")).toBeInTheDocument();
    expect(within(rail).getByText("Objective")).toBeInTheDocument();
  });

  it("3 · SwarmOS evaluates both agents with visible scores and reasons", () => {
    renderAt(2.5);

    const first = screen.getByTestId("candidate-mav-001");
    const second = screen.getByTestId("candidate-mav-002");
    expect(first).toHaveTextContent("ELIGIBLE");
    expect(first).toHaveTextContent("2.257");
    expect(first).toHaveTextContent(/dist 40m/);
    expect(first).toHaveTextContent(/batt 100%/);
    expect(second).toHaveTextContent("2.258");
    expect(screen.getByText("Fleet evaluated by SwarmOS")).toBeInTheDocument();
    expect(screen.getByText("SERVER REASONS")).toBeInTheDocument();
  });

  it("4 · mav-002 is selected and owns the mission", () => {
    renderAt(2.5);

    expect(screen.getByTestId("candidate-mav-002")).toHaveTextContent("SELECTED");
    const rail = screen.getByTestId("decision-rail");
    expect(within(rail).getByText("Selected by SwarmOS")).toBeInTheDocument();
    expect(within(rail).getAllByText("mav-002").length).toBeGreaterThan(0);
    expect(within(rail).getByText(`mission ${shortId(TAKE_A.missionOne)}`)).toBeInTheDocument();
    expect(within(rail).getByText("owned by mav-002")).toBeInTheDocument();
    expect(screen.getByTestId("decision-summary")).toHaveTextContent(
      "mav-002 selected · highest score of 2 eligible agents"
    );
  });

  it("5 · execution is discrete steps, not a percentage", () => {
    renderAt(5);

    const ladder = screen.getByTestId("execution-ladder");
    for (const step of ["ALLOCATED", "DISPATCHED", "EN ROUTE", "ON STATION", "RTL", "DONE"]) {
      expect(within(ladder).getByText(step)).toBeInTheDocument();
    }
    expect(within(ladder).getAllByText("pending").length).toBeGreaterThan(0);
    expect(screen.queryByText(/%\s*complete/i)).not.toBeInTheDocument();
  });

  it("6 · arrival is proven by MISSION_ITEM_REACHED", () => {
    renderAt(20);

    const rail = screen.getByTestId("decision-rail");
    expect(within(rail).getByText("MISSION_ITEM_REACHED")).toBeInTheDocument();
    expect(within(rail).getAllByText(/PX4 SITL/).length).toBeGreaterThan(0);
    expect(screen.getByTestId(`objective-${TAKE_A.missionOne}`)).toHaveTextContent("ON STATION");
  });

  it("7 · the physical response separates confirmed output from simulated playback", () => {
    renderAt(21);

    const light = screen.getByTestId("payload-LIGHT");
    expect(light).toHaveTextContent("LIGHT ON");
    expect(light).toHaveTextContent("PX4 OUTPUT CONFIRMED");

    const speaker = screen.getByTestId("payload-SPEAKER");
    expect(speaker).toHaveTextContent("SPEAKER ACTIVE");
    expect(speaker).toHaveTextContent("SIMULATED");
  });

  it("8 · the second objective arrives while the first mission is still running", () => {
    renderAt(26);

    expect(screen.getByTestId(`objective-${TAKE_A.missionOne}`)).toHaveTextContent("EXECUTING");
    const second = screen.getByTestId(`objective-${TAKE_A.missionTwo}`);
    expect(second).toHaveTextContent("OBJ 02");
    expect(second).toHaveTextContent("HEAT_SPOT");
  });

  it("9 · mav-002 is excluded as BUSY with mission 1's exact id, and mav-001 is selected", () => {
    renderAt(26);

    const excluded = screen.getByTestId("candidate-mav-002");
    expect(excluded).toHaveTextContent("EXCLUDED · BUSY");
    expect(excluded).toHaveTextContent(shortId(TAKE_A.missionOne));

    expect(screen.getByTestId("candidate-mav-001")).toHaveTextContent("SELECTED");
    expect(screen.getByTestId("decision-summary")).toHaveTextContent(
      `mav-002 excluded · BUSY · already owns mission ${shortId(TAKE_A.missionOne)}`
    );

    // The same fact is on the agent's own row, not only in the decision rail.
    expect(screen.getByTestId("fleet-excluded-mav-002")).toHaveTextContent(
      "EXCLUDED FROM OBJ 02 · BUSY"
    );
  });

  it("10 · both missions are simultaneously owned and executing", () => {
    renderAt(30);

    expect(screen.getByTestId("fleet-mav-002")).toHaveTextContent(
      `owns OBJ 01 · mission ${shortId(TAKE_A.missionOne)}`
    );
    expect(screen.getByTestId("fleet-mav-001")).toHaveTextContent(
      `owns OBJ 02 · mission ${shortId(TAKE_A.missionTwo)}`
    );

    expect(screen.getByTestId("concurrency-badge")).toHaveTextContent(
      "CONCURRENT MISSION OWNERSHIP · 2 EXECUTING"
    );
    expect(screen.getByTestId(`lane-${TAKE_A.missionOne}`)).toHaveTextContent("mav-002");
    expect(screen.getByTestId(`lane-${TAKE_A.missionTwo}`)).toHaveTextContent("mav-001");
  });

  it("closes mission 1 only with an acknowledged RTL", async () => {
    renderAt(45);

    // Focus follows the newest objective, so step back to the first one.
    await userEvent.click(screen.getByTestId(`objective-${TAKE_A.missionOne}`));

    const rail = screen.getByTestId("decision-rail");
    expect(within(rail).getByText("RTL COMMAND ACKNOWLEDGED")).toBeInTheDocument();
    expect(screen.getByTestId(`objective-${TAKE_A.missionOne}`)).toHaveTextContent("CLOSED");
  });

  it("never renders the simulated imagery as evidence or as a live feed", () => {
    renderAt(30);

    expect(screen.getByText("SIMULATED IMAGERY · NOT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("NOT A LIVE FEED")).toBeInTheDocument();
    expect(screen.queryByLabelText("Simulated drone view")).not.toBeInTheDocument();
  });

  it("renders TAKE B's execution group, roles and failover in the same language", () => {
    const slice = foldTakeA(30_000, FRAMES);
    render(
      <OperationalConsole
        frame={{
          link: "connected",
          sessionLabel: "take b",
          operatorId: "op-demo",
          role: "viewer",
          clockText: "12:00:00 UTC",
          ...slice,
          executionGroups: [
            {
              id: "group-1",
              objective_mission_id: "objective-1",
              objective_kind: "COOPERATIVE_VERIFY",
              anomaly_id: TAKE_A.anomalyOne,
              requested_members: 3,
              state: "DEGRADED",
              failure_reason: null,
              ts: "2026-08-15T12:00:30Z",
              members: [
                {
                  agent_id: "mav-001",
                  role: "PRIMARY_OBSERVER",
                  mission_id: "child-primary",
                  state: "ACTIVE",
                  score: 2.812,
                  score_breakdown: {},
                  replaces_agent_id: null,
                  ts: "2026-08-15T12:00:30Z",
                },
                {
                  agent_id: "mav-003",
                  role: "SECONDARY_OBSERVER",
                  mission_id: "child-secondary-old",
                  state: "REPLACED",
                  score: 2.641,
                  score_breakdown: {},
                  replaces_agent_id: null,
                  ts: "2026-08-15T12:00:30Z",
                },
                {
                  agent_id: "mav-004",
                  role: "SECONDARY_OBSERVER",
                  mission_id: "child-secondary-new",
                  state: "ASSIGNED",
                  score: 2.432,
                  score_breakdown: {},
                  replaces_agent_id: "mav-003",
                  ts: "2026-08-15T12:00:31Z",
                },
              ],
            },
          ],
        }}
      />
    );

    expect(screen.getByText("Execution group")).toBeInTheDocument();
    expect(screen.getByText("COOPERATIVE VERIFY")).toBeInTheDocument();
    expect(screen.getByText("3 REQUIRED ROLES")).toBeInTheDocument();
    expect(screen.getByTestId("group-member-child-secondary-old")).toHaveTextContent("REPLACED");
    expect(screen.getByTestId("group-member-child-secondary-new")).toHaveTextContent(
      "REPLACES mav-003"
    );
    expect(
      screen.getByText(/Physical agents\s+do not choose peers or roles/i)
    ).toBeInTheDocument();
  });

  it("makes no operational claim before SwarmOS publishes one", () => {
    render(
      <OperationalConsole
        frame={{
          link: "connecting",
          sessionLabel: "cold",
          operatorId: "",
          role: null,
          clockText: "—",
          units: [],
          anomalies: [],
          allocations: [],
          missionRuntime: [],
          missionRuntimeLog: [],
          payloadEvents: [],
          executionGroups: [],
          missions: [],
          now: TAKE_A.t0,
        }}
      />
    );

    expect(screen.getByText("No allocator frame yet.")).toBeInTheDocument();
    expect(screen.getByText("WAITING FOR FLEET STATE")).toBeInTheDocument();
    expect(screen.getByText("awaiting fleet position frames")).toBeInTheDocument();
    expect(screen.getByText("NO MISSION LANE")).toBeInTheDocument();
  });
});
