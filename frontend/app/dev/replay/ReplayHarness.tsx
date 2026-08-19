"use client";

import { useEffect, useMemo, useState } from "react";

import { ConsoleSurface, type SurfaceFrame } from "@/components/console/ConsoleSurface";
import {
  causalTakeCDurationMs,
  foldCausalTakeC,
  isCausalTakeCCapture,
  type CausalTakeCCapture,
} from "@/lib/causal-take-c";
import {
  TAKE_A,
  TAKE_B,
  foldTakeA,
  foldTakeB,
  takeAFrames,
  takeBFrames,
} from "@/lib/demo-frames";

/**
 * Drives the operational surface from recorded truth.
 *
 * A and B retain their historical static bench captures. C is different: it
 * has no authored fallback. The dev/recording workflow must first generate
 * `/public/dev/take-c-causal-sim.json` from the causal simulator runtime. The
 * browser only folds those captured frames; it never chooses executors,
 * creates reinforcement, computes disposition geometry or interpolates
 * physical motion.
 *
 * Every take remains stamped `REPLAY · RECORDED FRAMES · NOT LIVE` unless the
 * badge is explicitly disabled for layout measurement on this dev-only route.
 */
export type TakeId = "a" | "b" | "c";

export function ReplayHarness({
  initialAtMs = 30_000,
  take = "a",
  replayBadge = true,
}: {
  initialAtMs?: number;
  take?: TakeId;
  replayBadge?: boolean;
}) {
  const [causalCapture, setCausalCapture] = useState<CausalTakeCCapture | null>(null);
  const [captureError, setCaptureError] = useState<string | null>(null);

  const staticFrames = useMemo(
    () => (take === "a" ? takeAFrames() : take === "b" ? takeBFrames() : null),
    [take]
  );
  const staticScript = take === "a" ? TAKE_A : take === "b" ? TAKE_B : null;

  useEffect(() => {
    if (take !== "c") {
      setCausalCapture(null);
      setCaptureError(null);
      return;
    }

    let cancelled = false;
    setCausalCapture(null);
    setCaptureError(null);
    void fetch("/dev/take-c-causal-sim.json", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`capture unavailable (${response.status})`);
        }
        const payload: unknown = await response.json();
        if (!isCausalTakeCCapture(payload)) {
          throw new Error("capture failed causal provenance validation");
        }
        if (!cancelled) setCausalCapture(payload);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setCaptureError(error instanceof Error ? error.message : "capture unavailable");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [take]);

  const durationMs =
    take === "c"
      ? causalCapture
        ? causalTakeCDurationMs(causalCapture)
        : 0
      : (staticScript?.durationMs ?? 0);

  const [atMs, setAtMs] = useState(() => Math.max(0, initialAtMs));
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (durationMs <= 0) return;
    setAtMs((current) => Math.min(current, durationMs));
  }, [durationMs]);

  useEffect(() => {
    if (!playing || durationMs <= 0) return;
    const id = window.setInterval(() => {
      setAtMs((prev) => (prev >= durationMs ? 0 : Math.min(durationMs, prev + 250)));
    }, 250);
    return () => window.clearInterval(id);
  }, [playing, durationMs]);

  const slice = useMemo(() => {
    if (take === "a" && staticFrames) return foldTakeA(atMs, staticFrames);
    if (take === "b" && staticFrames) return foldTakeB(atMs, staticFrames);
    if (take === "c" && causalCapture) return foldCausalTakeC(atMs, causalCapture);
    return null;
  }, [take, atMs, staticFrames, causalCapture]);

  if (take === "c" && !slice) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-absolute-black px-8 text-center">
        <div className="max-w-[720px] border border-launch-amber/40 bg-absolute-black/95 p-6 font-mono text-launch-amber">
          <div className="text-[11px] uppercase tracking-[0.22em]">TAKE C · CAUSAL CAPTURE REQUIRED</div>
          <p className="mt-3 text-[11px] leading-5 text-white/65">
            {captureError ?? "Loading generated SwarmOS runtime capture…"}
          </p>
          {captureError ? (
            <p className="mt-3 text-[10px] leading-5 text-white/45">
              Generate frontend/public/dev/take-c-causal-sim.json with
              scripts/capture_causal_take_c_truth.py before replaying or recording Take C.
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  if (!slice) return null;

  const frame: SurfaceFrame = {
    link: "connected",
    clockText: new Date(slice.now).toISOString().slice(11, 19),
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
          max={durationMs}
          step={250}
          value={Math.min(atMs, durationMs)}
          onChange={(event) => setAtMs(Number(event.target.value))}
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
