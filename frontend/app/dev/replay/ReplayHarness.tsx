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
import { augmentTakeCForSwarmStory } from "@/lib/demo-swarm-story";

/**
 * Drives the operational surface from a recorded frame script.
 *
 * Three takes, all stamped `REPLAY · RECORDED FRAMES · NOT LIVE`, on a route
 * that is 404 in a production build:
 *
 *   A — two concurrent single-executor objectives with the BUSY exclusion.
 *   B — one SwarmOS-owned ExecutionGroup, a live member failure, and the
 *       central replacement of the vacated role.
 *   C — a primary swarm composed under strength, a second multi-subunit swarm
 *       dispatched as reinforcement, the disposition widening to hold both,
 *       and take B's recorded failure/replacement landing inside that wide shot.
 *
 * The extra support subunit in take C is explicitly scripted presentation data
 * in `demo-swarm-story.ts`; it never borrows or relabels recorded evidence.
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

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setAtMs((prev) => (prev >= script.durationMs ? 0 : prev + 250));
    }, 250);
    return () => window.clearInterval(id);
  }, [playing, script.durationMs]);

  const rawSlice = useMemo(() => FOLD[take](atMs, frames), [take, atMs, frames]);
  const slice = useMemo(
    () => (take === "c" ? augmentTakeCForSwarmStory(rawSlice, atMs) : rawSlice),
    [take, rawSlice, atMs]
  );

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
