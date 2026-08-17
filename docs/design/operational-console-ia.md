# Operational Console — information architecture

Scope: the `/demo/intrusion` surface. This document defines what the operator
surface shows, where every value comes from, and what it is forbidden to claim.
It does not change backend, allocator, mission logic, PX4 integration, probes or
data semantics.

The surface exists to make one sentence legible without narration:

> **SwarmOS decides. Physical agents execute. Console supervises.**

## 1. Truth inventory — what the Console can actually render

Every field below is a server-issued frame already reaching the Console over
REST boot + WS (`lib/ws.ts`). Nothing else may appear as operational truth.

| Frame | Fields the surface uses | Provenance on the PX4 SITL path |
| --- | --- | --- |
| `unit` (`UnitState`) | `agent_id`, `fsm_state`, `battery_pct`, `geo`, `heading_deg`, `altitude_agl_m`, `link_quality`, `current_mission_id` | real — `GLOBAL_POSITION_INT` / battery / heartbeat sampled at 4 Hz by the MAVLink adapter |
| `anomaly_view` (`AnomalyView`) | `id`, `kind`, `geo`, `confidence`, `detected_at`, `detected_by`, `evidence.headline` | event injected on the bus; geo is the real target coordinate the mission is built from |
| `allocation` (`AllocationDecision`) | `mission_id`, `anomaly_id`, `mode`, `eligible_units[]` + `score` + full `score_breakdown`, `excluded_units[]` + `reason` + `active_mission_id`, `winner_agent_id`, `winner_score`, `ts` | real — computed server-side by the allocator |
| `mission_runtime` (`MissionRuntimeEvent`) | `mission_id`, `agent_id`, `phase`, `evidence`, `error`, `ts` | real — projected from adapter `MissionProgress`; evidence only where the adapter established it |
| `payload` (`PayloadEvent`) | `kind`, `status`, `execution_mode`, `agent_id`, `mission_id`, `ts` | real — `mavlink_output_confirmed` for the light, `simulated` for the speaker |
| `execution_group` (`ExecutionGroup`) | `objective_kind`, `state`, `requested_members`, `members[]` (role, agent, mission, state, score, `replaces_agent_id`) | real — SwarmOS-owned composition (TAKE B) |
| `mission` (`MissionView`) | `track[]`, `waypoints[]` | real — `track` is the observed position history SwarmOS keeps per agent |

### Deliberately not available, therefore never drawn

- No onboard camera stream. The MAVLink path publishes no video.
- No per-mission ETA on the PX4 path.
- No same-aircraft preemption/diversion — not implemented, so no UI for it.
- No fleet-wide "confidence" or health score beyond `awareness`, which this
  surface does not use.

### Simulation boundary

Two things on this surface are simulated and must stay visually separated from
verified evidence:

1. **Speaker payload** — `execution_mode: "simulated"`. Rendered amber, in a
   `SIMULATED` lane, never in the verified-evidence lane.
2. **CCTV imagery** — stock footage. Demoted to a small evidence thumbnail with
   a permanent `SIMULATED IMAGERY · NOT EVIDENCE` stamp. The stock drone POV
   video is removed entirely.

## 2. The reading order the layout must enforce

```
objective → fleet state → SwarmOS decision → mission ownership
          → physical execution → verified evidence → adaptation
```

Adaptation is the second event: `mav-002 EXCLUDED · BUSY` → `mav-001 SELECTED`,
with both missions owned and executing at the same time.

## 3. Layout — 2560 × 1440, no page scroll

Fixed three-band grid. The map is the primary surface; nothing floats over it
except state.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ COMMAND BAR                                                                   h 52   │
│ SWARM · SwarmOS   SITE FRAME   CONNECTED   FLEET 002/002   OBJECTIVES 02   UTC clock │
├────────────────────┬───────────────────────────────────────────┬─────────────────────┤
│ OBJECTIVE QUEUE    │                                           │ DECISION RAIL       │
│ w 380              │        OPERATIONAL MAP                    │ w 520               │
│                    │        (fills remaining width)            │                     │
│ one row per        │                                           │ for the focused     │
│ objective, ordered │  local ENU site frame projected from      │ objective:          │
│ by arrival:        │  real PX4 geo                             │                     │
│  kind, confidence, │                                           │  01 OBJECTIVE       │
│  owner, ladder     │  · frame origin = observed home           │  02 FLEET EVALUATED │
│                    │  · graticule + range rings in metres      │     eligible rows   │
│ ─────────────────  │  · agents: heading glyph + state ring     │     excluded rows   │
│ FLEET              │  · objectives: distinct marker            │  03 SELECTED        │
│                    │  · assignment link agent → objective      │  04 OWNERSHIP       │
│ one row per agent: │  · observed track polyline                │  05 EXECUTION       │
│  state, battery,   │  · scale bar + origin lat/lon             │     state ladder    │
│  mission ownership │                                           │  06 EVIDENCE        │
│                    │                                           │     verified lane   │
│ CCTV evidence      │                                           │     simulated lane  │
│ thumbnail (small,  │                                           │     fleet payload   │
│ labeled simulated) │                                           │  07 EXECUTION GROUP │
│                    │                                           │     (TAKE B, same   │
│                    │                                           │      language)      │
├────────────────────┴───────────────────────────────────────────┴─────────────────────┤
│ MISSION TIMELINE                                                              h 280  │
│ one swimlane per mission, x = wall clock, ticks at observed state transitions        │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

Concurrency is proved by the timeline: two swimlanes overlapping in time, each
labelled with its own owner and mission id.

Three details exist specifically so the surface survives the second objective:

