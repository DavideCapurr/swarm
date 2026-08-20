"use client";

import { useEffect, useMemo, useState } from "react";

import { ConsoleSurface, type SurfaceFrame } from "@/components/console/ConsoleSurface";
import {
  TAKE_A,
  TAKE_B,
  TAKE_C,
  foldTakeA,
  foldTakeB,
  foldTakeC,
  takeAFrames,
  takeBFrames,
  takeCFrames,
} from "@/lib/demo-frames";

/**
 * Drives the operational surface from a recorded frame script.
 *
 * Three takes, all stamped `REPLAY · RECORDED FRAMES · NOT LIVE`, on a route
 * that is 404 in a production build:
 *
 *   A — two concurrent single-executor objectives with the BUSY exclusion.
 *   B — one SwarmOS-owned ExecutionGroup, a live member failure, and the
 *       central replacement of the vacated role.
 *   C — a swarm composed under strength, reinforced by a second ExecutionGroup,
 *       the disposition widening to hold both, take B's recorded failure and
 *       replacement landing inside that wide shot, and a second, thirty-
 *       executor sweep objective SwarmOS holds concurrently.
 *
 * `replayBadge` can drop the stamp for layout measurement only.
 */
export type TakeId = "a" | "b" | "c";

const SCRIPT = { a: TAKE_A, b: TAKE_B, c: TAKE_C } as const;
const FRAMES = { a: takeAFrames, b: takeBFrames, c: takeCFrames } as const;
const FOLD = { a: foldTakeA, b: foldTakeB, c: foldTakeC } as const;

export function ReplayHarness({
  initialAtMs = 30_000,
  take = "a",
  replayBadge = true,
}: {
  initialAtMs?: number;
  take?: TakeId;
  replayBadge?: boolean;
}) {
  const script = SCRIPT[take];
  const frames = useMemo(() => FRAMES[take](), [take]);
  const [atMs, setAtMs] = useState(() =>
    Math.max(0, Math.min(script.durationMs, initialAtMs))
  );
  const [playing, setPlaying] = useState(false);

  // Advances by real elapsed wall time rather than a fixed 250 ms tick, so
  // playback reads as continuous motion at whatever frame rate the source
  // frames were actually authored at — the same `dt`-clamped, self-cancelling
  // shape `useCameraGlide` already uses for the camera.
  useEffect(() => {
    if (!playing) return;
    let raf: number;
    let last = performance.now();
    const step = (now: number) => {
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      setAtMs((prev) => {
        const next = prev + dt * 1000;
        return next >= script.durationMs ? 0 : next;
      });
      raf = window.requestAnimationFrame(step);
    };
    raf = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(raf);
  }, [playing, script.durationMs]);

  const slice = useMemo(() => FOLD[take](atMs, frames), [take, atMs, frames]);

  const frame: SurfaceFrame = {
    link: "connected",
    clockText: new Date(script.t0 + atMs).toISOString().slice(11, 19),
    replay: replayBadge,
    ...slice,
  };

  return (
    <div className="relative">
      <ConsoleSurface frame={frame} />
      <div className="fixed bottom-3 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 border border-launch-amber/70 bg-absolute-black/95 px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-launch-amber">
          take {take}
        </span>
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          className="font-mono text-[10px] tracking-[0.16em] text-launch-amber"
        >
          {playing ? "PAUSE" : "PLAY"}
        </button>
        <input
          type="range"
          min={0}
          max={script.durationMs}
          step={250}
          value={atMs}
          onChange={(e) => setAtMs(Number(e.target.value))}
          className="w-[380px] accent-[#FFB45C]"
          aria-label="take position"
        />
        <span className="font-mono text-[10px] tabular-nums text-launch-amber">
          T+{(atMs / 1000).toFixed(1)}s
        </span>
      </div>
    </div>
  );
}
