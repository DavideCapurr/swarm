# SWARM — YC application draft

> **Status:** working draft, updated 2026-08-15.
>
> This document is grounded in the current repo state and the canonical thesis in [`../../swarm-thesis.md`](../../swarm-thesis.md).
>
> **Do not copy stale batch dates from older versions of this file. Confirm the live YC application window before submission.**

## Honesty rule

Every technical claim must preserve the repo's evidence level.

The MAVLink/PX4 path is **PX4 SITL-validated**.

SWARM is **not** yet bench-validated or field-proven on physical aircraft.

The current wildfire / intrusion / search scenarios are simulation fixtures. They are not customer validation and do not establish the first market.

---

## Company

**Company name:** SWARM

### Describe what your company does in 50 characters or less

Preferred:

> `Coordination OS for autonomous drone fleets`

Alternative:

> `Autonomous coordination for drone fleets`

The short answer should describe the product, not an unvalidated vertical.

### Company URL / product link

> Public demo / landing page + GitHub repo once the multi-agent SITL demo is packaged and deployed.

### Demo video

Target: **60–90 seconds**.

The demo should show multiple PX4 SITL vehicles, a neutral physical-world task, autonomous fleet allocation, mission dispatch, a mid-mission change, reallocation/re-tasking, and an auditable explanation of why SWARM made each decision.

The environment must be clearly labeled as **PX4 SITL / simulation**.

The reviewer should understand, without a long explanation:

> The autopilot flies the aircraft. SWARM decides what the fleet should do.

---

## What is your company going to make?

> SWARM is building the coordination layer for autonomous drone fleets.
>
> Individual drone autopilots already know how to fly a mission. The unsolved layer above them is deciding which unit should respond, when it should launch, what objective it should execute, how multiple units should coordinate, when one unit should replace another, how battery and availability affect the mission, and what happens when the situation changes.
>
> SWARM turns a heterogeneous set of autonomous aircraft into one operational system. A task enters the system; SWARM evaluates the fleet, selects the best available unit or units, dispatches missions through vendor adapters, tracks execution, re-tasks when conditions change, and produces an auditable result for the operator.
>
> Today the product runs end-to-end in simulation and the MAVLink/PX4 path is validated against PX4 SITL for connect, telemetry, mission dispatch, and return-to-launch. The next technical proof is a short multi-vehicle SITL demo that makes autonomous allocation and re-tasking visible.
>
> We have deliberately reopened the first commercial wedge instead of forcing the company around an unvalidated wildfire/private-land assumption. We are now interviewing operators of industrial sites, logistics yards, mines, energy infrastructure, ports, inspection workflows, and other large physical environments to find the highest-frequency situation where someone currently has to physically go and check what is happening.
>
> The long-term vision is larger than drone fleet management: SWARM can become a coordination runtime that gives software reliable physical presence through distributed autonomous machines.

---

## Progress

### How far along are you?

> SWARM has an end-to-end coordination stack: domain core, mission model, fleet state machine, auction-based allocator, simulator, orchestrator, backend, real-time telemetry, operator Console, persistence/audit, autonomy/shadow-mode logic, CV-backed scenarios, security controls, and a multi-vendor adapter architecture.
>
> The MAVLink/PX4 adapter has been validated against PX4 SITL. A reproducible probe covers connect, status visibility, telemetry ingest, mission dispatch and RTL.
>
> The strongest missing technical proof is physical-aircraft validation. We are not claiming it yet.
>
> The strongest missing company proof is customer evidence. The previous wildfire/vineyard wedge was based too heavily on thesis rather than real buyer evidence, so we reopened the first market and are doing cross-vertical customer discovery before naming a canonical wedge.

### Are people using your product?

> No production users yet.

### Revenue?

> No revenue yet.

### What have you done that is difficult or impressive?

> I built the coordination system end-to-end before starting university: the mission allocator, autonomy logic, fleet state, simulator, backend, Console, audit/security discipline, and PX4/MAVLink integration. The codebase is designed to keep claims typed: simulated, SITL-validated, bench-validated and field-proven are separate evidence levels. The PX4 path is at SITL today, and I know exactly what remains to make it physical.

Use actual test counts and other engineering metrics only if re-verified immediately before submission.

---

## Idea

### Why this idea?

> Physical systems are still dispatched and coordinated much more manually than software systems. A drone can autonomously fly a route, but operating many distributed drones across changing tasks still requires humans to decide who should go, when, with which capabilities, and what should happen when the situation changes.
>
> My core insight is that the durable product may not be one better airframe. It may be the coordination layer that makes many replaceable autonomous units behave like one system.
>
> A single drone is an asset. A coordinated fleet can become infrastructure.

### How do you know people need it?

**Do not submit the old vineyard/wildfire founder-hunch answer.**

The final answer should be replaced with real discovery evidence.

Before submission, answer with concrete patterns such as:

> We spoke with [N] operators across [verticals]. The repeated workflow was [specific physical verification task]. It happens [frequency], currently takes [time/cost], and [buyer type] owns the budget. [N] said they would evaluate a supervised pilot if we can hit [specific success metric].

If that evidence does not exist yet, say so honestly rather than fabricating certainty.

---

## First wedge

### Current position

The first wedge is **not yet canonically selected**.

Candidate environments for discovery:

- industrial sites and logistics yards;
- mines and quarries;
- energy infrastructure;
- ports and large compounds;
- infrastructure inspection;
- large private/semi-private sites;
- manual drone-service workflows that already suffer from dispatch/coverage constraints.

