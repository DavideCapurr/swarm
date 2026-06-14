/**
 * Evidence layer — EvidenceBlock renders the *why* from server-provided
 * evidence: the headline (truth), provenance, sensor, and the measurement.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EvidenceBlock } from "@/components/EvidenceBlock";
import type { AnomalyEvidence } from "@/lib/api";
import { makeAnomaly } from "./_swarmState";

function evidence(overrides: Partial<AnomalyEvidence> = {}): AnomalyEvidence {
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

describe("EvidenceBlock", () => {
  it("renders the server headline, source, sensor and measurement", () => {
    render(
      <EvidenceBlock
        anomaly={makeAnomaly({ kind: "FIRE", evidence: evidence() })}
      />
    );
    expect(screen.getByTestId("evidence-block")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-headline")).toHaveTextContent(
      "thermal · +29°C over baseline"
    );
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("thermal sat");
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("thermal");
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("+29°C over baseline");
    // value-vs-baseline reading row
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("47°C vs 18°C");
  });

  it("flags sim-modelled signals with a SIMULATED eyebrow", () => {
    render(<EvidenceBlock anomaly={makeAnomaly({ evidence: evidence() })} />);
    expect(screen.getByTestId("evidence-simulated")).toBeInTheDocument();
  });

  it("renders a CV label + score for an onboard-cv anomaly", () => {
    render(
      <EvidenceBlock
        anomaly={makeAnomaly({
          kind: "INTRUSION",
          detected_by: "sim-2",
          evidence: evidence({
            source: "drone_cv",
            sensor: "RGB",
            metric: "object_score",
            label: "person",
            value: 0.71,
            baseline: null,
            unit: "score",
            headline: "drone cv · person · 071%",
          }),
        })}
      />
    );
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("onboard cv");
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("person · 071%");
    expect(screen.getByTestId("evidence-block")).toHaveTextContent("unit 002");
  });

  it("renders nothing when the anomaly has no evidence", () => {
    const { container } = render(
      <EvidenceBlock anomaly={makeAnomaly({ evidence: null })} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
