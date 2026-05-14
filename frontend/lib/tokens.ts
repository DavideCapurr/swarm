/**
 * SWARM design tokens — derived from `docs/design-system/v1.html` (Brand
 * Aesthetic v1.0). When that document changes, this file changes; nothing
 * else.
 *
 * Layering rule the design system enforces:
 *   85% monochrome surface + 15% activation accent.
 *   Color appears only when something activates.
 *
 * Naming preserved from the brand:
 *   The names "orbital-blue / launch-amber / signal-green" are intentional
 *   brand poetry. The hex values are the truth.
 */

export const tokens = {
  // ── Monochrome (the 85%) ────────────────────────────────────────────────
  color: {
    absoluteBlack: "#030406",
    obsidian: "#0B0E11",
    gunmetal: "#1A2026",
    graphite: "#2A3138",
    ash: "#6B7480",
    mutedSilver: "#A8AFB8",
    bone: "#C8CDD3",
    platinum: "#EEF0F3",

    mistHi: "#D3D6DA",
    mistMid: "#9398A0",
    mistLo: "#3F4348",

    ink: "#1A1C1F",
    ink2: "#3F4348",
    ink3: "#6B7080",

    // ── Activation accents (the 15%) ──────────────────────────────────────
    // Spec: accents are state, not decoration.
    orbitalBlue: "#7BE7FF",   // CONNECTED · focus · live channel
    signalGreen: "#B8FF66",   // OPERATIONAL · online · confirmed
    launchAmber: "#FFB45C",   // ATTENTION · pre-launch · warning
  },

  // ── Semantic aliases used across the dashboard ────────────────────────────
  semantic: {
    bg: "#030406",            // absoluteBlack
    surface: "#0B0E11",       // obsidian
    line: "#1A2026",          // gunmetal — hairline borders
    inkPrimary: "#EEF0F3",    // platinum
    inkSecondary: "#A8AFB8",  // mutedSilver
    inkMuted: "#6B7480",      // ash
    rest: "#EEF0F3",          // platinum — neutral state dot
    connected: "#7BE7FF",     // orbitalBlue
    operational: "#B8FF66",   // signalGreen
    attention: "#FFB45C",     // launchAmber
  },

  // ── Typography ──────────────────────────────────────────────────────────
  // The SWARM stack uses five families. Loaded from Google Fonts in
  // `app/layout.tsx`.
  font: {
    editorial:
      "'Cormorant Garamond', 'EB Garamond', Georgia, serif",
    display:
      "'Geist', 'Inter', system-ui, -apple-system, sans-serif",
    body:
      "'Geist', 'Inter', system-ui, -apple-system, sans-serif",
    mono:
      "'IBM Plex Mono', 'SF Mono', ui-monospace, monospace",
    grotesk:
      "'Space Grotesk', system-ui, sans-serif",
  },

  // ── Type scale (px) — from spread 13 ────────────────────────────────────
  type: {
    hero:    { size: "144px", lh: "1.04", tracking: "-0.015em" },
    h1:      { size: "64px",  lh: "1.04", tracking: "-0.01em" },
    h2:      { size: "40px",  lh: "1.15", tracking: "0" },
    h3:      { size: "28px",  lh: "1.15", tracking: "0" },
    lede:    { size: "17px",  lh: "1.5",  tracking: "0" },
    body:    { size: "15px",  lh: "1.5",  tracking: "0" },
    ui:      { size: "13px",  lh: "1.4",  tracking: "0" },
    eyebrow: { size: "11px",  lh: "1.2",  tracking: "0.18em" },
    mono:    { size: "13px",  lh: "1.4",  tracking: "0.04em" },
  },

  // ── Spacing (px) — 4/8 scale from spread 17 ─────────────────────────────
  spacing: {
    "0":   "0",
    "0.5": "2px",
    "1":   "4px",
    "2":   "8px",
    "3":   "12px",
    "4":   "16px",
    "6":   "24px",
    "8":   "32px",
    "12":  "48px",
    "16":  "64px",
    "24":  "96px",
    "32":  "128px",
  },

  // ── Radius — borders, never shadows ─────────────────────────────────────
  radius: {
    none: "0",
    chip: "2px",
    input: "4px",
    card: "6px",
    pill: "999px",
  },

  // ── Borders — hairlines only ────────────────────────────────────────────
  border: {
    hairline: "1px solid #1A2026",  // gunmetal
    hairlineFocus: "1px solid #7BE7FF",  // orbital-blue focus ring
    insetHighlight: "inset 0 1px 0 rgba(238,240,243,0.06)",
  },

  // ── Motion — the SWARM easing ───────────────────────────────────────────
  motion: {
    easing: "cubic-bezier(0.2, 0.7, 0.1, 1)",
    duration: {
      press: "120ms",
      connect: "2400ms",
      loader: "900ms",
      breath: "4000ms",
    },
  },

  // ── Wordmark / lockup tracking ──────────────────────────────────────────
  tracking: {
    wordmark: "0.36em",  // SWARM in editorial uppercase
    wide: "0.32em",
    eyebrow: "0.18em",
    eyebrowMono: "0.22em",
  },
} as const;

// ── State helpers ────────────────────────────────────────────────────────────
// Map our SWARM-OS AgentState values to brand state colors.
// Mirrors the Control UI spread (24): RING-A op, RING-B att, RING-D lnk.
export type SwarmState = "rest" | "connected" | "operational" | "attention";

export function agentStateToSwarm(fsm: string): SwarmState {
  switch (fsm) {
    case "DOCKED":
      return "rest";
    case "TAKEOFF":
      return "connected";
    case "EN_ROUTE":
    case "ON_STATION":
    case "RTL":
    case "LANDING":
    case "DOCKING":
      return "operational";
    case "OFFLINE":
      return "rest";
    case "ERROR":
      return "attention";
    default:
      return "rest";
  }
}

export type Tokens = typeof tokens;
