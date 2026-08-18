import { describe, expect, it } from "vitest";

import { telemetrySourceLabel } from "../telemetry-source";

const unit = (vendor: string, model: string) => ({ vendor, model });

describe("telemetrySourceLabel", () => {
  it("names the PX4 SITL bench the recording actually runs on", () => {
    expect(
      telemetrySourceLabel([unit("mavlink", "px4-iris-sitl"), unit("mavlink", "px4-iris-sitl")])
    ).toBe("PX4 SITL TELEMETRY");
  });

  it("does not call a simulated fleet PX4", () => {
    const label = telemetrySourceLabel([unit("simulated", "sim-quad")]);
    expect(label).toBe("SIMULATED TELEMETRY");
    expect(label).not.toContain("PX4");
  });

  it("does not upgrade a non-SITL MAVLink model to a SITL claim", () => {
    const label = telemetrySourceLabel([unit("mavlink", "px4-x500")]);
    expect(label).toBe("MAVLINK TELEMETRY · PX4-X500");
    expect(label).not.toContain("SITL");
  });

  it("says so when the fleet is mixed", () => {
    expect(
      telemetrySourceLabel([unit("mavlink", "px4-iris-sitl"), unit("simulated", "sim-quad")])
    ).toBe("MIXED TELEMETRY SOURCES");
  });

  it("claims nothing before any unit reports", () => {
    expect(telemetrySourceLabel([])).toBe("AWAITING TELEMETRY");
  });
});
