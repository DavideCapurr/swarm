/**
 * Phase 7.C — EventFeed renders the `auto` kind label on autonomy rows.
 *
 * For Operator-kind events the column normally reads `operator`. When
 * the row's source is "autonomy" we replace the label with `auto`
 * (Orbital Blue) so the operator spots autonomy decisions in the feed.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { EventFeed } from "@/components/EventFeed";
import { makeEvent } from "./_swarmState";

describe("EventFeed", () => {
  it("renders the `auto` kind label on autonomy-source events", () => {
    const events = [
      makeEvent({
        id: "evt-auto",
        kind: "operator",
        source: "autonomy",
        body: "autonomy verify dispatched · R1",
      }),
    ];
    render(<EventFeed events={events} />);

    const label = screen.getByTestId("event-kind-auto-evt-auto");
    expect(label).toHaveTextContent("auto");
    expect(label.className).toMatch(/text-orbital-blue/);
    // Body stays honest, exactly as the backend emitted it.
    expect(screen.getByText("autonomy verify dispatched · R1")).toBeInTheDocument();
  });

  it("renders the `operator` kind label on operator-source events", () => {
    const events = [
      makeEvent({
        id: "evt-op",
        kind: "operator",
        source: "operator",
        body: "operator intent accepted · verify",
      }),
    ];
    render(<EventFeed events={events} />);

    // The auto chip selector must not be present for operator rows.
    expect(screen.queryByTestId("event-kind-auto-evt-op")).not.toBeInTheDocument();
    // The legacy column still shows the kind in lowercase.
    expect(screen.getByText("operator")).toBeInTheDocument();
  });
});
