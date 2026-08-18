import { notFound } from "next/navigation";

import { ReplayHarness } from "./ReplayHarness";

/**
 * Development-only replay of the recorded take.
 *
 * Not part of the product surface: it exists so the operational console can be
 * built and reviewed without a two-instance PX4 SITL bench. It is 404 in a
 * production build and is never linked from the Console.
 *
 * `?at=<milliseconds>` selects a deterministic point in the already-recorded
 * frame script for visual QA. It does not create or alter runtime truth.
 *
 * `?take=a|b` chooses the frame script: A is the two concurrent objectives with
 * the BUSY exclusion, B is the SwarmOS-owned ExecutionGroup with a live member
 * failure and central replacement.
 *
 * `?replay=0` reproduces the surface actually recorded, which carries no REPLAY
 * badge. Measuring layout on the harness's own defaults would flatter the
 * result. Neither switch invents runtime truth — the frames are the same
 * recorded frames, and dropping the badge is only legitimate because this route
 * is 404 in a production build and is never linked from the Console.
 */
export const metadata = {
  title: "SWARM · console replay (dev)",
};

type ReplayPageProps = {
  searchParams: Promise<{
    at?: string | string[];
    take?: string | string[];
    replay?: string | string[];
  }>;
};

function one(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function ReplayPage({ searchParams }: ReplayPageProps) {
  if (process.env.NODE_ENV === "production") notFound();

  const params = await searchParams;
  const parsed = Number(one(params.at));
  const initialAtMs = Number.isFinite(parsed) ? parsed : 30_000;
  const take = one(params.take) === "b" ? "b" : "a";

  return (
    <ReplayHarness
      initialAtMs={initialAtMs}
      take={take}
      replayBadge={one(params.replay) !== "0"}
    />
  );
}
