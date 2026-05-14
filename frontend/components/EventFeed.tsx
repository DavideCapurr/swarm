/**
 * EventFeed — the operator's timeline.
 *
 * Spread 21 (voice mechanics): periods are weapons; sentence case; numerals
 * always digits. Spread 14 (telemetry): time in fixed columns; mono.
 *
 * Layout: timestamp (mono) · kind (state-colored eyebrow) · target · body.
 * Newest at the top.
 */
import type { EventLog } from "@/lib/api";
import { Eyebrow } from "./Eyebrow";

type Props = { events: EventLog[] };

function kindClass(kind: string): string {
  switch (kind) {
    case "anomaly":
      return "text-launch-amber";
    case "progress":
      return "text-signal-green";
    case "connected":
      return "text-orbital-blue";
    default:
      return "text-muted-silver";
  }
}

function timestamp(e: EventLog): string {
  const ts = (e.ts as string) ?? "";
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.slice(11, 19);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function target(e: EventLog): string {
  if (typeof e.source_agent === "string" && e.source_agent) return e.source_agent;
  if (typeof e.mission_id === "string" && e.mission_id) {
    return `mission ${e.mission_id.slice(0, 8)}`;
  }
  if (typeof e.id === "string" && e.id) return e.id.slice(0, 8);
  return "—";
}

function body(e: EventLog): string {
  if (e.kind === "anomaly") {
    const kind = (e.anomaly_kind ?? "smoke").toString().toLowerCase();
    const conf = (e.confidence as number) ?? 0;
    const subject =
      kind === "smoke"
        ? "thermal irregularity"
        : kind === "intruder"
          ? "movement pattern"
          : kind;
    const band =
      conf >= 0.85 ? "verified" : conf >= 0.65 ? "medium-confidence" : "low-confidence";
    return `${band} ${subject} · sector requires verification. c ${conf.toFixed(2)}.`;
  }
  if (e.kind === "progress") {
    const phase = (e.phase as string) ?? "—";
    const pct = ((e.progress_pct as number) ?? 0).toFixed(0);
    return `${phase.toLowerCase()} · ${pct}%.`;
  }
  if (e.kind === "telemetry") {
    return "telemetry frame.";
  }
  return JSON.stringify(e).slice(0, 80);
}

export function EventFeed({ events }: Props) {
  const ordered = [...events].reverse();

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-baseline justify-between">
        <Eyebrow mono>Events</Eyebrow>
        <span className="eyebrow-mono">{ordered.length} · last 50</span>
      </div>
      <div className="flex flex-col overflow-y-auto pr-2">
        {ordered.length === 0 && (
          <div className="text-muted-silver text-ui font-mono py-6 text-center">
            no events yet.
          </div>
        )}
        {ordered.slice(0, 50).map((e, i) => (
          <div
            key={i}
            className="grid grid-cols-[88px_72px_120px_1fr] items-baseline gap-4 py-2 border-b border-gunmetal text-ui"
          >
            <span className="mono-num text-ash">{timestamp(e)}</span>
            <span className={`font-mono uppercase tracking-eyebrow text-eyebrow ${kindClass(e.kind)}`}>
              {e.kind}
            </span>
            <span className="font-mono uppercase tracking-eyebrow text-eyebrow text-muted-silver truncate">
              {target(e)}
            </span>
            <span className="font-display text-platinum truncate">{body(e)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
