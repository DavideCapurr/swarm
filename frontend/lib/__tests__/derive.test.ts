/**
 * Evidence-layer display formatters — units/labels only. Every value comes
 * from the server; these helpers format the Δ / score for the operator.
 */

import { describe, expect, it } from "vitest";

import { anomalyCallout, describeSource, formatEvidence } from "@/lib/derive";
import type { AnomalyEvidence, AnomalyView, OperatorCommand } from "@/lib/api";

function anomaly(overrides: Partial<AnomalyView> = {}): AnomalyView {
  return {
    id: "a-1",
    kind: "FIRE",
    geo: { lat: 44.7, lon: 8.03, alt_m: 0 },
    sector_id: "center-a",
    confidence: 0.88,
    band: "verified",
    state: "pending",
    detected_at: new Date(0).toISOString(),
    detected_by: null,
    verifying_agent: null,
    ts: new Date(0).toISOString(),
    ...overrides,
  };
}

function ev(overrides: Partial<AnomalyEvidence> = {}): AnomalyEvidence {
  return {
    source: "drone_cv",
    sensor: "RGB",
    label: null,
    metric: null,
    value: null,
    baseline: null,
    unit: null,
    headline: "",
    simulated: true,
    ...overrides,
  };
}

describe("describeSource", () => {
  it("maps each provenance to a plain-voice label", () => {
    expect(describeSource("thermal_sat")).toBe("thermal sat");
    expect(describeSource("fire_detector")).toBe("fire detector");
    expect(describeSource("drone_cv")).toBe("onboard cv");
    expect(describeSource("unknown")).toBe("signal");
  });
});

describe("formatEvidence", () => {
  it("formats a thermal delta over baseline", () => {
    expect(
      formatEvidence(
        ev({
          source: "thermal_sat",
          sensor: "THERMAL",
          metric: "temperature_c",
          value: 47,
          baseline: 18,
          unit: "°C",
        })
      )
    ).toBe("+29°C over baseline");
  });

  it("formats a CV object score with label", () => {
    expect(
      formatEvidence(
        ev({ metric: "object_score", label: "fire", value: 0.88, unit: "score" })
      )
    ).toBe("fire · 088%");
  });

  it("formats a CV object score without label", () => {
    expect(
      formatEvidence(ev({ metric: "object_score", value: 0.55 }))
    ).toBe("055%");
  });

  it("formats a fire-detector trip", () => {
    expect(
      formatEvidence(ev({ source: "fire_detector", sensor: "THERMAL" }))
    ).toBe("heat trip");
  });

  it("falls back to the server headline when shape is unrecognised", () => {
    expect(
      formatEvidence(ev({ source: "unknown", headline: "signal · awaiting provenance" }))
    ).toBe("signal · awaiting provenance");
  });
});

describe("anomalyCallout", () => {
  it("leads with source + evidence when evidence is present", () => {
    const out = anomalyCallout(
      anomaly({
        state: "verified",
        evidence: ev({
          source: "thermal_sat",
          sensor: "THERMAL",
          metric: "temperature_c",
          value: 47,
          baseline: 18,
          unit: "°C",
          headline: "thermal · +29°C over baseline",
        }),
      }),
      null
    );
    expect(out).toContain("thermal sat");
    expect(out).toContain("+29°C over baseline");
    expect(out).toContain("verified");
  });

  it("shows the CV source label + score for a drone-cv anomaly", () => {
    const out = anomalyCallout(
      anomaly({
        kind: "INTRUSION",
        state: "pending",
        evidence: ev({ metric: "object_score", label: "person", value: 0.71 }),
      }),
      null
    );
    expect(out).toContain("onboard cv");
    expect(out).toContain("person · 071%");
  });

  it("prepends an auto eyebrow with the rule when autonomy is in flight", () => {
    const auto = { rule: "R2", status: "in_flight" } as unknown as OperatorCommand;
    const out = anomalyCallout(
      anomaly({
        state: "escalated",
        evidence: ev({
          source: "thermal_sat",
          metric: "temperature_c",
          value: 47,
          baseline: 18,
          unit: "°C",
        }),
      }),
      auto
    );
    expect(out.startsWith("auto · r2 · ")).toBe(true);
    expect(out).toContain("thermal sat");
  });

  it("keeps the legacy state callout when no evidence is present", () => {
    const out = anomalyCallout(anomaly({ evidence: null, confidence: 0.62, state: "pending" }), null);
    expect(out).toBe("anomaly detected · confidence 062 %");
  });
});
