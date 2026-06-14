/**
 * SWARM icon set — inline SVG, named, 24px, stroke 1.5, round caps + joins.
 *
 * No external icon kit. Lucide is a fallback only; everything used in the
 * Console must live here. Spec PDF §5.10.
 */

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 24, children, ...rest }: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

// ── Action rail ────────────────────────────────────────────────────────────────

export const IconVerify = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="m8.5 12 2.5 2.5L15.5 9.5" />
  </Svg>
);

export const IconHold = (p: IconProps) => (
  <Svg {...p}>
    <rect x="6" y="5" width="4" height="14" rx="0.5" />
    <rect x="14" y="5" width="4" height="14" rx="0.5" />
  </Svg>
);

export const IconDismiss = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M9 9l6 6M15 9l-6 6" />
  </Svg>
);

export const IconReturn = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 11h11a4 4 0 0 1 4 4v0a4 4 0 0 1-4 4H9" />
    <path d="M8 7 4 11l4 4" />
  </Svg>
);

// ── Rail cards ─────────────────────────────────────────────────────────────────

export const IconRisk = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 4 3 20h18Z" />
    <path d="M12 10v4" />
    <path d="M12 17h0.01" />
  </Svg>
);

export const IconPatrol = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8" />
    <path d="M12 7v5l3 2" />
  </Svg>
);

export const IconWeather = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 17h11a4 4 0 1 0-1.5-7.7A6 6 0 0 0 4 11.5 3.5 3.5 0 0 0 6 17Z" />
  </Svg>
);

export const IconLink = (p: IconProps) => (
  <Svg {...p}>
    <path d="M10 14a4 4 0 0 1 0-5.66l2-2a4 4 0 0 1 5.66 5.66l-1 1" />
    <path d="M14 10a4 4 0 0 1 0 5.66l-2 2a4 4 0 0 1-5.66-5.66l1-1" />
  </Svg>
);

export const IconAnomaly = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7" strokeDasharray="2 3" />
  </Svg>
);

// ── Evidence sources (provenance glyphs) ─────────────────────────────────────────
// One named 24px glyph per AnomalySource. Stroke 1.5, round caps — no kit.

// Thermal satellite pass — orbiting body over a horizon with a downward beam.
export const IconThermalSat = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 20h18" />
    <circle cx="12" cy="7" r="3" />
    <path d="M12 10v4" />
    <path d="M9.5 16.5 12 14l2.5 2.5" />
    <path d="M5 7h1M18 7h1M12 2v1" />
  </Svg>
);

// Fixed fire detector — a ceiling sensor disc emitting two sensing arcs.
export const IconFireDetector = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 5h16" />
    <circle cx="12" cy="11" r="3" />
    <path d="M12 5v3" />
    <path d="M7.5 16a6 6 0 0 1 9 0" />
  </Svg>
);

// Onboard drone camera + CV — a quad airframe with a centred lens.
export const IconDroneCv = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="2.5" />
    <path d="M9.5 9.5 6 6M14.5 9.5 18 6M9.5 14.5 6 18M14.5 14.5 18 18" />
    <circle cx="5" cy="5" r="1.5" />
    <circle cx="19" cy="5" r="1.5" />
    <circle cx="5" cy="19" r="1.5" />
    <circle cx="19" cy="19" r="1.5" />
  </Svg>
);

// ── Map / system ───────────────────────────────────────────────────────────────

export const IconSector = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 7l8-3 8 3v10l-8 3-8-3Z" />
    <path d="M12 4v16" />
    <path d="M4 7l16 10" />
  </Svg>
);

export const IconRoute = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="5" cy="6" r="2" />
    <circle cx="19" cy="18" r="2" />
    <path d="M5 8c0 6 8 4 8 10" />
  </Svg>
);

export const IconDock = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4" y="13" width="16" height="6" rx="1" />
    <path d="M8 13V8h8v5" />
    <path d="M10 8V5h4v3" />
  </Svg>
);

export const IconUnit = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="2" />
    <path d="M12 4v3M12 17v3M4 12h3M17 12h3" />
    <path d="M6.5 6.5 8 8M16 16l1.5 1.5M6.5 17.5 8 16M16 8l1.5-1.5" />
  </Svg>
);

// ── Mobile chrome ──────────────────────────────────────────────────────────────

export const IconBack = (p: IconProps) => (
  <Svg {...p}>
    <path d="M15 6 9 12l6 6" />
  </Svg>
);

// Phase 6.G — fleet-wide return icon. A nested ring + an inward chevron so
// the affordance reads as "everything coming home" without any red-band
// imagery. Stays inside the 24px viewBox at stroke 1.5px.
export const IconEmergencyReturn = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="4" />
    <path d="M12 3v4M21 12h-4M12 21v-4M3 12h4" />
  </Svg>
);

export const IconClose = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);

// ── Aliases consumed elsewhere ────────────────────────────────────────────────

export type { IconProps };
