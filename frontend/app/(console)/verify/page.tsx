"use client";

/**
 * /verify — anomaly intake list. Honest reads from useSwarm; no fetches here.
 */

import Link from "next/link";

import { useSwarm } from "@/lib/state";
import { describeAnomalyKind, describeBand } from "@/lib/derive";
import { Eyebrow } from "@/components/Eyebrow";
import { StatusPill } from "@/components/StatusPill";

export default function VerifyIndex() {
  const { anomalies } = useSwarm();
  const pending = anomalies.filter(
    (a) => a.state === "pending" || a.state === "verifying"
  );
  const resolved = anomalies.filter(
    (a) => a.state === "verified" || a.state === "escalated"
  );

  return (
    <main className="flex-1 px-6 py-6 flex flex-col gap-6 overflow-y-auto">
      <header className="flex items-baseline justify-between">
        <h1 className="font-editorial text-h3 text-platinum">Verification</h1>
        <span className="eyebrow-mono">
          {pending.length} pending · {resolved.length} resolved
        </span>
      </header>

      <Section title="Pending" rows={pending} state="attention" empty="territory quiet · no pending anomaly" />
      <Section title="Resolved" rows={resolved} state="operational" empty="no resolved anomaly this session" />
    </main>
  );
}

function Section({
  title,
  rows,
  state,
  empty,
}: {
  title: string;
  rows: ReturnType<typeof useSwarm>["anomalies"];
  state: "attention" | "operational";
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <Eyebrow mono>{title}</Eyebrow>
      {rows.length === 0 ? (
        <span className="eyebrow-mono text-ash">{empty}</span>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((a) => (
            <li key={a.id}>
              <Link
                href={`/verify/${a.id}`}
                className="card p-4 flex items-baseline justify-between focus:outline-none focus-visible:outline-1 focus-visible:outline-orbital-blue"
              >
                <div className="flex flex-col">
                  <span className="font-mono text-ui text-platinum tracking-eyebrow-mono uppercase">
                    {a.id.slice(0, 4)} · {describeAnomalyKind(a.kind)}
                  </span>
                  <span className="eyebrow-mono">
                    {describeBand(a.band)} · sector {a.sector_id ?? "—"}
                  </span>
                </div>
                <div className="flex items-baseline gap-3">
                  <span className="mono-num text-platinum text-lede">
                    {String(Math.round(a.confidence * 100)).padStart(3, "0")} %
                  </span>
                  <StatusPill state={state}>{a.state}</StatusPill>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
