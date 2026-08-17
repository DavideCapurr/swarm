"use client";

import { useEffect, useMemo, useState } from "react";

import { OperationalConsole, type ConsoleFrame } from "@/components/ops/OperationalConsole";
import { TAKE_A, foldTakeA, takeAFrames } from "@/lib/demo-frames";

/**
 * Drives the operational console from the recorded frame script.
 *
 * Everything the console renders here is stamped REPLAY by the command bar, so
 * it can never be mistaken for live SwarmOS truth.
 */
export function ReplayHarness({ initialAtMs = 30_000 }: { initialAtMs?: number }) {
  const frames = useMemo(() => takeAFrames(), []);
  const [atMs, setAtMs] = useState(() =>
    Math.max(0, Math.min(TAKE_A.durationMs, initialAtMs))
  );
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => {
      setAtMs((prev) => (prev >= TAKE_A.durationMs ? 0 : prev + 250));
    }, 250);
    return () => window.clearInterval(id);
  }, [playing]);

  const slice = useMemo(() => foldTakeA(atMs, frames), [atMs, frames]);

  const frame: ConsoleFrame = {
    link: "connected",
    sessionLabel: "take a · recorded",
    operatorId: "replay",
    role: "viewer",
    clockText: new Date(TAKE_A.t0 + atMs).toISOString().slice(11, 19),
    replay: true,
    executionGroups: [],
    ...slice,
  };

  return (
    <div className="relative">
      <OperationalConsole frame={frame} />
      <div className="fixed bottom-4 right-6 z-50 flex items-center gap-3 border border-launch-amber bg-absolute-black px-3 py-2">
        <button
          type="button"
          onClick={() => setPlaying((p) => !p)}
          className="font-mono text-[11px] tracking-[0.16em] text-launch-amber"
        >
          {playing ? "PAUSE" : "PLAY"}
        </button>
        <input
          type="range"
          min={0}
          max={TAKE_A.durationMs}
          step={250}
          value={atMs}
          onChange={(e) => setAtMs(Number(e.target.value))}
          className="w-[420px] accent-[#FFB45C]"
          aria-label="take position"
        />
        <span className="font-mono text-[11px] tabular-nums text-launch-amber">
          T+{(atMs / 1000).toFixed(1)}s
        </span>
      </div>
    </div>
  );
}
