"use client";

/**
 * useCameraGlide — moves the camera to where the mission is.
 *
 * `targetFrame` recomputes the framing the mission wants on every render. Using
 * it directly would snap, and a map that snaps is unwatchable. This glides:
 * each frame the held camera moves a fixed fraction of the remaining distance
 * to the target, which is exponential decay — no spring, no overshoot, no
 * settling wobble. The result is a camera that is always arriving and never
 * arrives abruptly.
 *
 * Extent is smoothed in log space, so zooming out by a factor of two takes the
 * same time as zooming in by a factor of two. Smoothed linearly, a long transit
 * opening up reads as a lurch and the close-in reads as a crawl.
 *
 * It stops. Once the camera is within epsilon of its target the loop cancels
 * itself, so a scene at rest costs nothing and a paused recording frame is
 * exactly reproducible.
 */

import { useEffect, useRef, useState } from "react";

import type { LocalPoint, MapGeo } from "@/lib/opsmap";

/** Seconds to close ~63% of the remaining distance. Extent trails the pan. */
const TAU_CENTER_S = 0.45;
const TAU_EXTENT_S = 0.62;

/** Below these the camera is considered arrived, and the loop shuts down. */
const EPSILON_M = 0.15;
const EPSILON_RATIO = 0.004;

export type Camera = { origin: MapGeo | null; center: LocalPoint; extentM: number };

function near(held: Camera, target: Camera): boolean {
  const panned = Math.hypot(target.center.e - held.center.e, target.center.n - held.center.n);
  const zoomed = Math.abs(Math.log(target.extentM / held.extentM));
  return panned < EPSILON_M && zoomed < EPSILON_RATIO;
}

export function useCameraGlide(target: Camera): Camera {
  const [camera, setCamera] = useState<Camera>(target);
  const heldRef = useRef<Camera>(target);
  const targetRef = useRef<Camera>(target);
  const rafRef = useRef<number | null>(null);
  const lastRef = useRef<number>(0);

  targetRef.current = target;

  // The first frame with a real origin is a cut, not a move: there is nothing
  // to glide from, and easing in from a placeholder would read as a zoom the
  // mission did not ask for.
  if (heldRef.current.origin === null && target.origin !== null) {
    heldRef.current = target;
  }

  useEffect(() => {
    const step = (now: number) => {
      const held = heldRef.current;
      const want = targetRef.current;
      const dt = lastRef.current ? Math.min(0.1, (now - lastRef.current) / 1000) : 1 / 60;
      lastRef.current = now;

      if (!want.origin || near(held, want)) {
        heldRef.current = want;
        setCamera(want);
        rafRef.current = null;
        lastRef.current = 0;
        return;
      }

      const kCenter = 1 - Math.exp(-dt / TAU_CENTER_S);
      const kExtent = 1 - Math.exp(-dt / TAU_EXTENT_S);
      const next: Camera = {
        origin: want.origin,
        center: {
          e: held.center.e + (want.center.e - held.center.e) * kCenter,
          n: held.center.n + (want.center.n - held.center.n) * kCenter,
        },
        // Log-space, so a factor of two costs the same in either direction.
        extentM: Math.exp(
          Math.log(held.extentM) +
            (Math.log(want.extentM) - Math.log(held.extentM)) * kExtent
        ),
      };
      heldRef.current = next;
      setCamera(next);
      rafRef.current = window.requestAnimationFrame(step);
    };

    if (rafRef.current === null && !near(heldRef.current, target)) {
      lastRef.current = 0;
      rafRef.current = window.requestAnimationFrame(step);
    }

    return () => {
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
  }, [target]);

  return camera;
}
