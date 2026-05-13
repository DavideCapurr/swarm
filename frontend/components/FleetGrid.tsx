import type { FleetMember } from "@/lib/api";

type Props = { fleet: FleetMember[] };

function batteryColor(pct: number): string {
  if (pct < 25) return "text-crit";
  if (pct < 50) return "text-warn";
  return "text-ok";
}

export function FleetGrid({ fleet }: Props) {
  return (
    <div>
      <h2 className="text-xs tracking-[0.2em] text-muted mb-3 orbital-line pb-2">FLEET</h2>
      <div className="space-y-2">
        {fleet.length === 0 && (
          <div className="text-xs text-muted py-6 text-center">no units online</div>
        )}
        {fleet.map((m) => (
          <div
            key={m.agent_id}
            className="border border-line bg-bg p-3 grid grid-cols-[1fr_auto] gap-2"
          >
            <div className="flex flex-col">
              <span className="text-sm font-mono">{m.agent_id}</span>
              <span className="text-[10px] text-muted uppercase tracking-wider">
                {m.vendor} · {m.model}
              </span>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-muted">{m.fsm_state}</div>
              <div className={`text-sm font-mono ${batteryColor(m.battery_pct)}`}>
                {m.battery_pct.toFixed(0)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
