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
                  : "border-l-2 border-l-transparent hover:bg-obsidian"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="flex items-baseline gap-3">
                  <span className="font-mono text-[13px] tracking-[0.16em] text-launch-amber">
                    {story.label}
                  </span>
                  <Value size="md">{story.missionKind} {story.kind}</Value>
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
                  <span className="text-orbital-blue">{story.owner ?? "unassigned"}</span>
                </span>
              </div>

              <div className="mt-[5px] flex items-baseline justify-between gap-3 font-mono text-[11px] uppercase tracking-[0.12em]">
                <span className="text-ash">
                  reported input{" "}
                  <span className="text-launch-amber">
                    {story.detectedBy ?? "swarm anomaly bus"}
                  </span>
                </span>
                <span className="text-muted-silver">→ {story.label}</span>
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
                <div className="mt-[8px] flex items-baseline gap-2 border-l-2 border-signal-green pl-2">
                  <span className="font-mono text-[12px] uppercase tracking-[0.1em] text-signal-green">
                    {latestVerifiedProof(story)}
                  </span>
                  <span className="font-mono text-[11px] tracking-[0.1em] text-ash">PX4 SITL</span>
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
    <section className="border border-gunmetal bg-absolute-black">
      <header className="flex h-[30px] items-center justify-between border-b border-gunmetal bg-obsidian px-3">
        <Eyebrow>sensor input context</Eyebrow>
        <span className="font-mono text-[12px] tracking-[0.16em] text-launch-amber">
          SIMULATED IMAGERY
        </span>
      </header>
      <div className="relative h-[116px] w-full overflow-hidden bg-obsidian">
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

        {story ? (
          <div className="absolute left-2 top-2 bg-absolute-black/85 px-2 py-1 font-mono text-[11px] uppercase tracking-[0.12em]">
            <div className="text-launch-amber">REPORTED SOURCE · {source}</div>
            <div className="mt-[2px] text-platinum">{intent} · {confidence}</div>
            <div className="mt-[2px] text-orbital-blue">REPORTED INPUT → {story.label}</div>
          </div>
        ) : null}

        <div className="absolute inset-x-0 bottom-0 flex items-end justify-between px-2 pb-2">
          <span className="bg-absolute-black/85 px-[6px] py-[3px] font-mono text-[10px] tracking-[0.12em] text-launch-amber">
            SIMULATED IMAGERY · NOT EVIDENCE
          </span>
          <span className="bg-absolute-black/85 px-[6px] py-[3px] font-mono text-[10px] tracking-[0.12em] text-ash">
            NOT A LIVE FEED
          </span>
        </div>
      </div>
    </section>
  );
}