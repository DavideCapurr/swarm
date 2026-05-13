import type { EventLog } from "@/lib/api";

type Props = { events: EventLog[] };

function eventColor(kind: string): string {
  switch (kind) {
    case "anomaly":
      return "text-warn";
    case "progress":
      return "text-accent";
    default:
      return "text-muted";
  }
}

export function EventFeed({ events }: Props) {
  return (
    <div>
      <h2 className="text-xs tracking-[0.2em] text-muted mb-3 orbital-line pb-2">EVENTS</h2>
      <div className="space-y-1 font-mono text-xs">
        {events.length === 0 && (
          <div className="text-muted py-4 text-center">no events yet</div>
        )}
        {events
          .slice()
          .reverse()
          .map((e, i) => (
            <div key={i} className="flex gap-3 py-1 border-b border-line">
              <span className={`uppercase tracking-wider ${eventColor(e.kind)}`}>
                {e.kind}
              </span>
              <span className="text-ink truncate">{JSON.stringify(eventBody(e))}</span>
            </div>
          ))}
      </div>
    </div>
  );
}

function eventBody(e: EventLog): Record<string, unknown> {
  const { kind: _kind, ...rest } = e;
  return rest as Record<string, unknown>;
}
