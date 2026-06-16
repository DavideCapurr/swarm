import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import {
  BASEMAPS,
  BASEMAP_STORAGE_KEY,
  BasemapSwitch,
  STATE_COLOR,
  readStoredBasemap,
  type BasemapMode,
} from "@/components/Map";
import { tokens } from "@/lib/tokens";

// next.config.mjs cannot be executed under vitest (its top-level
// `fileURLToPath(import.meta.url)` is not a file URL once transformed), so we
// assert against its source text — the host allowlist lives there literally.
const NEXT_CONFIG = readFileSync(
  resolve(process.cwd(), "next.config.mjs"),
  "utf8"
);

// ── Basemap toggle persistence ──────────────────────────────────────────────

describe("readStoredBasemap", () => {
  it("defaults to the tactical (dark, design-system) basemap", () => {
    expect(readStoredBasemap()).toBe("tactical");
  });

  it("round-trips a stored mode", () => {
    window.localStorage.setItem(BASEMAP_STORAGE_KEY, "satellite");
    expect(readStoredBasemap()).toBe("satellite");
  });

  it("ignores a corrupt stored value and falls back to tactical", () => {
    window.localStorage.setItem(BASEMAP_STORAGE_KEY, "moon-relief");
    expect(readStoredBasemap()).toBe("tactical");
  });
});

// ── Basemap selector UI ─────────────────────────────────────────────────────

describe("BasemapSwitch", () => {
  it("renders both modes and marks the active one pressed", () => {
    render(<BasemapSwitch mode="tactical" onChange={() => {}} />);
    const tactical = screen.getByTestId("basemap-tactical");
    const satellite = screen.getByTestId("basemap-satellite");
    expect(tactical).toHaveAttribute("aria-pressed", "true");
    expect(satellite).toHaveAttribute("aria-pressed", "false");
  });

  it("emits the chosen mode on click", () => {
    const onChange = vi.fn();
    render(<BasemapSwitch mode="tactical" onChange={onChange} />);
    fireEvent.click(screen.getByTestId("basemap-satellite"));
    expect(onChange).toHaveBeenCalledWith("satellite");
  });
});

// ── Basemap config integrity ────────────────────────────────────────────────

describe("BASEMAPS", () => {
  const modes = Object.keys(BASEMAPS) as BasemapMode[];

  it("offers exactly the tactical + satellite modes", () => {
    expect(new Set(modes)).toEqual(new Set(["tactical", "satellite"]));
  });

  it("gives every basemap at least one tile URL and a licence attribution", () => {
    for (const mode of modes) {
      const cfg = BASEMAPS[mode];
      expect(cfg.tiles.length).toBeGreaterThan(0);
      expect(cfg.attribution.trim().length).toBeGreaterThan(0);
      expect(cfg.opacity).toBeGreaterThan(0);
      expect(cfg.opacity).toBeLessThanOrEqual(1);
    }
  });
});

// ── CSP ↔ basemap host invariant ────────────────────────────────────────────
// Every basemap tile host must be allowlisted in next.config's CSP connect-src,
// or the tiles silently fail to load in prod. This binds the M0 CSP deliverable
// to the basemap config so adding a basemap without updating the CSP fails CI.

describe("next.config CSP covers every basemap tile host", () => {
  it("allowlists each tile host in the config", () => {
    for (const mode of Object.keys(BASEMAPS) as BasemapMode[]) {
      for (const tile of BASEMAPS[mode].tiles) {
        const host = new URL(tile).host;
        expect(NEXT_CONFIG).toContain(host);
      }
    }
  });

  it("pins the basemap hosts in a connect-src directive", () => {
    expect(NEXT_CONFIG).toContain("MAP_CONNECT_SRC");
    expect(NEXT_CONFIG).toMatch(/connect-src/);
  });

  it("keeps img-src open to https so raster tiles can paint", () => {
    expect(NEXT_CONFIG).toMatch(/img-src[^"]*https:/);
  });
});

// ── Per-state marker colours ────────────────────────────────────────────────

describe("STATE_COLOR (per-state markers)", () => {
  it("covers every swarm state with the documented accent token", () => {
    expect(STATE_COLOR).toEqual({
      rest: tokens.color.platinum,
      connected: tokens.color.orbitalBlue,
      operational: tokens.color.signalGreen,
      attention: tokens.color.launchAmber,
    });
  });

  it("uses amber (never red) for the attention state — design-system §5.2", () => {
    // No-red guard: a red-dominant marker would violate the hard rule that
    // escalation/attention is amber, not red.
    const isRed = (hex: string) => {
      const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex);
      if (!m) return false;
      const [r, g, b] = [m[1], m[2], m[3]].map((h) => parseInt(h, 16));
      return r > 160 && g < 110 && b < 110; // red-dominant, low green/blue
    };
    for (const color of Object.values(STATE_COLOR)) {
      expect(isRed(color)).toBe(false);
    }
  });
});
