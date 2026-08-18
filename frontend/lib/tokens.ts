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
    // ash carries the label tier — `text-ash` is the second most used text
    // colour in the console (97 call sites) and every one of them renders at
    // 9–13px, which WCAG never treats as large text. The brand-book value
    // #6B7480 measured 4.09:1 on obsidian and 3.34:1 on a graphite/60 hovered
    // row, i.e. under the 4.5:1 floor everywhere. #7F8A98 is the same cool
    // grey lightened along its own hue until the worst surface it lands on
    // clears AA: 5.85:1 on absolute-black, 5.52:1 on obsidian, 4.52:1 on
    // graphite/60. It stays firmly recessive — relative luminance 0.250
    // against muted-silver 0.425 and platinum 0.870 — so the three text tiers
    // still read as three tiers.
    ash: "#7F8A98",
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

  // ── Surface ramp ────────────────────────────────────────────────────────
  //
  // The console is delivered as a compressed video, and it used to paint panel
  // bodies in `absoluteBlack` on a page ground of `absoluteBlack` — the same
  // colour, separated only by a 1px hairline, which is the first thing an
  // encoder destroys. Measured in the page: ground and panel body both
  // rgb(3, 4, 6), at every frame.
  //
  // Three steps now, all greyscale, so the 85% monochrome rule is untouched.
  // They are chosen in Rec.709 luma rather than by eye, and stated below in the
  // limited-range code values a delivered video actually carries:
  //
  //                        luma   tv code
  //   surface0  ground     13.6      28     the gaps between panels
  //   surface1  panel body 24.2      37     +9 — content sits here
  //   surface2  raised     31.2      43     +6 — panel headers, command bar
  //
  // The defect was never a floor to clear: limited range rescales 0-255 into
  // 16-235, it does not clip. It was that ground and panel body were the *same
  // colour*, so the separation between them was zero code values and no encoder
  // could preserve a distinction that did not exist. All that carried a panel
  // edge was a 1px hairline, which is exactly the high-frequency detail block
  // transforms smear first.
  //
  // surface2 is capped by accessibility, not taste. `ash` — the label tier, 97
  // call sites at 9-13px — measures 4.69:1 here. The next step up the ramp
  // (#1E262E) drops it to 4.37 and breaks the AA floor that `fbb26bd`
  // established. The ramp stops where the text stops clearing.
  //
  // The map keeps `absoluteBlack`. It is a canvas, not a panel: being darker
  // than the ground is what bounds it, its marks are drawn in light tones, and
  // its graticule keeps an 18-point luma margin over it.
  surfaceRamp: {
    s0: "#0B0E11",            // ground — obsidian
    s1: "#131920",            // panel body
    s2: "#1A2026",            // raised chrome — gunmetal
  },

  // ── Semantic aliases used across the dashboard ────────────────────────────
  semantic: {
    bg: "#030406",            // absoluteBlack
    surface: "#0B0E11",       // obsidian
    line: "#1A2026",          // gunmetal — hairline borders
    inkPrimary: "#EEF0F3",    // platinum
    inkSecondary: "#A8AFB8",  // mutedSilver
    inkMuted: "#7F8A98",      // ash
    rest: "#EEF0F3",          // platinum — neutral state dot
    connected: "#7BE7FF",     // orbitalBlue
    operational: "#B8FF66",   // signalGreen
    attention: "#FFB45C",     // launchAmber
  },

  // ── Typography ──────────────────────────────────────────────────────────
  // The SWARM stack uses four families. Loaded from Google Fonts in
  // `app/layout.tsx`.
  //
  // Display/body is Inter, which is what the brand book actually renders:
  // `docs/design-system/v1.html` asks for 'Satoshi','Inter' and Google Fonts
  // does not serve Satoshi, so Inter is the face on those spreads.
  //
  // Inter is also the most legible option at the 11–13px sizes this console
  // is built from. Measured x-height, as a fraction of the em:
  //   Inter 0.546 · Geist 0.530 · Public Sans 0.517 · IBM Plex Sans 0.516 ·
  //   Roboto Flex 0.514 · Atkinson Hyperlegible 0.496
  // Inter is also the only candidate carrying an `opsz` axis, so
  // `font-optical-sizing: auto` in styles/globals.css lets the face open its
  // apertures and letter spacing as type gets smaller.
  //
  // Mono is JetBrains Mono, which carries every operational number on the
  // surface at 9–13px. Measured x-height 0.550 em against IBM Plex Mono's
  // 0.516 — 6.6% more apparent size at the same px, the largest single gain
  // available in this stack. Both faces already disambiguate zero with an
  // interior dot, so that is a wash; the x-height is the reason.
  //
  // JetBrains Mono ships `calt` code ligatures (`->`, `!=`, `==`). Telemetry
  // is not code, so globals.css disables them — a fused arrow inside a
  // coordinate or an ID would misreport state.
  font: {
    editorial:
      "'Cormorant Garamond', 'EB Garamond', Georgia, serif",
    display:
      "'Inter', system-ui, -apple-system, sans-serif",
    body:
      "'Inter', system-ui, -apple-system, sans-serif",
    mono:
      "'JetBrains Mono', 'SF Mono', ui-monospace, monospace",
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
