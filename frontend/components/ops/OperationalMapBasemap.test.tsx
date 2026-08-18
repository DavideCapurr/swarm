import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OperationalMap } from "./OperationalMap";
import type { FleetRow } from "@/lib/mission-story";

/**
 * The attribution strip is a claim, so it is held to the same standard as the
 * rest of the surface: it may say a real basemap is underneath only when the
 * tile host actually answered. A recording machine with no route to the tile
 * host draws the site frame alone, and the strip has to say so.
 */

const UNIT: FleetRow = {
  agentId: "mav-002",
  fsmState: "EN_ROUTE",
  batteryPct: 99,
  linkQuality: 100,
  altitudeAglM: 17,
  headingDeg: 40,
  geo: { lat: 47.3977794, lon: 8.545613 },
  missionId: null,
  objectiveLabel: null,
  step: null,
  excludedFrom: null,
  role: null,
};

/** Replaces `Image` so the probe resolves the way the network would. */
function stubTileHost(outcome: "load" | "error") {
  class ProbeImage {
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    set src(_value: string) {
      queueMicrotask(() => {
        if (outcome === "load") this.onload?.();
        else this.onerror?.();
      });
    }
  }
  vi.stubGlobal("Image", ProbeImage);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("basemap attribution", () => {
  it("claims a real basemap only once the tile host answered", async () => {
    stubTileHost("load");
    render(
      <OperationalMap
        units={[UNIT]}
        stories={[]}
        focusMissionId={null}
        telemetrySource="PX4 SITL TELEMETRY"
      />
    );

    await waitFor(() =>
      expect(screen.getByTestId("basemap-attribution")).toHaveTextContent(
        "REAL BASEMAP · © OPENSTREETMAP CONTRIBUTORS · © CARTO · CONTEXT ONLY"
      )
    );
  });

  it("says the site frame stands alone when the tiles never arrive", async () => {
    stubTileHost("error");
    render(
      <OperationalMap
        units={[UNIT]}
        stories={[]}
        focusMissionId={null}
        telemetrySource="PX4 SITL TELEMETRY"
      />
    );

    const strip = await screen.findByTestId("basemap-attribution");
    await waitFor(() =>
      expect(strip).toHaveTextContent("BASEMAP UNAVAILABLE · SITE FRAME ONLY · NO EXTERNAL CONTEXT")
    );
    expect(strip).not.toHaveTextContent("REAL BASEMAP");
  });
});
