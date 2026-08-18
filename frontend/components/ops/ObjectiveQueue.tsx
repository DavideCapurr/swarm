"use client";

/**
 * ObjectiveQueue — every objective SwarmOS is currently answering, in arrival
 * order, each carrying its reported source, owner and how far its mission has
 * actually got.
 *
 * This is where the second event has to become obvious: a new objective
 * appears while the first is still mid-ladder.
 */

import { clock, type ObjectiveStory } from "@/lib/mission-story";

import { Eyebrow, LadderTick, Panel, Value } from "./primitives";

const MISSION_PROOFS = new Set(["MISSION_ITEM_REACHED", "RTL COMMAND ACKNOWLEDGED"]);

/**
 * The proof to keep on the row. Mission-level evidence wins over payload
 * evidence: at a glance, "it got there" matters more than "the light is on".
 */
function latestVerifiedProof(story: ObjectiveStory): string | null {
  const verified = story.evidence.filter((row) => row.tier === "verified");
  const mission = verified.filter((row) => MISSION_PROOFS.has(row.proof));
  return (mission.at(-1) ?? verified.at(-1))?.proof ?? null;
}

function activityState(story: ObjectiveStory): { label: string; tone: string } {
  if (!story.active) return { label: "CLOSED", tone: "text-ash" };
  if (story.latestStep === "ALLOCATED" && !story.serverPhase) {
    return { label: "OWNED", tone: "text-orbital-blue" };
  }
  return { label: "EXECUTING", tone: "text-signal-green" };
}

