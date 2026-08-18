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
 * `?label=` and `?replay=0` reproduce the width pressure of the surface that is
 * actually recorded: `/demo/intrusion` carries a longer session label and no
 * REPLAY badge, so the command bar and the control loop have less room there
 * than they do here. Measuring layout on the harness's own defaults would flatter
 * the result. Neither switch invents runtime truth — the frames are the same
 * recorded frames, and dropping the badge is only legitimate because this route
 * is 404 in a production build and is never linked from the Console.
 */
export const metadata = {
  title: "SWARM · console replay (dev)",
};

type ReplayPageProps = {
  searchParams: Promise<{
    at?: string | string[];
    label?: string | string[];
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
  const label = one(params.label);

  return (
    <ReplayHarness
      initialAtMs={initialAtMs}
      sessionLabel={label && label.trim() ? label.trim() : undefined}
      replayBadge={one(params.replay) !== "0"}
    />
  );
}
