/**
 * glyphs.tsx — the named marks this surface is drawn from.
 *
 * Inline SVG only, 24px box, 1.5px stroke, round caps, no external icon kit.
 * Every glyph here is either a navigation affordance or an entity on the map;
 * none of them is decoration.
 */

export type GlyphProps = { size?: number; className?: string };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 1.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true as const,
});

/** Navigation — the map itself. */
export const GlyphMap = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" />
    <path d="M9 4v13.5M15 6.5V20" />
  </svg>
);

/** Navigation — objectives. The same survey mark the map draws, reduced. */
export const GlyphObjective = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="6.5" />
    <path d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
  </svg>
);

/** Navigation — physical capacity. Three executors, one of them spare. */
export const GlyphCapacity = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <path d="M6 3.5 8.5 9 6 7.9 3.5 9z" />
    <path d="M18 3.5 20.5 9 18 7.9 15.5 9z" />
    <path d="M12 14 14.5 19.5 12 18.4 9.5 19.5z" />
    <path d="M6 11v2.5h12V11" opacity="0.5" />
  </svg>
);

/** Navigation — missions. */
export const GlyphMission = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <path d="M4 19c3.5 0 3.5-5 7-5s3.5-5 7-5" />
    <circle cx="4" cy="19" r="1.6" />
    <circle cx="18" cy="9" r="1.6" />
    <path d="M14.5 4.5h5.5V10" opacity="0.55" />
  </svg>
);

/** Navigation — evidence. */
export const GlyphEvidence = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <path d="M5 4h9l5 5v11H5z" />
    <path d="M14 4v5h5" />
    <path d="M8.5 14.5 11 17l4.5-5" />
  </svg>
);

/** Navigation — system. */
export const GlyphSystem = ({ size = 20, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" />
  </svg>
);

/** The SWARM mark — three executors composed around one centre. */
export const GlyphSwarm = ({ size = 22, className }: GlyphProps) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    className={className}
  >
    <circle cx="12" cy="12" r="2.4" fill="currentColor" />
    <circle cx="12" cy="3.6" r="1.7" fill="currentColor" opacity="0.85" />
    <circle cx="19.3" cy="16.2" r="1.7" fill="currentColor" opacity="0.85" />
    <circle cx="4.7" cy="16.2" r="1.7" fill="currentColor" opacity="0.85" />
    <path
      d="M12 5.3v4.3M17.9 15.3 14.1 13.2M6.1 15.3 9.9 13.2"
      stroke="currentColor"
      strokeWidth="1.1"
      opacity="0.5"
    />
  </svg>
);

/** Link state — carried in the top status only. */
export const GlyphLink = ({ size = 14, className }: GlyphProps) => (
  <svg {...base(size)} className={className}>
    <path d="M12 19.5v-6" />
    <path d="M8.2 11.4a5.4 5.4 0 0 1 7.6 0" />
    <path d="M5 8a9.9 9.9 0 0 1 14 0" />
  </svg>
);
