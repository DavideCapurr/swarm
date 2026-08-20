import { notFound } from "next/navigation";

import { ReplayHarness, type TakeId } from "./ReplayHarness";

/**
 * Development-only replay of recorded truth.
 *
 * Not part of the product surface: it exists so the operational console can be
 * reviewed without presenting a replay as live operations. It is 404 in a
 * production build and is never linked from the Console.
 *
 * `?at=<milliseconds>` selects a deterministic replay point for visual QA. For
 * Take C this is presentation time over the uniformly time-dilated causal
 * simulator capture; the captured decisions, ordering, positions and server
 * disposition geometry are unchanged.
 *
 * `?take=a|b|c` chooses the source. A and B retain their historical recorded
 * bench fixtures. C has no scripted fallback: the recording workflow generates
 * `/public/dev/take-c-causal-sim.json` from the causal SwarmOS simulator run
 * before the frontend starts, then the browser only folds those captured truth
 * frames.
 *
 * `?replay=0` removes the replay stamp for layout measurement only. `?controls=0`
 * hides the dev scrubber for screenshots/video. Both are presentation flags on
 * this dev-only route and cannot alter captured runtime truth.
 */
export const metadata = {
  title: "SWARM · console replay (dev)",
};

type ReplayPageProps = {
  searchParams: Promise<{
    at?: string | string[];
    take?: string | string[];
    replay?: string | string[];
    controls?: string | string[];
  }>;
};

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ReplayPage({ searchParams }: ReplayPageProps) {
  if (process.env.NODE_ENV === "production") notFound();

  const params = await searchParams;
  const requested = one(params.take);
  const take: TakeId = requested === "b" || requested === "c" ? requested : "a";
  const parsed = Number(one(params.at));
  const defaultAtMs = take === "c" ? 0 : 30_000;
  const initialAtMs = Number.isFinite(parsed) ? parsed : defaultAtMs;

  return (
    <ReplayHarness
      initialAtMs={initialAtMs}
      take={take}
      replayBadge={one(params.replay) !== "0"}
      controls={one(params.controls) !== "0"}
    />
  );
}
