/**
 * Phase 7.C — selector that drives the AUTO chip on AnomalySummary,
 * the verify panel, and the mobile alert surface.
 */

import { describe, expect, it } from "vitest";

import { findActiveAutonomyCommand, findLatestAutonomyCommand } from "./autonomy";
import { makeCommand } from "@/components/__tests__/_swarmState";

describe("findActiveAutonomyCommand", () => {
  it("returns the in-flight autonomy command targeting the anomaly", () => {
    const cmd = makeCommand({
      source: "autonomy",
      target: "anomaly:a-1",
      status: "in_flight",
    });
    expect(findActiveAutonomyCommand([cmd], "a-1")).toBe(cmd);
  });

  it("ignores operator-source commands targeting the same anomaly", () => {
    const cmd = makeCommand({
      source: "operator",
      target: "anomaly:a-1",
      status: "in_flight",
    });
    expect(findActiveAutonomyCommand([cmd], "a-1")).toBeNull();
  });

  it("ignores terminal-status autonomy commands", () => {
    const completed = makeCommand({
      source: "autonomy",
      target: "anomaly:a-1",
      status: "completed",
    });
    const rejected = makeCommand({
      id: "cmd-rej",
      source: "autonomy",
      target: "anomaly:a-1",
      status: "rejected",
    });
    expect(findActiveAutonomyCommand([completed, rejected], "a-1")).toBeNull();
  });

  it("returns the most-recently-submitted autonomy command when several are in flight", () => {
    const older = makeCommand({
      id: "cmd-old",
      source: "autonomy",
      target: "anomaly:a-1",
      status: "in_flight",
      submitted_at: "2026-05-20T10:00:00Z",
    });
    const newer = makeCommand({
      id: "cmd-new",
      source: "autonomy",
      target: "anomaly:a-1",
      status: "in_flight",
      submitted_at: "2026-05-20T12:00:00Z",
    });
    expect(findActiveAutonomyCommand([older, newer], "a-1")).toBe(newer);
  });

  it("only matches the requested anomaly id", () => {
    const other = makeCommand({
      source: "autonomy",
      target: "anomaly:b-2",
      status: "submitted",
    });
    expect(findActiveAutonomyCommand([other], "a-1")).toBeNull();
  });
});

describe("findLatestAutonomyCommand", () => {
  it("returns a terminal (completed) autonomy command — the AUTO chip persists", () => {
    const cmd = makeCommand({
      source: "autonomy",
      action: "escalate",
      target: "anomaly:a-1",
      status: "completed",
      rule: "R2",
    });
    expect(findLatestAutonomyCommand([cmd], "a-1")).toBe(cmd);
  });

  it("returns the most-recent autonomy command regardless of terminal status", () => {
    const olderInFlight = makeCommand({
      id: "cmd-old",
      source: "autonomy",
      target: "anomaly:a-1",
      status: "in_flight",
      submitted_at: "2026-05-20T10:00:00Z",
    });
    const newerCompleted = makeCommand({
      id: "cmd-new",
      source: "autonomy",
      target: "anomaly:a-1",
      status: "completed",
      submitted_at: "2026-05-20T12:00:00Z",
    });
    expect(
      findLatestAutonomyCommand([olderInFlight, newerCompleted], "a-1")
    ).toBe(newerCompleted);
  });

  it("ignores operator-source commands even after they terminate", () => {
    const cmd = makeCommand({
      source: "operator",
      target: "anomaly:a-1",
      status: "completed",
    });
    expect(findLatestAutonomyCommand([cmd], "a-1")).toBeNull();
  });

  it("returns null when no autonomy command targets the anomaly", () => {
    const other = makeCommand({
      source: "autonomy",
      target: "anomaly:b-2",
      status: "completed",
    });
    expect(findLatestAutonomyCommand([other], "a-1")).toBeNull();
  });
});
