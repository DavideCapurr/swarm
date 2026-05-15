"use client";

/**
 * LiveFeedFrame — the verification viewport placeholder.
 *
 * Per PDF §5.2 and §10: NEVER show a stock clip. When no real stream is wired
 * (Phase 5 brings the adapter), the frame renders an honest hairline plate
 * with the canonical mono copy: "UNIT 003 VIEWPORT PENDING" / "STREAM
 * OFFLINE".
 *
 * Geometry: 4:3 viewport, gunmetal border, cross-hair graticule, corner
 * stamps. No glow, no shadow, no glassmorphism.
 */

import type { UnitState } from "@/lib/api";

type Props = {
  unit: UnitState | null;
  linkOk?: boolean;
};

export function LiveFeedFrame({ unit, linkOk = true }: Props) {
  const unitId = unit ? unitLabel(unit.agent_id) : "—";
  const heading = unit ? `${unit.heading_deg.toFixed(0).padStart(3, "0")}°` : "—";
  const altitude = unit ? `${unit.altitude_agl_m.toFixed(0).padStart(3, "0")} m` : "—";
  const link = unit ? `${(unit.link_quality * 100).toFixed(0)} %` : "—";
  const message = !unit
    ? "stream offline"
    : !linkOk
      ? "stream offline"
      : "viewport pending";

  return (
    <div className="relative bg-absolute-black border border-gunmetal aspect-[4/3] overflow-hidden">
      {/* Cross-hair graticule */}
      <svg
        className="pointer-events-none absolute inset-0 w-full h-full"
        viewBox="0 0 400 300"
        preserveAspectRatio="xMidYMid slice"
      >
        <g stroke="#1A2026" strokeWidth="0.5">
          <line x1="0" y1="150" x2="400" y2="150" />
          <line x1="200" y1="0" x2="200" y2="300" />
        </g>
        <g stroke="#1A2026" strokeWidth="0.5" strokeDasharray="2 4">
          <rect x="40" y="30" width="320" height="240" fill="none" />
        </g>
        <g fill="#EEF0F3">
          <rect x="198" y="148" width="4" height="4" />
        </g>
      </svg>

      {/* Center placard */}
      <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
        <span className="eyebrow-mono text-platinum tracking-eyebrow">
          UNIT {unitId} {message.toUpperCase()}
        </span>
        <span className="eyebrow-mono text-ash">
          no stock video · honest placeholder
        </span>
      </div>

      {/* Corner stamps */}
      <div className="pointer-events-none absolute left-3 top-3 eyebrow-mono mono-num">
        hd · 320p · {link}
      </div>
      <div className="pointer-events-none absolute right-3 top-3 eyebrow-mono mono-num text-right">
        hdg {heading}
      </div>
      <div className="pointer-events-none absolute left-3 bottom-3 eyebrow-mono mono-num">
        unit {unitId}
      </div>
      <div className="pointer-events-none absolute right-3 bottom-3 eyebrow-mono mono-num text-right">
        alt {altitude}
      </div>
    </div>
  );
}

function unitLabel(agentId: string): string {
  const m = agentId.match(/(\d+)/);
  return m ? m[1].padStart(3, "0") : agentId.slice(0, 3).toUpperCase();
}
