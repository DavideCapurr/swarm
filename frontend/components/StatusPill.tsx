/**
 * StatusPill — the SWARM status pill with halo dot.
 * Used in the head bar ("007 / 128 online") and inline in the Units list.
 *
 * Spread 19 (Components) defines four states: rest / connected /
 * operational / attention. The pill borders + dot use the same state color.
 */
import type { SwarmState } from "@/lib/tokens";

type Props = {
  state: SwarmState;
  children: React.ReactNode;
  className?: string;
  "data-testid"?: string;
};

const STATE_CLASS: Record<SwarmState, string> = {
  rest: "pill",
  connected: "pill pill-connected",
  operational: "pill pill-operational",
  attention: "pill pill-attention",
};

const DOT_CLASS: Record<SwarmState, string> = {
  rest: "dot dot-rest",
  connected: "dot dot-connected",
  operational: "dot dot-operational",
  attention: "dot dot-attention",
};

export function StatusPill({
  state,
  children,
  className = "",
  "data-testid": dataTestId,
}: Props) {
  return (
    <span
      className={`${STATE_CLASS[state]} ${className}`}
      data-testid={dataTestId}
    >
      <span className={DOT_CLASS[state]} />
      {children}
    </span>
  );
}
