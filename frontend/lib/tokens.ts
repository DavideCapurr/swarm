/**
 * SWARM design tokens — PLACEHOLDER.
 *
 * Canonical source: docs/pdf/SWARM-design-system-v1.pdf
 * Status: PLACEHOLDER until the design system PDF is extracted (no
 * `pdftotext`/`poppler` available in the current environment). See
 * docs/design-system.md for the graduation path.
 *
 * The values below are consistent with the textual PDFs' voice:
 *   - dark canvas
 *   - thin orbital line motif
 *   - restrained typography
 *   - operational, not cinematic
 *
 * When tokens land from the PDF, only this file changes.
 */
export const tokens = {
  color: {
    bg: "#000000",
    surface: "#0a0a0c",
    ink: "#f5f5f7",
    muted: "#6e6e76",
    accent: "#bcd5ff",
    ok: "#7ad6a0",
    warn: "#f1c277",
    crit: "#e26666",
    line: "#1a1a1f",
  },
  font: {
    sans: ["-apple-system", "Inter", "Helvetica Neue", "Arial", "sans-serif"],
    mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
  },
  spacing: {
    "1": "4px",
    "2": "8px",
    "3": "12px",
    "4": "16px",
    "6": "24px",
    "8": "32px",
    "12": "48px",
  },
  radius: {
    none: "0",
    sm: "2px",
    md: "4px",
    lg: "8px",
  },
} as const;

export type Tokens = typeof tokens;