The wedge should be chosen based on repeated evidence that the workflow is frequent, painful, has a clear budget owner, and benefits from coordinated autonomous mobile units.

Wildfire remains a possible application, not the identity of the company.

---

## Competitors

The final answer should compare SWARM against the categories the selected wedge actually encounters.

At the platform layer, likely categories include:

- single-vendor drone fleet-management products;
- drone-in-a-box systems;
- manual drone-service operators;
- fixed camera/sensor systems;
- robotics orchestration systems;
- internal operator workflows built around one autopilot/vendor.

### What do we understand differently?

> Onboard autonomy and airframes will keep improving and becoming more replaceable. The coordination problem remains: heterogeneous assets, many simultaneous tasks, limited human attention, battery/availability constraints, and changing priorities. SWARM is designed to own that layer rather than one airframe.

Do not claim a moat from vendor neutrality alone. The defensibility must eventually come from deployed workflow integration, coordination reliability, operational data, adapters, safety/evidence tooling, and the ability to manage increasingly complex fleets.

---

## Business model

Do not force a final pricing model until the wedge is selected.

Possible models include:

- annual software license per site / fleet;
- per-site managed deployment;
- software + support / integration;
- usage-based mission or asset coordination;
- later API/runtime pricing for third-party systems that request physical tasks.

The first pricing answer should be tied to the workflow discovered in customer interviews and to a clear existing cost or budget line.

---

## Market size

Do not use “all drones” as the initial TAM.

Once the wedge is selected:

> target sites × realistic annual contract value × realistic initial market

Then explain how the same coordination layer expands to adjacent workflows and industries.

Long-term vision:

> SWARM becomes infrastructure for software-directed physical agency, starting with autonomous drone fleets and potentially expanding to other distributed robotic systems.

---

## Why now?

Potential structural tailwinds to verify and cite before submission:

- rapidly improving and cheaper autonomous drone hardware;
- better onboard autonomy and commodity autopilots;
- increasing drone-in-a-box deployment;
- more AI systems capable of detecting events and generating tasks;
- growing demand for remote inspection and operations;
- increasing need to coordinate heterogeneous fleets rather than one vehicle at a time.

Use current sources in the final application rather than unsupported generalities.

---

## Founder / team

### Founder

> Technical founder who designed and built SWARM's coordination stack end-to-end before starting university.

The application should make the unusual technical slope the center of the founder story.

### Cofounder

Current state: unresolved.

Do not add a placeholder cofounder.

If still solo, say so plainly. Explain that the highest-value complementary profile would likely add robotics/controls, hardware/flight operations, regulation, or industrial customer access.

---

## Founder commitment / university

This answer must match reality.

Possible structure:

> I am starting university, but SWARM is not a class project. I built the current system before university and I am continuing to push the company through customer discovery and technical proof. If the evidence shows this should become my full-time company, I am prepared to make that decision rather than treating school as a reason not to act.

Do not use this wording if it overstates actual willingness.

---

## Regulatory / deployment answer

> We are separating software proof from deployment claims. Today the real-aircraft path is not field-proven. Early physical testing will be supervised and bounded under the applicable operating rules. Broader BVLOS/autonomous operations are a real scaling constraint that must be addressed market by market; we are not assuming regulation away. The coordination layer can still be developed and validated in SITL and supervised operations while the deployment envelope expands.

Verify jurisdiction-specific details before submission.

---

## Demo script — target 60–90 seconds

### 0–10s

> “SWARM coordinates autonomous drone fleets. The autopilot flies each drone. SWARM decides who should go, when, and what happens next.”

Show three PX4 SITL units with clearly different battery/availability states.

### 10–30s

Create:

`VERIFY anomaly at sector C7`

Show the allocator reasoning and autonomous unit selection.

### 30–50s

Show mission dispatch through the PX4/MAVLink path and live fleet state.

### 50–70s

Introduce a second higher-priority event or make the selected unit unavailable / low battery.

Show SWARM reallocate, add a second unit, or command RTL.

### 70–90s

Show the audit/result view.

Close:

> “Everything shown here is PX4 SITL. We have not field-validated the aircraft path yet. Next we are taking this same coordination layer into the first workflow that customer discovery proves is worth deploying.”

That ending is stronger than pretending simulation is hardware.

---

## The bigger picture

> Software can move information instantly, but physical response is still limited by where machines and people happen to be. SWARM's long-term goal is to make physical presence programmable: a software system expresses an objective, and SWARM finds and coordinates the available autonomous agents that can carry it out.
>
> We start with drones because they are increasingly capable, mobile and replaceable. The larger company can become the runtime for autonomous physical infrastructure.

---

## Pre-submit checklist

- [ ] Re-verify all current YC dates and application fields.
- [ ] Record the multi-agent PX4 SITL demo.
- [ ] Deploy a simple public demo/landing link.
- [ ] Complete serious cross-vertical customer discovery.
- [ ] Replace all placeholder demand answers with real evidence.
- [ ] Select a wedge only if evidence supports it.
- [ ] Re-verify test counts and technical metrics.
- [ ] Keep SITL / bench / field claims distinct.
- [ ] Decide the honest founder-commitment answer.
- [ ] Decide solo/cofounder status.
- [ ] Build wedge-specific market sizing only after the buyer/workflow is clear.
