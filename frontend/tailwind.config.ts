import type { Config } from "tailwindcss";
import { tokens } from "./lib/tokens";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Monochrome palette
        "absolute-black": tokens.color.absoluteBlack,
        obsidian: tokens.color.obsidian,
        gunmetal: tokens.color.gunmetal,
        graphite: tokens.color.graphite,
        ash: tokens.color.ash,
        "muted-silver": tokens.color.mutedSilver,
        bone: tokens.color.bone,
        platinum: tokens.color.platinum,
        "mist-hi": tokens.color.mistHi,
        "mist-mid": tokens.color.mistMid,
        "mist-lo": tokens.color.mistLo,
        ink: tokens.color.ink,
        "ink-2": tokens.color.ink2,
        "ink-3": tokens.color.ink3,

        // Activation accents
        "orbital-blue": tokens.color.orbitalBlue,
        "signal-green": tokens.color.signalGreen,
        "launch-amber": tokens.color.launchAmber,

        // Semantic aliases
        bg: tokens.semantic.bg,
        surface: tokens.semantic.surface,
        line: tokens.semantic.line,
      },
      fontFamily: {
        editorial: tokens.font.editorial.split(",").map((s) => s.trim().replace(/'/g, "")),
        display: tokens.font.display.split(",").map((s) => s.trim().replace(/'/g, "")),
        sans: tokens.font.body.split(",").map((s) => s.trim().replace(/'/g, "")),
        mono: tokens.font.mono.split(",").map((s) => s.trim().replace(/'/g, "")),
        grotesk: tokens.font.grotesk.split(",").map((s) => s.trim().replace(/'/g, "")),
      },
      fontSize: {
        hero:    [tokens.type.hero.size,    { lineHeight: tokens.type.hero.lh,    letterSpacing: tokens.type.hero.tracking }],
        h1:      [tokens.type.h1.size,      { lineHeight: tokens.type.h1.lh,      letterSpacing: tokens.type.h1.tracking }],
        h2:      [tokens.type.h2.size,      { lineHeight: tokens.type.h2.lh,      letterSpacing: tokens.type.h2.tracking }],
        h3:      [tokens.type.h3.size,      { lineHeight: tokens.type.h3.lh,      letterSpacing: tokens.type.h3.tracking }],
        lede:    [tokens.type.lede.size,    { lineHeight: tokens.type.lede.lh,    letterSpacing: tokens.type.lede.tracking }],
        body:    [tokens.type.body.size,    { lineHeight: tokens.type.body.lh,    letterSpacing: tokens.type.body.tracking }],
        ui:      [tokens.type.ui.size,      { lineHeight: tokens.type.ui.lh,      letterSpacing: tokens.type.ui.tracking }],
        eyebrow: [tokens.type.eyebrow.size, { lineHeight: tokens.type.eyebrow.lh, letterSpacing: tokens.type.eyebrow.tracking }],
        mono:    [tokens.type.mono.size,    { lineHeight: tokens.type.mono.lh,    letterSpacing: tokens.type.mono.tracking }],
      },
      spacing: tokens.spacing,
      borderRadius: {
        none: tokens.radius.none,
        chip: tokens.radius.chip,
        input: tokens.radius.input,
        card: tokens.radius.card,
        pill: tokens.radius.pill,
      },
      letterSpacing: {
        wordmark: tokens.tracking.wordmark,
        wide: tokens.tracking.wide,
        eyebrow: tokens.tracking.eyebrow,
        "eyebrow-mono": tokens.tracking.eyebrowMono,
      },
      boxShadow: {
        "inset-highlight": "inset 0 1px 0 rgba(238,240,243,0.06)",
        "halo-orbital": "0 0 8px rgba(123,231,255,0.55)",
        "halo-signal": "0 0 8px rgba(184,255,102,0.5)",
        "halo-launch": "0 0 8px rgba(255,180,92,0.55)",
      },
      transitionTimingFunction: {
        swarm: tokens.motion.easing,
      },
      transitionDuration: {
        press: tokens.motion.duration.press,
        connect: tokens.motion.duration.connect,
        loader: tokens.motion.duration.loader,
        breath: tokens.motion.duration.breath,
      },
      keyframes: {
        breath: {
          "0%, 100%": { opacity: "0.6" },
          "50%": { opacity: "1.0" },
        },
        revolve: {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
      },
      animation: {
        breath: "breath 4s cubic-bezier(0.2, 0.7, 0.1, 1) infinite",
        revolve: "revolve 900ms cubic-bezier(0.2, 0.7, 0.1, 1) infinite",
      },
    },
  },
  plugins: [],
};

export default config;
