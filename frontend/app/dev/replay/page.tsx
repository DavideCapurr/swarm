import { notFound } from "next/navigation";

import { ReplayHarness } from "./ReplayHarness";

/**
 * Development-only replay of the recorded take.
 *
 * Not part of the product surface: it exists so the operational console can be
 * built and reviewed without a two-instance PX4 SITL bench. It is 404 in a
 * production build and is never linked from the Console.
 */
export const metadata = {
  title: "SWARM · console replay (dev)",
};

export default function ReplayPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <ReplayHarness />;
}
