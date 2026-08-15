"use client";

import { useMemo } from "react";

import type {
  AllocationDecision,
  AllocationEligibleUnit,
  AllocationExcludedUnit,
  AnomalyView,
  MissionRuntimeEvent,
  PayloadEvent,
} from "@/lib/api";
import { useSwarm } from "@/lib/state";

const CCTV_VIDEO = "/sim-feed/intrusion-pov.mp4";
const DRONE_VIDEO = "/sim-feed/drone-pov.mp4";

function shortId(value: string | null | undefined): string {
  if (!value) return "—";
  return value.length <= 10 ? value : `${value.slice(0, 8)}…`;
}

function clock(ts: string | null | undefined): string {
  if (!ts) return "—";
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function score(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(3);
}

function phaseLabel(phase: string | null | undefined): string {
  if (!phase) return "AWAITING RUNTIME";
  return phase.replaceAll("_", " ").toUpperCase();
}

function evidenceLabel(event: MissionRuntimeEvent | undefined): string | null {
  if (!event?.evidence) return null;
  if (event.evidence === "mavlink_mission_item_reached") {
    return "MISSION_ITEM_REACHED";
  }
  if (event.evidence === "mavlink_rtl_command_acknowledged") {
    return "RTL COMMAND ACKNOWLEDGED";
  }
  return null;
}

function payloadMode(event: PayloadEvent): string {
  if (event.execution_mode === "mavlink_output_confirmed") {
    return "PX4 OUTPUT CONFIRMED";
  }
  if (event.execution_mode === "mavlink_ack") return "MAVLINK ACK";
  if (event.execution_mode === "simulated") return "SIMULATED";
  return event.status.toUpperCase();
}

function payloadAction(event: PayloadEvent): string {
  const labels: Record<PayloadEvent["kind"], string> = {
    light_on: "LIGHT ON",
    light_off: "LIGHT OFF",
    play_message: "SPEAKER ACTIVE",
    stop_message: "SPEAKER STOPPED",
  };
  return labels[event.kind];
}

function anomalyFor(
  decision: AllocationDecision | undefined,
  anomalies: Map<string, AnomalyView>
): AnomalyView | undefined {
  if (!decision?.anomaly_id) return undefined;
  return anomalies.get(decision.anomaly_id);
}

function selectDemoDecisions(
  allocations: AllocationDecision[],
  anomalies: Map<string, AnomalyView>
): AllocationDecision[] {
  const ordered = allocations
    .filter((decision) => decision.mission_kind === "VERIFY")
    .slice()
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  if (ordered.length <= 2) return ordered;

  // Prefer the most recent intrusion that has a following allocation so the
  // two-event story remains visible after a longer bench session. This chooses
  // which server frames to show; it never recomputes an allocation decision.
  for (let index = ordered.length - 2; index >= 0; index -= 1) {
    const anomaly = anomalyFor(ordered[index], anomalies);
    if (anomaly?.kind === "INTRUSION") {
      return [ordered[index], ordered[index + 1]];
    }
  }

  return ordered.slice(-2);
}

function EligibleRow({ unit }: { unit: AllocationEligibleUnit }) {
  const reason = unit.score_breakdown;
  return (
    <div className="grid grid-cols-[minmax(90px,0.8fr)_90px_74px_minmax(0,1.7fr)] items-center gap-3 border-t border-white/10 py-3 text-[11px]">
      <div className="font-mono text-paper">{unit.agent_id}</div>
      <div className="font-mono text-status-online">ELIGIBLE</div>
      <div className="font-mono tabular-nums text-paper">{score(unit.score)}</div>
      <div className="min-w-0 font-mono text-text-muted">
        {Math.round(reason.distance_m)}m · batt {reason.battery_pct.toFixed(0)}% · dist +
        {reason.distance_score.toFixed(2)} · batt +{reason.battery_score.toFixed(2)} · priority +
        {reason.priority_score.toFixed(2)}
      </div>
    </div>
  );
}

function ExcludedRow({ unit }: { unit: AllocationExcludedUnit }) {
  return (
    <div
      data-testid={`excluded-${unit.agent_id}`}
      className="grid grid-cols-[minmax(90px,0.8fr)_90px_74px_minmax(0,1.7fr)] items-center gap-3 border-t border-white/10 py-3 text-[11px]"
    >
      <div className="font-mono text-paper">{unit.agent_id}</div>
      <div className="font-mono text-status-caution">EXCLUDED</div>
      <div className="font-mono text-text-muted">—</div>
      <div className="font-mono text-text-muted">
        {unit.reason}
        {unit.active_mission_id ? ` · mission ${shortId(unit.active_mission_id)}` : ""}
      </div>
    </div>
  );
}

function AllocationPanel({ decision }: { decision: AllocationDecision | undefined }) {
  if (!decision) {
    return (
      <section className="border-y border-white/10 py-5">
        <div className="eyebrow-mono text-text-muted">ALLOCATION DECISION</div>
        <div className="mt-5 font-editorial text-2xl text-paper">Waiting for allocator frame.</div>
        <p className="mt-2 max-w-xl text-sm leading-6 text-text-muted">
          No candidate, score, exclusion or winner is rendered until the orchestrator publishes it.
        </p>
      </section>
    );
  }

  return (
    <section className="border-y border-white/10 py-5" aria-label="Allocation decision">
      <div className="flex items-start justify-between gap-6">
        <div>
          <div className="eyebrow-mono text-orbital-blue">ALLOCATION DECISION</div>
          <div className="mt-2 font-editorial text-2xl text-paper">
            {decision.mode === "auction" ? "Fleet auction" : decision.mode.toUpperCase()}
          </div>
        </div>
        <div className="text-right font-mono text-[10px] leading-5 text-text-muted">
          <div>{clock(decision.ts)}</div>
          <div>MISSION {shortId(decision.mission_id)}</div>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-[minmax(90px,0.8fr)_90px_74px_minmax(0,1.7fr)] gap-3 pb-2 font-mono text-[9px] tracking-[0.15em] text-text-muted">
        <span>UNIT</span>
        <span>STATUS</span>
        <span>SCORE</span>
        <span>SERVER REASONS</span>
      </div>
      {decision.eligible_units.map((unit) => (
        <EligibleRow key={unit.agent_id} unit={unit} />
      ))}
      {decision.excluded_units.map((unit) => (
        <ExcludedRow key={unit.agent_id} unit={unit} />
      ))}

      <div className="mt-2 flex items-baseline justify-between border-t border-white/20 pt-4">
        <span className="eyebrow-mono text-text-muted">WINNER</span>
        <div className="text-right">
          <span className="font-editorial text-2xl text-paper">
            {decision.winner_agent_id ?? "NO AWARD"}
          </span>
          {decision.winner_score != null ? (
            <span className="ml-3 font-mono text-xs text-orbital-blue">
              {score(decision.winner_score)}
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}

function SituationFeed({ intrusion }: { intrusion: AnomalyView | undefined }) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between">
        <div>
          <div className="eyebrow-mono text-text-muted">PERIMETER CCTV · VISUALIZATION</div>
          <div className="mt-1 font-editorial text-2xl text-paper">North perimeter</div>
        </div>
        <div className="font-mono text-[10px] text-status-caution">SIMULATED STOCK FOOTAGE</div>
      </div>
      <div className="relative aspect-video overflow-hidden border border-white/15 bg-black">
        <video
          aria-label="Simulated perimeter CCTV"
          className="h-full w-full object-cover opacity-80"
          src={CCTV_VIDEO}
          autoPlay
          muted
          loop
          playsInline
        />
        <div className="absolute left-4 top-4 border border-white/25 bg-black/75 px-2 py-1 font-mono text-[9px] tracking-[0.14em] text-paper">
          CAM VISUALIZATION · 04
        </div>
        {intrusion ? (
          <>
            <div className="absolute left-[48%] top-[23%] h-[54%] w-[18%] border border-status-caution" />
            <div className="absolute bottom-4 left-4 right-4 flex items-end justify-between gap-4 bg-black/80 px-3 py-2">
              <div>
                <div className="font-mono text-[10px] tracking-[0.12em] text-status-caution">
                  INTRUSION DETECTED
                </div>
                <div className="mt-1 font-mono text-[10px] text-text-muted">
                  EVENT {shortId(intrusion.id)} · SOURCE {intrusion.detected_by ?? "SWARM ANOMALY BUS"}
                </div>
              </div>
              <div className="font-mono text-sm tabular-nums text-paper">
                {(intrusion.confidence * 100).toFixed(0)}%
              </div>
            </div>
          </>
        ) : (
          <div className="absolute inset-x-4 bottom-4 bg-black/80 px-3 py-2 font-mono text-[10px] text-text-muted">
            WAITING FOR BACKEND INTRUSION EVENT
          </div>
        )}
      </div>
    </section>
  );
}

function DroneFeed({ runtime }: { runtime: MissionRuntimeEvent | undefined }) {
  const proof = evidenceLabel(runtime);
  return (
    <section>
      <div className="mb-3 flex items-end justify-between">
        <div>
          <div className="eyebrow-mono text-text-muted">DRONE FEED · VISUALIZATION</div>
          <div className="mt-1 font-editorial text-2xl text-paper">
            {runtime?.agent_id ?? "Awaiting dispatch"}
          </div>
        </div>
        <div className="font-mono text-[10px] text-status-caution">SIMULATED DRONE VIEW</div>
      </div>
      <div className="relative aspect-video overflow-hidden border border-white/15 bg-black">
        <video
          aria-label="Simulated drone view"
          className="h-full w-full object-cover opacity-75"
          src={DRONE_VIDEO}
          autoPlay
          muted
          loop
          playsInline
        />
        <div className="absolute inset-x-4 bottom-4 flex items-end justify-between gap-4 bg-black/80 px-3 py-2">
          <div>
            <div className="font-mono text-[10px] tracking-[0.12em] text-paper">
              {phaseLabel(runtime?.phase)}
            </div>
            <div className="mt-1 font-mono text-[10px] text-text-muted">
              {runtime ? `MISSION ${shortId(runtime.mission_id)}` : "NO MISSION RUNTIME FRAME"}
            </div>
          </div>
          <div className="text-right">
            {runtime ? (
              <div className="font-mono text-xs tabular-nums text-paper">
                {runtime.progress_pct.toFixed(0)}%
              </div>
            ) : null}
            {proof ? (
              <div className="mt-1 font-mono text-[9px] tracking-[0.1em] text-status-online">
                {proof}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function MissionLedger({
  decisions,
  anomalies,
  runtimeByMission,
}: {
  decisions: AllocationDecision[];
  anomalies: Map<string, AnomalyView>;
  runtimeByMission: Map<string, MissionRuntimeEvent>;
}) {
  return (
    <section>
      <div className="eyebrow-mono text-text-muted">ACTIVE / RECENT MISSIONS</div>
      <div className="mt-3 border-t border-white/10">
        {decisions.length === 0 ? (
          <div className="py-5 font-mono text-[11px] text-text-muted">NO MISSION OWNERSHIP FRAME</div>
        ) : (
          decisions.map((decision, index) => {
            const anomaly = anomalyFor(decision, anomalies);
            const runtime = runtimeByMission.get(decision.mission_id);
            const proof = evidenceLabel(runtime);
            return (
              <div
                key={decision.mission_id}
                data-testid={`mission-${decision.mission_id}`}
                className="grid grid-cols-[36px_minmax(0,1.4fr)_minmax(100px,0.8fr)] gap-3 border-b border-white/10 py-4"
              >
                <div className="font-mono text-[10px] text-text-muted">0{index + 1}</div>
                <div>
                  <div className="font-mono text-[10px] tracking-[0.1em] text-paper">
                    {anomaly?.kind ?? decision.mission_kind} · {shortId(decision.mission_id)}
                  </div>
                  <div className="mt-1 text-sm text-text-muted">
                    owner <span className="font-mono text-paper">{decision.winner_agent_id ?? "—"}</span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-[10px] text-orbital-blue">
                    {phaseLabel(runtime?.phase ?? (decision.winner_agent_id ? "allocated" : "no_award"))}
                  </div>
                  {proof ? (
                    <div className="mt-1 font-mono text-[9px] text-status-online">{proof}</div>
                  ) : null}
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

function ResponseLedger({ events }: { events: PayloadEvent[] }) {
  const ordered = events.slice().sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  return (
    <section>
      <div className="eyebrow-mono text-text-muted">PHYSICAL RESPONSE LEDGER</div>
      <div className="mt-3 border-t border-white/10">
        {ordered.length === 0 ? (
          <div className="py-5 font-mono text-[11px] text-text-muted">
            NO PAYLOAD RESULT PUBLISHED
          </div>
        ) : (
          ordered.slice(-6).map((event) => (
            <div
              key={event.id}
              className="grid grid-cols-[68px_minmax(0,1fr)_minmax(150px,0.9fr)] gap-3 border-b border-white/10 py-3 text-[10px]"
            >
              <div className="font-mono text-text-muted">{clock(event.ts)}</div>
              <div>
                <div className="font-mono text-paper">{payloadAction(event)}</div>
                <div className="mt-1 font-mono text-text-muted">
                  {event.agent_id} · {shortId(event.mission_id)}
                </div>
              </div>
              <div
                className={`text-right font-mono ${
                  event.execution_mode === "simulated" ? "text-status-caution" : "text-status-online"
                }`}
              >
                {payloadMode(event)}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function FleetStrip({ decisions }: { decisions: AllocationDecision[] }) {
  const { units } = useSwarm();
  const ownership = new Map<string, string>();
  for (const decision of decisions) {
    if (decision.winner_agent_id) ownership.set(decision.winner_agent_id, decision.mission_id);
  }

  return (
    <section className="border-t border-white/10 pt-4">
      <div className="eyebrow-mono text-text-muted">FLEET · SERVER STATE</div>
      <div className="mt-3 grid gap-px border-y border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-3">
        {units.length === 0 ? (
          <div className="bg-void px-4 py-4 font-mono text-[10px] text-text-muted">WAITING FOR FLEET STATE</div>
        ) : (
          units.map((unit) => (
            <div key={unit.agent_id} className="bg-void px-4 py-4">
              <div className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-xs text-paper">{unit.agent_id}</span>
                <span className="font-mono text-[9px] text-orbital-blue">{unit.fsm_state}</span>
              </div>
              <div className="mt-2 flex justify-between font-mono text-[10px] text-text-muted">
                <span>batt {unit.battery_pct.toFixed(0)}%</span>
                <span>{ownership.has(unit.agent_id) ? `mission ${shortId(ownership.get(unit.agent_id))}` : "unassigned"}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export function IntrusionResponseDemo() {
  const { allocations, anomalies, missionRuntime, payloadEvents, link } = useSwarm();

  const anomalyMap = useMemo(
    () => new Map(anomalies.map((anomaly) => [anomaly.id, anomaly])),
    [anomalies]
  );
  const decisions = useMemo(
    () => selectDemoDecisions(allocations, anomalyMap),
    [allocations, anomalyMap]
  );
  const runtimeByMission = useMemo(
    () => new Map(missionRuntime.map((event) => [event.mission_id, event])),
    [missionRuntime]
  );
  const firstDecision = decisions[0];
  const secondDecision = decisions[1];
  const currentDecision = secondDecision ?? firstDecision;
  const intrusion = decisions
    .map((decision) => anomalyFor(decision, anomalyMap))
    .find((anomaly) => anomaly?.kind === "INTRUSION");

  const focusRuntime = useMemo(() => {
    const active = decisions
      .slice()
      .reverse()
      .map((decision) => runtimeByMission.get(decision.mission_id))
      .find((runtime) => runtime && runtime.phase !== "DONE" && runtime.phase !== "FAILED");
    if (active) return active;
    return currentDecision ? runtimeByMission.get(currentDecision.mission_id) : undefined;
  }, [decisions, currentDecision, runtimeByMission]);

  const demoMissionIds = new Set(decisions.map((decision) => decision.mission_id));
  const demoPayloadEvents = payloadEvents.filter((event) => demoMissionIds.has(event.mission_id));

  return (
    <main className="min-h-screen bg-void text-paper">
      <header className="border-b border-white/10 px-5 py-4 lg:px-8">
        <div className="mx-auto flex max-w-[1600px] items-end justify-between gap-6">
          <div>
            <div className="eyebrow-mono text-orbital-blue">SWARM / INCIDENT CONSOLE</div>
            <h1 className="mt-1 font-editorial text-3xl tracking-tight text-paper lg:text-4xl">
              Perimeter response
            </h1>
          </div>
          <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.12em]">
            <span className={link === "connected" ? "text-status-online" : "text-status-caution"}>
              {link.toUpperCase()}
            </span>
            <span className="text-white/20">/</span>
            <span className="text-text-muted">SWARM RUNTIME LIVE · IMAGERY SIMULATED</span>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1600px] px-5 py-6 lg:px-8 lg:py-8">
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1.35fr)_minmax(440px,0.8fr)]">
          <div className="space-y-7">
            <SituationFeed intrusion={intrusion} />
            <DroneFeed runtime={focusRuntime} />
          </div>

          <div className="space-y-7">
            <AllocationPanel decision={currentDecision} />
            <MissionLedger
              decisions={decisions}
              anomalies={anomalyMap}
              runtimeByMission={runtimeByMission}
            />
            <ResponseLedger events={demoPayloadEvents} />
          </div>
        </div>

        <div className="mt-8">
          <FleetStrip decisions={decisions} />
        </div>

        <footer className="mt-6 flex flex-col justify-between gap-2 border-t border-white/10 pt-4 font-mono text-[9px] leading-5 text-text-muted md:flex-row">
          <span>Console renders allocator, runtime and payload frames. It does not calculate winners or response outcomes.</span>
          <span>STOCK CCTV / DRONE VIDEO IS VISUALIZATION ONLY.</span>
        </footer>
      </div>
    </main>
  );
}
