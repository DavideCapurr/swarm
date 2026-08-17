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
 */
export const metadata = {
  title: "SWARM · console replay (dev)",
};

type ReplayPageProps = {
  searchParams: Promise<{ at?: string | string[] }>;
};

export default async function ReplayPage({ searchParams }: ReplayPageProps) {
  if (process.env.NODE_ENV === "production") notFound();

  const params = await searchParams;
  const rawAt = Array.isArray(params.at) ? params.at[0] : params.at;
  const parsed = Number(rawAt);
  const initialAtMs = Number.isFinite(parsed) ? parsed : 30_000;

  return <ReplayHarness initialAtMs={initialAtMs} />;
}
