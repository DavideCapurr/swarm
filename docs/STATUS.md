# SwarmOS — execution status

Live, slim status. Read this first for the current execution state.

The canonical company thesis is [`../swarm-thesis.md`](../swarm-thesis.md). When this status document or an older product/roadmap document conflicts with the thesis, the thesis wins.

Full historical phase notes live in [`STATUS-archive.md`](STATUS-archive.md).

## Current strategic state — 2026-08-15

SWARM has moved past the point where more speculative software breadth is the highest-leverage work.

The coordination stack is already substantial. The next two proofs are:

1. **technical proof that makes multi-agent coordination obvious** through a short, honest PX4 SITL demo;
2. **market proof** through customer discovery across operators of large physical sites, without assuming wildfire or any other vertical is the answer.

Wildfire-risk patrol is no longer the canonical first wedge. It remains one possible application and one useful simulation scenario.

The first commercial wedge is now explicitly **TBD by evidence**.

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
| MAVLink/PX4 adapter | **PX4 SITL-validated; no physical aircraft proof yet** |
| Multi-vehicle investor demo | **next technical priority** |
| First wedge | **open; customer discovery required** |
| Customer evidence | **insufficient / next market priority** |
| Physical bench / field proof | **not yet done** |
| Pilot / revenue | **none yet** |

## Evidence already available

The MAVLink/PX4 path has a reproducible SITL proof covering connect, status visibility, telemetry ingest, mission dispatch and return-to-launch. See [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md).

The repository also contains end-to-end simulation scenarios for wildfire, intrusion and search. These are useful technical fixtures and regression proofs. They must not be interpreted as validated markets.

## Immediate queue

### 1. Build the YC-grade multi-agent SITL demo

The demo should use several PX4 SITL vehicles with different locations, battery states and availability.

Target sequence:

- neutral event enters SWARM, e.g. `VERIFY anomaly at sector C7`;
- SWARM ranks available units;
- one unit is selected automatically;
- mission is dispatched through the PX4/MAVLink path;
- a second event or state change occurs;
- SWARM re-tasks, replaces, adds or returns a unit;
- Console shows the reason for the decision;
- mission completes and fleet state recovers.

The demo must be visibly labeled as SITL/simulation. No stock or simulated footage may be presented as physical flight evidence.

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

### 4. Physical proof later, without requiring owned hardware now

SWARM does not need to buy drones merely to create the next demo.

After SITL + customer signal, the same MAVLink path should be tested on physical aircraft through the lowest-friction credible route: borrowed hardware, a university/maker/robotics partner, a drone operator, or purchased hardware if that becomes justified.

## What is explicitly on hold

Unless a customer or demo blocker requires it, defer:

- more speculative ML;
- federation breadth;
- multi-site abstractions;
- additional compliance documentation;
- extra dashboard polish;
- unsupported vendor breadth;
- platform features that do not improve the SITL demo, customer discovery, physical proof, or pilot path.

The repo already has enough engineering depth to demonstrate founder capability. The next marginal unit of progress should create external evidence.

## YC posture

The strongest YC story is now:

> We built the coordination core first. It already runs end-to-end and the PX4 path is SITL-validated. We are now making multi-agent allocation/re-tasking visible in a short demo and talking to operators of large physical sites to discover the first high-frequency workflow worth deploying into.

Do not present an unvalidated vertical as certainty.

Do not claim hardware proof that does not exist.

Do lead with the technical slope, the clarity of what remains unproven, and the speed at which those gaps are being closed.

## Canonical references

- Company thesis: [`../swarm-thesis.md`](../swarm-thesis.md)
- README: [`../README.md`](../README.md)
- PX4/SITL evidence: [`bench/phase9-sitl-validation.md`](bench/phase9-sitl-validation.md)
- YC readiness: [`yc/readiness-and-gaps.md`](yc/readiness-and-gaps.md)
- YC application draft: [`yc/application-draft.md`](yc/application-draft.md)
- Customer discovery kit: [`yc/customer-discovery-kit.md`](yc/customer-discovery-kit.md)
- Evidence-to-scale roadmap: [`plan/swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md)
