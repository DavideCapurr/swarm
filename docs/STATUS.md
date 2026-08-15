# SwarmOS — execution status

Live, slim status. Read this first for the current execution state.

The canonical company thesis is [`../swarm-thesis.md`](../swarm-thesis.md). When this status document or an older product/roadmap document conflicts with the thesis, the thesis wins.

Full historical phase notes live in [`STATUS-archive.md`](STATUS-archive.md).

## Current strategic state — 2026-08-15

SWARM has moved past the point where more speculative software breadth is the highest-leverage work.

The coordination stack is substantial, and the real PX4 path now has a **live two-vehicle SITL proof through the actual backend orchestrator**. Two independent PX4 v1.14 instances become one SWARM fleet, one anomaly is auctioned, one vehicle is selected, the winning PX4 reaches the final waypoint, and SWARM then commands RTL.

The next two proofs are therefore narrower:

1. **make changing-condition coordination obvious on screen** by extending the proven multi-PX4 runtime with a second event/state change and recording the Console decision/re-task flow;
2. **market proof** through customer discovery across operators of large physical sites, without assuming wildfire or any other vertical is the answer.

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
| Waypoint-completion semantics | **final MISSION_ITEM_REACHED required; timeout fails closed to RTL + FAILED** |
| YC-grade multi-agent demo | **partial: real allocation/dispatch/arrival/RTL proven; dynamic re-task + Console cut pending** |
| First wedge | **open; customer discovery required** |
| Customer evidence | **insufficient / next market priority** |
| Physical bench / field proof | **not yet done** |
| Pilot / revenue | **none yet** |

## Evidence already available

The original MAVLink/PX4 path has a reproducible single-vehicle SITL proof covering connect, status visibility, telemetry ingest, mission dispatch and return-to-launch. See [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md).

The backend-owned fleet path now also has a reproducible **two-PX4 live SITL proof**. See [`bench/phase9-multi-sitl-validation.md`](bench/phase9-multi-sitl-validation.md) and [`bench/artifacts/phase9-multi-sitl-backend-probe.json`](bench/artifacts/phase9-multi-sitl-backend-probe.json).

That live gate also exposed and fixed two mission-semantics bugs that fake/single-path tests had not made obvious:

- `MISSION_CURRENT` was incorrectly usable as waypoint-completion evidence for a one-item mission;
- the implicit mission deadline ignored current-aircraft → first-waypoint travel and climb.

The backend fleet runtime now requires final `MISSION_ITEM_REACHED` before `ON_STATION`, and deadline expiry produces RTL + `FAILED`, never a false `DONE`.

The repository also contains end-to-end simulation scenarios for wildfire, intrusion and search. These remain useful technical fixtures and regression proofs. They must not be interpreted as validated markets.

## Immediate queue

### 1. Finish the YC-grade multi-agent SITL demo on the proven runtime

Do not build another parallel demo system. Use the backend path already validated with two live PX4 SITL vehicles.

The remaining demo sequence is:

- start several PX4 SITL units with visibly different state;
- neutral event enters SWARM;
- SWARM ranks the real fleet state and selects one unit automatically;
- the winning PX4 receives the mission and reaches the target;
- while that mission is active, introduce a second higher-priority event or availability/battery change;
- show SWARM re-task, replace, add or return a unit using behavior that is genuinely implemented;
- expose the fleet-level decision/reason in the Console;
- show terminal result and audit trail;
- keep SITL labeling explicit.

The first half is no longer hypothetical: two live PX4 instances, fleet readiness, auction, mission dispatch, final waypoint reach and RTL are already proven through the real backend.

### 2. Compose bounded payload presence-response onto the real runtime

PR #122 is useful only if it stops being a separate proof path. After the multi-PX4 runtime lands, rebase/compose its bounded payload action onto the same mission lifecycle:

`event → fleet auction → winning PX4 → verified ON_STATION → payload action → RTL`

Do not let payload simulation become a substitute for the more important coordination demo. The value is that physical action becomes one optional capability of the same vendor-neutral fleet runtime.

### 3. Run cross-vertical customer discovery

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

### 4. Convert one strong problem signal into a pilot hypothesis

Only after repeated evidence appears should SWARM name a first wedge.

A useful signal is not “cool idea.” A useful signal is repeated evidence that a workflow is frequent, costly or slow, has a clear budget owner, and can credibly be improved by autonomous mobile verification/response.

### 5. Physical proof after the demo/customer signal

SWARM does not need to buy drones merely to create the software demo.

The next large technical evidence jump after the SITL demo is the same coordination path on physical aircraft through the lowest-friction credible route: borrowed hardware, a university/maker/robotics partner, a drone operator, or purchased hardware if justified.

## What is explicitly on hold

Unless a customer, physical-proof or demo blocker requires it, defer:

- more speculative ML;
- federation breadth;
- multi-site abstractions;
- additional compliance documentation;
- extra dashboard polish unrelated to the demo decision flow;
- unsupported vendor breadth;
- platform features that do not improve the multi-agent demo, customer discovery, physical proof, or pilot path.

The repo already has enough engineering depth to demonstrate founder capability. The next marginal unit of progress should create external evidence.

## YC posture

The strongest technical sentence is now:

> SWARM already runs one fleet-level auction across multiple live PX4 SITL vehicles through the real backend, dispatches the winning autopilot, waits for actual waypoint-reached proof, and commands return. We are now making dynamic re-tasking obvious in the Console and finding the first workflow worth deploying into.

Do not present an unvalidated vertical as certainty.

Do not describe SITL as physical aircraft proof.

Do lead with the technical slope, the bugs live evidence exposed, the fact that they were fixed fail-closed, and the clarity of what remains unproven.

## Canonical references

- Company thesis: [`../swarm-thesis.md`](../swarm-thesis.md)
- README: [`../README.md`](../README.md)
- Single-PX4 SITL evidence: [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md)
- Multi-PX4 backend SITL evidence: [`bench/phase9-multi-sitl-validation.md`](bench/phase9-multi-sitl-validation.md)
- Multi-PX4 probe artifact: [`bench/artifacts/phase9-multi-sitl-backend-probe.json`](bench/artifacts/phase9-multi-sitl-backend-probe.json)
- YC readiness: [`yc/readiness-and-gaps.md`](yc/readiness-and-gaps.md)
- YC application draft: [`yc/application-draft.md`](yc/application-draft.md)
- Customer discovery kit: [`yc/customer-discovery-kit.md`](yc/customer-discovery-kit.md)
- Evidence-to-scale roadmap: [`plan/swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md)
