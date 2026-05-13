import type { Config } from "tailwindcss";
import { tokens } from "./lib/tokens";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: tokens.color.bg,
        surface: tokens.color.surface,
        ink: tokens.color.ink,
        muted: tokens.color.muted,
        accent: tokens.color.accent,
        warn: tokens.color.warn,
        crit: tokens.color.crit,
        ok: tokens.color.ok,
      },
      fontFamily: {
        sans: tokens.font.sans,
        mono: tokens.font.mono,
      },
      spacing: tokens.spacing,
      borderRadius: tokens.radius,
    },
  },
  plugins: [],
};

export default config;
