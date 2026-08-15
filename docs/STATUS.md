# SwarmOS — execution status

Live, slim status. Read this first for the current execution state.

The canonical company thesis is [`../swarm-thesis.md`](../swarm-thesis.md). When this status document or an older product/roadmap document conflicts with the thesis, the thesis wins.

Full historical phase notes live in [`STATUS-archive.md`](STATUS-archive.md).

## Current strategic state — 2026-08-15

SWARM has moved past the point where more speculative software breadth is the highest-leverage work.

The real PX4 path now has three successive live proofs through the actual backend orchestrator:

1. **multi-vehicle execution:** two independent PX4 v1.14 instances become one SWARM fleet, one anomaly is auctioned, the winning PX4 reaches the final waypoint, and SWARM commands RTL;
2. **changing-condition coordination:** while the first PX4 is still `EN_ROUTE`, a second event triggers another fleet auction and SWARM allocates the second response to the other available PX4. Both missions then complete independently;
3. **bounded physical-output response:** after the winning PX4 reaches the verified `ON_STATION` gate, SWARM drives a configured PX4 offboard actuator output, confirms the output state from PX4 telemetry, runs bounded cleanup, then allows the mission lifecycle to continue to RTL/DONE.

The remaining technical demo gap is therefore mostly **observability**, not another coordination or payload engine: expose the fleet-level decision and exclusion reason in the Console so a viewer can see why each unit was selected and what happened after arrival.

The parallel company gap remains **market proof** through customer discovery across operators of large physical sites, without assuming wildfire or any other vertical is the answer.

Wildfire-risk patrol is no longer the canonical first wedge. It remains one possible application and one useful simulation scenario.

The first commercial wedge is explicitly **TBD by evidence**.

## Current state

| Area | State |
|---|---|
| Core domain / mission model / FSM | **done** |
| Auction-based allocator | **done** |
| Simulated adapter and scenarios | **done** |
| Console + backend + telemetry | **done** |
| Persistence / audit / security baseline | **done** |
| Autonomy + shadow-mode baseline | **done** |
| CV-backed simulation scenarios | **done** |
| MAVLink/PX4 adapter | **live PX4 SITL-validated; no physical aircraft proof yet** |
| Multi-vehicle PX4 backend orchestration | **live 2-vehicle SITL-validated** |
| Dynamic multi-event fleet reallocation | **live 2-vehicle SITL-validated** |
| Waypoint-completion semantics | **final MISSION_ITEM_REACHED required; timeout fails closed to RTL + FAILED** |
| Bounded payload presence response | **live PX4 SITL output-confirmed; speaker remains explicit simulation; no physical payload proof** |
| YC-grade multi-agent demo | **backend behavior proven; structured Console decision/explanation pending** |
| Same-aircraft preemption/diversion | **not implemented / not claimed** |
| First wedge | **open; customer discovery required** |
| Customer evidence | **insufficient / next market priority** |
| Physical bench / field proof | **not yet done** |
| Pilot / revenue | **none yet** |

## Evidence already available

The original MAVLink/PX4 path has a reproducible single-vehicle SITL proof covering connect, status visibility, telemetry ingest, mission dispatch and return-to-launch. See [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md).

The backend-owned fleet path has a reproducible **two-PX4 live SITL proof**. See [`bench/phase9-multi-sitl-validation.md`](bench/phase9-multi-sitl-validation.md) and [`bench/artifacts/phase9-multi-sitl-backend-probe.json`](bench/artifacts/phase9-multi-sitl-backend-probe.json).

The changing-condition path has a reproducible **two-event / two-PX4 overlap proof**. See [`bench/phase10-dynamic-multi-event-validation.md`](bench/phase10-dynamic-multi-event-validation.md) and [`bench/artifacts/phase10-dynamic-multi-event-probe.json`](bench/artifacts/phase10-dynamic-multi-event-probe.json).

In that dynamic live run:

- event A was awarded to `mav-002`;
- SWARM waited until `mav-002` was visibly `EN_ROUTE` in canonical fleet state;
- event B arrived while mission A was still active;
- event B was awarded to `mav-001` essentially immediately;
- mission A stayed active for another **28.178 s** after event B;
- mission B stayed active for **33.783 s** after event B;
- both missions completed `EN_ROUTE → ON_STATION → DONE`;
- both PX4 logs independently show arm, takeoff, mission finish, RTL and landing.

This is concurrent fleet reallocation, not serialized execution and not same-aircraft preemption.

The bounded payload path now also has a reproducible **two-PX4 live SITL proof on the same backend-owned lifecycle**. See [`bench/payload-presence-sitl-validation.md`](bench/payload-presence-sitl-validation.md) and [`bench/artifacts/payload-presence-sitl-backend-probe.json`](bench/artifacts/payload-presence-sitl-backend-probe.json).

In that live payload run:

- both PX4 instances had unused MAIN5 mapped to `Offboard Actuator Set 1` before the backend started;
- one `INTRUSION` anomaly at confidence `0.95` was auctioned normally;
- `mav-002` won the mission;
- mission progress was `EN_ROUTE → ON_STATION → DONE`;
- `ON_STATION` still required the final `MISSION_ITEM_REACHED`;
- light ON was reported only after PX4 output channel 5 was observed in the requested high state;
- the restricted-area speaker message was explicitly labeled `SIMULATED PAYLOAD`;
- cleanup stopped the message and confirmed the PX4 output low state;
- `DONE` arrived only after that cleanup sequence;
- the external probe passed in **36.912 s**.

This is flight-controller command-to-output proof in SITL, not proof of a physical lamp, driver, cable or speaker.

The Phase 9 live gate also exposed and fixed two mission-semantics bugs that fake/single-path tests had not made obvious:

- `MISSION_CURRENT` was incorrectly usable as waypoint-completion evidence for a one-item mission;
- the implicit mission deadline ignored current-aircraft → first-waypoint travel and climb.

The backend fleet runtime now requires final `MISSION_ITEM_REACHED` before `ON_STATION`, and deadline expiry produces RTL + `FAILED`, never a false `DONE`.

The repository also contains end-to-end simulation scenarios for wildfire, intrusion and search. These remain useful technical fixtures and regression proofs. They must not be interpreted as validated markets.

## Immediate queue

### 1. Make the validated fleet decision obvious in the Console

Do not build another parallel demo system. Use the backend behavior already validated by the multi-PX4, dynamic-reallocation and payload-output gates.

The remaining demo work is:

- publish a structured allocation-decision frame alongside each fleet award;
- include which units were eligible;
- include which units were excluded and why, especially `EN_ROUTE` / busy;
- include the winner and score;
- project that decision into the existing Console mission/event feed;
- make concurrent mission ownership accurate for more than one VERIFY at a time;
- show both active mission rows while event B is allocated;
- surface payload events without obscuring their evidence label;
- keep SITL labeling explicit.

The intended viewer-visible sequence is now factual, not aspirational:

`event A → mav-002 selected → mav-002 EN_ROUTE → event B → mav-002 excluded busy → mav-001 selected → both missions active → verified arrival → optional bounded payload response → RTL`

### 2. Run cross-vertical customer discovery

Do not pitch “wildfire drones” or “industrial security drones” as if the answer is known.

Interview operators who manage large physical environments and start with the workflow question:

> What situations on your site currently require a person to physically go and check what is happening?

Prioritize:

- industrial sites and logistics yards;
- mines and quarries;
- energy infrastructure;
- ports and large compounds;
- infrastructure inspection operators;
- large private/semi-private environments.

Record frequency, verification time, current workflow, cost, budget owner, urgency, drone usage today, regulation, and whether multiple concurrent events or wide-area coverage create a coordination problem.

### 3. Convert one strong problem signal into a pilot hypothesis

Only after repeated evidence appears should SWARM name a first wedge.

A useful signal is not “cool idea.” A useful signal is repeated evidence that a workflow is frequent, costly or slow, has a clear budget owner, and can credibly be improved by autonomous mobile verification/response.

### 4. Physical proof after the demo/customer signal

SWARM does not need to buy drones merely to create the software demo.

The next large technical evidence jump after the SITL demo is the same coordination and bounded-output path on physical aircraft through the lowest-friction credible route: borrowed hardware, a university/maker/robotics partner, a drone operator, or purchased hardware if justified.

For payload evidence, use a real mapped output and a simple visible load before adding more payload abstractions. The point is to prove that the same runtime crosses the simulator/hardware boundary, not to build a large payload framework first.

## What is explicitly on hold

Unless a customer, physical-proof or demo blocker requires it, defer:

- more speculative ML;
- federation breadth;
- multi-site abstractions;
- additional compliance documentation;
- extra dashboard polish unrelated to the allocation/mission decision flow;
- unsupported vendor breadth;
- additional payload abstraction not required by a real hardware or customer workflow;
- platform features that do not improve the multi-agent demo, customer discovery, physical proof, or pilot path.

The repo already has enough engineering depth to demonstrate founder capability. The next marginal unit of progress should create external evidence.

## YC posture

The strongest technical sentence is now:

> SWARM already coordinates multiple live PX4 SITL vehicles through the real backend. While one vehicle is actively responding, a second event triggers another fleet auction and SWARM dispatches the other available vehicle; after verified arrival the same runtime can execute a bounded PX4 output action, confirm that output state, clean up, and only then continue to return. We are now exposing the decision logic cleanly in the Console and finding the first workflow worth deploying into.

Do not call the dynamic proof same-aircraft preemption or diversion.

Do not present an unvalidated vertical as certainty.

Do not describe SITL or flight-controller output confirmation as physical aircraft/payload proof.

Do lead with the technical slope, the live overlap evidence, the reach-aware/fail-closed mission semantics, the bounded output proof, and the clarity of what remains unproven.

## Canonical references

- Company thesis: [`../swarm-thesis.md`](../swarm-thesis.md)
- README: [`../README.md`](../README.md)
- Single-PX4 SITL evidence: [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md)
- Multi-PX4 backend SITL evidence: [`bench/phase9-multi-sitl-validation.md`](bench/phase9-multi-sitl-validation.md)
- Multi-PX4 probe artifact: [`bench/artifacts/phase9-multi-sitl-backend-probe.json`](bench/artifacts/phase9-multi-sitl-backend-probe.json)
- Dynamic multi-event SITL evidence: [`bench/phase10-dynamic-multi-event-validation.md`](bench/phase10-dynamic-multi-event-validation.md)
- Dynamic multi-event probe artifact: [`bench/artifacts/phase10-dynamic-multi-event-probe.json`](bench/artifacts/phase10-dynamic-multi-event-probe.json)
- Payload presence-response SITL evidence: [`bench/payload-presence-sitl-validation.md`](bench/payload-presence-sitl-validation.md)
- Payload presence-response probe artifact: [`bench/artifacts/payload-presence-sitl-backend-probe.json`](bench/artifacts/payload-presence-sitl-backend-probe.json)
- YC readiness: [`yc/readiness-and-gaps.md`](yc/readiness-and-gaps.md)
- YC application draft: [`yc/application-draft.md`](yc/application-draft.md)
- Customer discovery kit: [`yc/customer-discovery-kit.md`](yc/customer-discovery-kit.md)
- Evidence-to-scale roadmap: [`plan/swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md)