- the decision rail **follows the newest objective automatically** — the
  adaptation beat must not need a click;
- the bounded-response channels are **fleet-wide, not focus-scoped** — the light
  is on because of objective 1 while SwarmOS is allocating objective 2;
- every objective row **keeps its own latest mission proof**, so an earlier
  verified arrival does not leave the screen when focus moves on.

Under step 03 the rail restates the decision in words, built only from fields
the allocator published (`mav-002 excluded · BUSY · already owns mission
4c97f2f2` / `mav-001 selected · highest score of 1 eligible agent`). It says out
loud what the rows above already show; it infers nothing.

Record at 2560 × 1440 with the browser at device pixel ratio 1, so the CSS
viewport is 2560 × 1440. The columns are proportional with pixel minimums, so a
smaller viewport degrades rather than breaks.

## 4. The state ladder

Discrete steps only. No percentage bar — `progress_pct` is not rendered.

| Step | Proven by | Notes |
| --- | --- | --- |
| `ALLOCATED` | `allocation` frame carrying `winner_agent_id` | SwarmOS decided |
| `DISPATCHED` | first `mission_runtime` frame for that `mission_id` | adapter accepted and opened the execution stream |
| `EN ROUTE` | `mission_runtime.phase == "EN_ROUTE"` | |
| `ON STATION` | `mission_runtime.phase == "ON_STATION"` | carries `MISSION_ITEM_REACHED` |
| `RTL` | `mission_runtime.evidence == "mavlink_rtl_command_acknowledged"` | on this path it arrives with `DONE` |
| `DONE` | `mission_runtime.phase == "DONE"` | |

A step that SwarmOS has not published is `PENDING`, never inferred. Steps are
reached only on an observed frame, and each reached step shows the server
timestamp that proves it.

`mission_runtime` is upserted latest-per-mission in both backend state and the
Console store, so the Console additionally keeps a bounded append-only log of
the runtime frames it observed. That log is a buffer of server frames — it
computes nothing.

## 5. Evidence hierarchy

Three visual tiers, unmistakably distinct:

1. **VERIFIED** — signal green, solid rule, filled marker.
   `MISSION_ITEM_REACHED`, `RTL COMMAND ACKNOWLEDGED`, `PX4 OUTPUT CONFIRMED`.
   Each is stamped `PX4 SITL` so the claim boundary is on screen.
2. **REPORTED** — platinum/monochrome. State transitions with no adapter proof.
3. **SIMULATED** — launch amber, hatched rule. Speaker playback, CCTV imagery.

## 6. Visual language

Foundations from the SWARM design system (`lib/tokens.ts`) are kept; the UI
elements are new and operational rather than editorial.

- Surface: absolute black `#030406`; panels obsidian `#0B0E11`; hairlines
  gunmetal `#1A2026`. No shadow other than the 1 px inset highlight.
- 85% monochrome. Accent is state only:
  - orbital blue `#7BE7FF` — SwarmOS decision, selection, focus, link
  - signal green `#B8FF66` — verified execution evidence
  - launch amber `#FFB45C` — exclusion, attention, simulated
- **No red anywhere.**
- Type: IBM Plex Mono for every operational value and label; Space Grotesk for
  eyebrows; Cormorant Garamond reserved for the wordmark and the few editorial
  headings. Tabular numerals for all telemetry.
- Icons: named inline SVG, 24 px, 1.5 px stroke, round caps. No icon kit.
- No gradients, no glow, no rounded SaaS cards, no glassmorphism, no
  decorative motion. Motion is limited to a state-change flash and the existing
  unit sweep.
- Every element on screen must encode state, relation, decision or evidence.

## 7. Voice

Confidence-bound, intent-based. Operator language is `verify sector`,
`hold patrol`, `return Unit 003`. Forbidden: `Intruder`, `Manual`, `fly drone`,
`alarm`, `red-alert`, `red state`.

## 8. Comprehension acceptance test

A viewer who has never seen SWARM must be able to follow TAKE A from the UI
alone:

1. an `INTRUSION` objective arrives with its confidence;
2. SwarmOS evaluates `mav-001` and `mav-002` with visible scores and reasons;
3. `mav-002` is selected and owns the mission;
4. `mav-002` executes and reaches the objective;
5. arrival is proven by `MISSION_ITEM_REACHED`;
6. the physical response is verified — light `PX4 OUTPUT CONFIRMED`, speaker
   explicitly `SIMULATED`;
7. `HEAT_SPOT` arrives while mission 1 is still active;
8. `mav-002` is `EXCLUDED · BUSY` with mission 1's exact active mission id;
9. `mav-001` is selected;
10. both missions are simultaneously owned and executing.

The redesign is incomplete until each of these ten beats is readable without a
voice-over.

These ten beats are executed as a test —
`frontend/components/ops/OperationalConsole.test.tsx` — driving the surface with
the recorded take-1 frames (`frontend/lib/demo-frames.ts`) and asserting each
beat at the point in the take where a viewer would look for it. The recorded
frame script is also what `/dev/replay` plays, so the surface can be reviewed
without a two-instance PX4 SITL bench. That route is 404 in a production build
and every frame it renders is stamped `REPLAY · RECORDED FRAMES · NOT LIVE`.

### Known limitation of the scenario, not of the surface

Event 2 (`HEAT_SPOT`, `47.39775, 8.54559`) sits about a metre from the PX4 SITL
home position, so its owner launches and reaches station almost directly above
its own launch point. The map shows that honestly — the aircraft climbs and
holds — but there is very little lateral movement to watch. If the recorded
scenario is ever revised, placing event 2 tens of metres from home would make
the second mission's execution as visible on the map as the first.
