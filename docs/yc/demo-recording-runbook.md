# SWARM — YC demo video recording runbook

> Updated 2026-08-15.
>
> Purpose: make the coordination layer understandable in under two minutes without implying physical-aircraft proof.
>
> This runbook supersedes the old wildfire-specific YC cut. Existing wildfire/intrusion/search demos remain useful technical fixtures, but the YC-facing demo should be neutral and coordination-first.

## Core message

The reviewer must understand this immediately:

> **The autopilot flies each aircraft. SWARM decides what the fleet should do.**

Everything in the demo should support that sentence.

## Evidence rule

The demo uses **PX4 SITL / simulation**.

Do not present simulated or stock footage as physical flight.

Do not imply that the system has been bench- or field-validated if it has not.

The strength of the demo is the real coordination path, not visual realism.

---

## Target duration

**60–90 seconds**.

Longer is acceptable only if every extra second demonstrates a distinct coordination capability.

Avoid product-tour narration, roadmap language, internal phase numbers, and long founder explanations.

---

## Demo scenario

Use a neutral synthetic large-site environment.

Example task:

`VERIFY anomaly at sector C7`

Start with at least three PX4 SITL vehicles in different states.

Example:

| Unit | Position | Battery | State | Capability |
|---|---|---:|---|---|
| Unit 01 | nearest | 22% | available | RGB |
| Unit 02 | medium | 87% | available | RGB + thermal |
| Unit 03 | farthest | 74% | busy | RGB |

SWARM should choose based on the actual allocator/mission logic rather than a scripted UI-only decision.

---

## Required beats

### Beat 1 — fleet state

Show multiple units and their different operational states.

Narration:

> “These are separate PX4 simulated aircraft. Each autopilot knows how to fly. SWARM is the layer above them that decides what the fleet should do.”

### Beat 2 — task enters

Create a neutral verification request.

Narration:

> “A task arrives at sector C7. SWARM evaluates the available fleet instead of asking an operator to choose an aircraft.”

### Beat 3 — autonomous allocation

Show the selected unit and the important reasons.

Narration:

> “It compares distance, battery, availability, mission priority and required capability, then selects the best unit.”

The UI should expose enough reasoning to prove the choice is not arbitrary.

### Beat 4 — PX4 mission dispatch

Show mission transition / telemetry that demonstrates the selected SITL vehicle has received the task through the MAVLink/PX4 path.

Narration:

> “The mission is dispatched through the same MAVLink/PX4 integration already validated in SITL.”

### Beat 5 — the situation changes

This is the most important beat.

While the first task is active, introduce one of:

- a second higher-priority event;
- a battery/availability change;
- a unit becoming unavailable;
- a requirement for a second viewpoint/capability.

Narration:

> “Now the world changes while the first mission is still running. SWARM recomputes the fleet plan.”

### Beat 6 — re-task / replace / add / return

Show SWARM changing the plan without the operator picking the aircraft.

Narration:

> “It reassigns the work, adds or replaces a unit, and returns an aircraft when continuing no longer makes sense.”

Use whichever behavior is genuinely implemented and reliable. Do not narrate capabilities the demo does not actually execute.

### Beat 7 — audit/result

Show the final mission result and decision history.

Narration:

> “Every fleet-level decision is recorded, so the operator can see what happened and why.”

### Beat 8 — honest close

Narration:

> “Everything shown here is PX4 SITL, not physical flight. The next company proof is taking the same coordination layer into the first real workflow that customer discovery proves is worth deploying.”

---

## Suggested full narration

> “These are separate PX4 simulated aircraft. Each autopilot knows how to fly. SWARM is the layer above them that decides what the fleet should do. A verification task arrives at sector C7. SWARM compares the fleet — distance, battery, availability, capability and mission priority — and selects the best unit automatically. The mission is dispatched through our MAVLink/PX4 integration. Now a higher-priority task appears while the first mission is still active. SWARM recomputes the plan and reallocates the fleet instead of asking an operator to choose aircraft one by one. Every decision is recorded so the operator can see what happened and why. Everything shown here is PX4 SITL, not physical flight. Next we are taking this coordination layer into the first workflow that customer discovery proves is worth deploying.”

Trim or modify this only to match what the final demo visibly proves.

---

## Recording checklist

Before recording:

- [ ] multi-vehicle PX4 SITL scenario runs reliably end-to-end;
- [ ] no manual UI-only aircraft selection is required for the core allocation beat;
- [ ] the selected-unit reasoning is visible;
- [ ] the second event/state change reliably produces a coordination response;
- [ ] the PX4/SITL label is visible;
- [ ] no screen implies real flight footage;
- [ ] no stale wildfire/vineyard positioning appears in the YC-facing cut;
- [ ] test run completes without dead time that would make the video feel staged or broken.

During recording:

- record only the relevant Console / telemetry view;
- keep cursor movement minimal;
- avoid scrolling through documentation;
- avoid explaining internal architecture before showing behavior;
- let the autonomous decision happen visibly;
- keep narration matter-of-fact.

After recording:

- trim setup/dead air;
- verify every spoken claim against what is actually shown;
- confirm SITL is clearly identified;
- confirm no claim implies bench/field proof;
- export H.264, 1080p, under two minutes.

Suggested output:

`docs/yc/videos/swarm-multi-agent-sitl-demo.mov`

---

## What not to optimize for

Do not spend the next development cycle making the environment cinematic.

Do not buy drones purely for the video.

Do not add a new vendor integration solely for breadth.

Do not add unrelated dashboard polish.

Do not turn the demo into a generic “three dots moving on a map” animation.

The differentiator to expose is **fleet-level decision-making under changing conditions**.

---

## Separate founder video

The founder video should remain separate from the product demo.

Use the current founder/company story from [`application-draft.md`](application-draft.md), updated with real customer evidence before submission.

The founder video should emphasize:

- built the coordination stack before university;
- knows exactly what is proven and what is not;
- is now moving from software proof to market and physical proof;
- is not hiding behind a broad vision instead of doing the next concrete step.
