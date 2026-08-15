import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { IntrusionResponseDemo } from "./IntrusionResponseDemo";

const mockUseSwarm = vi.fn();

vi.mock("@/lib/state", () => ({
  useSwarm: () => mockUseSwarm(),
}));

describe("IntrusionResponseDemo", () => {
  beforeEach(() => {
    mockUseSwarm.mockReturnValue({
      units: [],
      link: "lost",
    });
  });

  it("keeps simulated footage and side effects explicit", () => {
    render(<IntrusionResponseDemo />);

    expect(screen.getByText("SIMULATED STOCK FOOTAGE")).toBeInTheDocument();
    expect(screen.getByText("SIMULATED DRONE VIEW")).toBeInTheDocument();
    expect(screen.getByText(/No external call is placed in demo mode/i)).toBeInTheDocument();
    expect(screen.getByText(/Real coordination\. Simulated imagery and side effects\./i)).toBeInTheDocument();
  });

  it("surfaces the bounded physical-response actions without claiming hardware execution", () => {
    render(<IntrusionResponseDemo />);

    expect(screen.getByText("Notify site support")).toBeInTheDocument();
    expect(screen.getByText("Establish bounded presence")).toBeInTheDocument();
    expect(screen.getByText("Play site warning")).toBeInTheDocument();
    expect(screen.getAllByText("SIMULATED").length).toBeGreaterThanOrEqual(3);
  });

  it("can replay the scripted presentation without touching the legacy dashboard", () => {
    render(<IntrusionResponseDemo />);

    const replay = screen.getByRole("button", { name: "REPLAY" });
    fireEvent.click(replay);

    expect(screen.getByText("North perimeter · intrusion")).toBeInTheDocument();
    expect(screen.getByText("Watching")).toBeInTheDocument();
  });
});
