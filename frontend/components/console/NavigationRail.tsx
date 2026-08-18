"use client";

/**
 * NavigationRail — the standing left edge.
 *
 * Deliberately the least interesting surface on screen. It exists so the
 * software reads as a whole product rather than a single screen, and it stops
 * there: no account avatar, no workspace switcher, no notification bell, no
 * search, no marketing.
 *
 * The sections named here are the ones SwarmOS actually holds state for —
 * objectives, physical capacity, missions, evidence. The demo lives in MAP, and
 * the rest are shown at rest rather than wired to invented screens: a rail that
 * navigates to fabricated modules would be the same dishonesty as a fabricated
 * readout.
 */

import {
  GlyphCapacity,
  GlyphEvidence,
  GlyphMap,
  GlyphMission,
  GlyphObjective,
  GlyphSwarm,
  GlyphSystem,
  type GlyphProps,
} from "./glyphs";
import { HAIRLINE } from "./Surface";

export const RAIL_WIDTH = 60;

type Item = {
  id: string;
  label: string;
  Icon: (props: GlyphProps) => React.JSX.Element;
};

const SECTIONS: Item[] = [
  { id: "map", label: "Map", Icon: GlyphMap },
  { id: "objectives", label: "Objectives", Icon: GlyphObjective },
  { id: "capacity", label: "Capacity", Icon: GlyphCapacity },
  { id: "missions", label: "Missions", Icon: GlyphMission },
  { id: "evidence", label: "Evidence", Icon: GlyphEvidence },
];

function RailItem({ item, active }: { item: Item; active: boolean }) {
  const { Icon } = item;
  return (
    <div
      data-testid={`rail-${item.id}`}
      aria-current={active ? "page" : undefined}
      className="relative flex w-full flex-col items-center gap-[5px] py-[9px]"
      style={{ opacity: active ? 1 : 0.52 }}
    >
      {active ? (
        <span
          aria-hidden="true"
          className="absolute left-0 top-1/2 h-[26px] w-[2px] -translate-y-1/2 bg-orbital-blue"
        />
      ) : null}
      <Icon size={19} className={active ? "text-orbital-blue" : "text-muted-silver"} />
      <span
        className={`font-grotesk text-[8.5px] font-medium uppercase leading-none tracking-[0.11em] ${
          active ? "text-platinum" : "text-ash"
        }`}
      >
        {item.label}
      </span>
    </div>
  );
}

export function NavigationRail({ active = "map" }: { active?: string }) {
  return (
    <nav
      aria-label="SwarmOS sections"
      data-testid="navigation-rail"
      className="absolute inset-y-0 left-0 z-40 flex flex-col items-center"
      style={{
        width: RAIL_WIDTH,
        background: "rgba(4, 6, 8, 0.965)",
        borderRight: `1px solid ${HAIRLINE}`,
      }}
    >
      <div className="flex h-[54px] w-full items-center justify-center">
        <GlyphSwarm size={21} className="text-platinum" />
      </div>
      <div className="h-px w-[30px]" style={{ background: HAIRLINE }} aria-hidden="true" />

      <div className="mt-2 flex w-full flex-col">
        {SECTIONS.map((item) => (
          <RailItem key={item.id} item={item} active={item.id === active} />
        ))}
      </div>

      <div className="mt-auto flex w-full flex-col items-center pb-3">
        <div
          className="mb-2 h-px w-[30px]"
          style={{ background: HAIRLINE }}
          aria-hidden="true"
        />
        <RailItem
          item={{ id: "system", label: "System", Icon: GlyphSystem }}
          active={active === "system"}
        />
      </div>
    </nav>
  );
}