export function ObjectiveQueue({
  stories,
  focusMissionId,
  onFocus,
  className = "",
}: {
  stories: ObjectiveStory[];
  focusMissionId: string | null;
  onFocus: (missionId: string) => void;
  className?: string;
}) {
  const active = stories.filter((story) => story.active).length;
  return (
    <Panel
      className={className}
      title="Objectives"
      right={
        <span className="font-mono text-[12px] tracking-[0.16em] text-ash">
          {String(stories.length).padStart(2, "0")} TOTAL · {String(active).padStart(2, "0")} ACTIVE
        </span>
      }
      bodyClassName="overflow-y-auto"
    >
      {stories.length === 0 ? (
        <div className="px-3 py-5">
          <span className="font-mono text-[13px] text-ash">
            NO OBJECTIVE PUBLISHED BY SWARMOS
          </span>
        </div>
      ) : (
        stories.map((story) => {
          const activity = activityState(story);
          return (
            <button
              key={story.missionId}
              type="button"
              onClick={() => onFocus(story.missionId)}
              data-testid={`objective-${story.missionId}`}
              className={`block w-full border-b border-gunmetal px-3 py-3 text-left transition-colors duration-press ease-swarm ${
                story.missionId === focusMissionId
                  ? "border-l-2 border-l-orbital-blue bg-orbital-blue/[0.05]"
                  : "border-l-2 border-l-transparent hover:bg-surface-2"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="flex min-w-0 items-baseline gap-3">
                  {/* The objective label is an identifier, not a state. It used
                      to be amber, which spent the escalation colour on every
                      row and left real attention with nothing to say. */}
                  <span className="shrink-0 font-mono text-[13px] tracking-[0.16em] text-muted-silver">
                    {story.label}
                  </span>
                  <Value size="md" className="truncate">
                    {story.missionKind} {story.kind}
                  </Value>
                </span>
                <Value size="sm" tone="ash">
                  {clock(story.detectedAt ?? story.decisionTs)}
                </Value>
              </div>

              <div className="mt-[6px] flex items-baseline justify-between gap-3">
                <span className="font-mono text-[13px] tracking-[0.1em] text-ash">
                  confidence{" "}
                  <span className="text-muted-silver">
                    {story.confidence != null ? `${(story.confidence * 100).toFixed(0)}%` : "—"}
                  </span>
                </span>
                <span className="font-mono text-[13px] tracking-[0.1em] text-ash">
                  owner{" "}
                  <span className="text-platinum">{story.owner ?? "unassigned"}</span>
                </span>
              </div>

              {/* Sensor id and objective label are both data. Neither is a
                  state, so neither takes an accent. */}
              <div className="mt-[5px] flex items-baseline justify-between gap-3 font-mono text-[12px] uppercase tracking-[0.1em]">
                <span className="min-w-0 truncate text-ash">
                  reported input{" "}
                  <span className="text-muted-silver">
                    {story.detectedBy ?? "swarm anomaly bus"}
                  </span>
                </span>
                <span className="shrink-0 text-ash">→ {story.label}</span>
              </div>

              <div className="mt-[10px] flex items-center gap-[3px]">
                {story.ladder.map((slot, index) => (
                  <span key={slot.step} className="flex flex-1 items-center gap-[3px]">
                    <LadderTick
                      source={slot.source}
                      tone={slot.proof && slot.source === "observed" ? "green" : "orbital"}
                    />
                    {index < story.ladder.length - 1 ? (
                      <span
                        className={`h-px flex-1 ${
                          story.ladder[index + 1].source === "pending"
                            ? "bg-graphite"
                            : "bg-orbital-blue/60"
                        }`}
                      />
                    ) : null}
                  </span>
                ))}
              </div>
              <div className="mt-[6px] flex items-baseline justify-between">
                <span className="font-mono text-[15px] uppercase tracking-[0.14em] text-platinum">
                  {story.latestStep ?? "AWAITING RUNTIME"}
                </span>
                <span className={`font-mono text-[15px] uppercase tracking-[0.14em] ${activity.tone}`}>
                  {activity.label}
                </span>
              </div>

              {/* The rail follows the newest objective, so each row keeps its own
                  latest proof: an earlier mission's verified arrival must not
                  leave the screen when a second objective arrives. */}
              {latestVerifiedProof(story) ? (
                <div className="mt-[8px] flex items-baseline gap-2 border-l-2 border-signal-green bg-signal-green/[0.025] py-[3px] pl-2">
                  <span className="font-mono text-[14px] font-medium uppercase tracking-[0.08em] text-signal-green">
                    {latestVerifiedProof(story)}
                  </span>
                  <span className="font-mono text-[12px] tracking-[0.08em] text-ash">PX4 SITL</span>
                </div>
              ) : null}
            </button>
          );
        })
      )}
    </Panel>
  );
}

/**
 * A small, permanently labelled scene reference for the first reported input.
 *
 * The bundled clip is simulated and is never operational evidence or a live
 * camera. The source name and objective labels below come from the server story;
 * the imagery remains only visual context for that reported input.
 */
export function ImageryAside({ src, story }: { src: string; story: ObjectiveStory | null }) {
  const source = story?.detectedBy ?? "sensor input";
  const intent = story ? `${story.missionKind} ${story.kind}` : "AWAITING INPUT";
  const confidence =
    story?.confidence != null ? `${(story.confidence * 100).toFixed(0)}%` : "—";

  return (
    <section className="shrink-0 border border-gunmetal bg-surface-1">
      <header className="flex h-[30px] items-center justify-between border-b border-gunmetal bg-surface-2 px-3">
        <Eyebrow>sensor input context</Eyebrow>
        <span className="font-mono text-[12px] tracking-[0.16em] text-ash">
          SIMULATED IMAGERY
        </span>
      </header>
      {/* The caption used to be absolutely positioned over a 116px clip, so its
          third line landed on top of the bottom stamps. Caption and stamps now
          sit in normal flow above and below the imagery: nothing overlaps, and
          the honesty stamp can never be covered by scene content. */}
      {story ? (
        <div className="border-b border-gunmetal px-2 py-1 font-mono text-[11px] uppercase leading-[1.3] tracking-[0.08em]">
          <div className="truncate text-ash">REPORTED SOURCE · {source}</div>
          <div className="truncate text-platinum">{intent} · {confidence}</div>
          <div className="truncate text-muted-silver">REPORTED INPUT → {story.label}</div>
        </div>
      ) : null}
      <div className="relative h-[76px] w-full overflow-hidden bg-surface-1">
        {story ? (
          <video
            aria-label="Simulated scene reference for reported sensor input"
            className="h-full w-full object-cover opacity-55"
            src={src}
            autoPlay
            muted
            loop
            playsInline
          />
        ) : null}
      </div>
      {/* The one place amber is spent on this panel: the claim boundary that
          keeps simulated imagery from ever reading as operational evidence. */}
      <div className="flex items-center justify-between gap-2 border-t border-gunmetal px-2 py-[3px] font-mono text-[11px] tracking-[0.06em]">
        <span className="whitespace-nowrap font-medium text-launch-amber">
          SIMULATED IMAGERY · NOT EVIDENCE
        </span>
        <span className="shrink-0 whitespace-nowrap text-ash">NOT A LIVE FEED</span>
      </div>
    </section>
  );
}
