/**
 * Evidence layer — the heat overlay only renders for anomalies that carry a
 * usable surface-temperature signal (and aren't resolved). This pins the
 * selection logic; the maplibre circle layer itself is exercised in-browser.
 */

import { describe, expect, it } from "vitest";

import { thermalAnomalies } from "@/components/HeatOverlay";
import type { AnomalyEvidence } from "@/lib/api";
import { makeAnomaly } from "./_swarmState";

function ev(overrides: Partial<AnomalyEvidence> = {}): AnomalyEvidence {
  return {
    source: "thermal_sat",
    sensor: "THERMAL",
    label: null,
    metric: "temperature_c",
    value: 47,
    baseline: 18,
    unit: "°C",
    headline: "thermal · +29°C over baseline",
    simulated: true,
    ...overrides,
  };
}

describe("thermalAnomalies", () => {
  it("includes a thermal anomaly with value + baseline", () => {
    const a = makeAnomaly({ id: "fire", kind: "FIRE", evidence: ev() });
    expect(thermalAnomalies([a]).map((x) => x.id)).toEqual(["fire"]);
  });

  it("excludes non-temperature (drone-cv / object_score) anomalies", () => {
    const cv = makeAnomaly({
      id: "cv",
      evidence: ev({ source: "drone_cv", sensor: "RGB", metric: "object_score", baseline: null }),
    });
    expect(thermalAnomalies([cv])).toEqual([]);
  });

  it("excludes anomalies with no evidence", () => {
    expect(thermalAnomalies([makeAnomaly({ id: "x", evidence: null })])).toEqual([]);
  });

  it("excludes a thermal anomaly missing value or baseline", () => {
    const noVal = makeAnomaly({ id: "nv", evidence: ev({ value: null }) });
    const noBase = makeAnomaly({ id: "nb", evidence: ev({ baseline: null }) });
    expect(thermalAnomalies([noVal, noBase])).toEqual([]);
  });

  it("excludes resolved (dismissed / marked_known) anomalies", () => {
    const dismissed = makeAnomaly({ id: "d", state: "dismissed", evidence: ev() });
    const known = makeAnomaly({ id: "k", state: "marked_known", evidence: ev() });
    expect(thermalAnomalies([dismissed, known])).toEqual([]);
  });
});
