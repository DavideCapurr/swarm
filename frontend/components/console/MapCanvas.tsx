"use client";

/**
 * MapCanvas — the application ground.
 *
 * The map is not a panel on this surface; it is the surface. Satellite imagery
 * fills the viewport and every operating surface floats over it.
 *
 * The imagery is treated, not recoloured. Real-world colour is what makes the
 * physical world read as physical — the contrast between subdued earth and the
 * graphite of SwarmOS is the composition — so the treatment only lowers
 * brightness, pulls saturation back moderately, lifts mid-tone contrast a
 * little, and clamps the few blown highlights that would otherwise punch
 * through the interface. No global tint, no LUT, no filter cast.
 *
 * The imagery carries no operational claim. When the tile host does not answer
 * the surface says so and the site frame stands alone: every executor,
 * objective, assignment and track is projected from server frames and stays
 * authoritative either way.
 */

import { useEffect, useState, type ReactNode } from "react";

import {
  IMAGERY_ATTRIBUTION,
  IMAGERY_UNAVAILABLE,
  type Tile,
} from "./projection";

/**
 * Imagery treatment.
 *
 * Tuned against the recording, in this order: saturation held so vegetation
 * and roofs keep their identity without competing with state colour; contrast
 * up slightly for local separation; brightness pulled back just enough that
 * the black interface still reads above the world.
 *
 * An earlier pass at brightness(0.47) plus a 0.28 ground overlay made the
 * physical world read as a decorative dark backdrop rather than the thing this
 * software is actually deciding about — the map was losing the argument with
 * its own restraint. This is the brighter half of that same ramp: still
 * subdued, no longer receding.
 *
 * The exact value is bounded, not chosen by eye: platinum captions sit
 * directly over live imagery, and the design system's own rule is that
 * legibility outranks depth. Measured through this filter chain plus the
 * highlight clamp and the ground overlay below, worst case — a blown highlight
 * (bare concrete, a roof) directly under a platinum caption — holds 5.80:1,
 * clear of the 4.5:1 AA floor this console holds every other readout to. A
 * first pass at brightness(0.58) with the old, looser clamp only reached
 * 4.30:1 on the same case; HIGHLIGHT_CLAMP was tightened alongside the
 * brightness increase specifically to keep that margin.
 */
const IMAGERY_FILTER = "saturate(0.72) contrast(1.14) brightness(0.56)";

/**
 * Highlight clamp.
 *
 * `darken` holds every channel at or below this value, so blown roofs, bare
 * concrete and specular water stop short of the interface's own tone instead of
 * flaring behind the panels. Below the clamp nothing changes — mid-tones and
 * shadows pass through untouched, which is why this is not another brightness
 * reduction. Set to hold AA contrast for map captions at the current
 * brightness — see the note on IMAGERY_FILTER for the measured worst case.
 */
const HIGHLIGHT_CLAMP = "#70767c";

export type ImageryStatus = "pending" | "ok" | "unavailable";

/**
 * Whether the tile host actually answered.
 *
 * Tiles are drawn as images, but a single representative probe is what the
 * attribution strip is allowed to speak from — the strip may not claim imagery
 * the recording machine could not reach.
 */
export function useImageryStatus(sampleUrl: string | null): ImageryStatus {
  const [status, setStatus] = useState<ImageryStatus>("pending");

  useEffect(() => {
    if (!sampleUrl) {
      setStatus("pending");
      return;
    }
    let cancelled = false;
    const probe = new window.Image();
    probe.onload = () => {
      if (!cancelled) setStatus("ok");
    };
    probe.onerror = () => {
      if (!cancelled) setStatus("unavailable");
    };
    probe.src = sampleUrl;
    return () => {
      cancelled = true;
      probe.onload = null;
      probe.onerror = null;
    };
  }, [sampleUrl]);

  return status;
}

function TileLayer({ tiles }: { tiles: Tile[] }) {
  return (
    <div
      className="absolute inset-0"
      data-testid="satellite-imagery"
      style={{ filter: IMAGERY_FILTER }}
    >
      {tiles.map((tile) => (
        /* Not `next/image`. These are Web Mercator raster tiles positioned by
           the projection: the source is an external tile server pinned in the
           Console CSP, the URL set changes with the camera, and the optimizer
           would proxy every tile through the Next server for no benefit. The
           rule is about page-weight regressions on content images; a tile grid
           is not one. */
        // eslint-disable-next-line @next/next/no-img-element
        <img
          key={tile.key}
          src={tile.url}
          alt=""
          aria-hidden="true"
          draggable={false}
          decoding="async"
          className="absolute max-w-none select-none"
          style={{
            left: tile.left,
            top: tile.top,
            width: tile.size,
            height: tile.size,
            opacity: 0,
            transition: "opacity 260ms cubic-bezier(0.2, 0.7, 0.1, 1)",
          }}
          /* Written straight to the node: a tile arriving must not re-render
             the scene, and there are dozens of them in flight at once.

             The ref is not redundant. A tile already in the HTTP cache — every
             tile, on the second render of a take — is complete before React
             attaches `onLoad`, so the event never fires and the image would
             hold at zero opacity forever. That is precisely the case a
             recording hits. */
          ref={(node) => {
            if (node?.complete && node.naturalWidth > 0) node.style.opacity = "1";
          }}
          onLoad={(event) => {
            event.currentTarget.style.opacity = "1";
          }}
        />
      ))}
    </div>
  );
}

export function MapCanvas({
  tiles,
  status,
  children,
}: {
  tiles: Tile[];
  status: ImageryStatus;
  children: ReactNode;
}) {
  return (
    <div
      className="absolute inset-0 overflow-hidden bg-[#050605]"
      /* The blend layers below must compose against the imagery only, never
         against whatever the page paints underneath. */
      style={{ isolation: "isolate" }}
    >
      <TileLayer tiles={tiles} />

      {/* Highlight clamp — see HIGHLIGHT_CLAMP. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{ mixBlendMode: "darken", background: HIGHLIGHT_CLAMP }}
      />

      {/* Ground tone. Sits under the interface and over the world, so the two
          never meet at full imagery brightness. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{ background: "rgba(5, 6, 5, 0.22)" }}
      />

      {/* Vignette — deliberately weak. It settles the frame edges under the
          floating surfaces; it is not a cinematic effect. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(118% 98% at 46% 48%, rgba(5,6,5,0) 42%, rgba(5,6,5,0.26) 80%, rgba(5,6,5,0.52) 100%)",
        }}
      />

      {children}

      <div
        data-testid="imagery-attribution"
        className="pointer-events-none absolute bottom-[10px] right-[14px] z-30 font-mono text-[9px] uppercase leading-none tracking-[0.16em] text-ash/70"
      >
        {status === "ok"
          ? IMAGERY_ATTRIBUTION
          : status === "unavailable"
            ? IMAGERY_UNAVAILABLE
            : "SATELLITE IMAGERY PENDING · SITE FRAME ONLY"}
      </div>
    </div>
  );
}
