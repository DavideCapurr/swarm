/**
 * EventFeed — the operator's timeline.
 *
 * Spread 21 (voice mechanics): periods are weapons; sentence case; numerals
 * always digits. Spread 14 (telemetry): time in fixed columns; mono.
 *
 * Reads `TimelineEvent[]` (Phase 1 `Event` projection). Newest at the top.
 */
import type { TimelineEvent } from "@/lib/api";
import { Eyebrow } from "./Eyebrow";

type Props = { events: TimelineEvent[] };

const KIND_CLASS: Record<TimelineEvent["kind"], string> = {
  anomaly: "text-launch-amber",
  verify: "text-orbital-blue",
  operator: "text-orbital-blue",
  patrol: "text-signal-green",
  mission: "text-signal-green",
  dock: "text-muted-silver",
  link: "text-orbital-blue",
  sector: "text-muted-silver",
  system: "text-muted-silver",
};

function timestamp(ts: string): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts.slice(11, 19);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`;
}

function target(e: TimelineEvent): string {
  if (e.agent_id) return e.agent_id;
  if (e.mission_id) return `mission ${e.mission_id.slice(0, 8)}`;
  if (e.anomaly_id) return `anomaly ${e.anomaly_id.slice(0, 4)}`;
  if (e.sector_id) return `sector ${e.sector_id}`;
  if (e.dock_id) return `dock ${e.dock_id}`;
  return "—";
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
        {ordered.slice(0, 50).map((e) => (
          <div
            key={e.id}
            className="grid grid-cols-[88px_72px_140px_1fr] items-baseline gap-4 py-2 border-b border-gunmetal text-ui"
          >
            <span className="mono-num text-ash">{timestamp(e.ts)}</span>
            <span
              className={`font-mono uppercase tracking-eyebrow text-eyebrow ${KIND_CLASS[e.kind]}`}
            >
              {e.kind}
            </span>
            <span className="font-mono uppercase tracking-eyebrow text-eyebrow text-muted-silver truncate">
              {target(e)}
            </span>
            <span className="font-display text-platinum truncate">{e.body}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
