# SWARM Startup Thesis

## One-line definition

SWARM is the coordination layer for autonomous physical response.

Today, the physical agents are drones. SWARM turns many distributed, replaceable units into one coordinated system that can decide who should respond, when, where, how many units are needed, what role each should perform, and what happens next.

**Many units. One intention.**

---

## The company objective

Software can react instantly. Physical response still cannot.

When something important happens in the physical world, useful action is delayed by distance, fragmented information, limited human attention, dispatch latency, battery constraints, and uncertainty about what is actually happening.

SWARM exists to reduce that dead time.

The long-term objective is to create an autonomous physical-response layer: distributed physical agents, docking or charging infrastructure, sensors, and coordination software that can bring fast presence, visibility, verification, and eventually task execution to real-world events.

SWARM is not fundamentally a wildfire company, a security company, an inspection company, or a drone manufacturer.

Those are possible applications.

The core product is coordination.

---

## The core insight

The winning system is not necessarily one better drone.

The winning system can be the software that makes many simple, replaceable units act like one operational network.

Individual autopilots already know how to stabilize, follow waypoints, avoid obstacles, return home, and enforce immediate flight-safety constraints. SWARM operates one layer above them.

The autopilot decides **how to execute safely**.

SWARM decides:

- which unit or units should respond;
- when they should launch;
- where they should go;
- which payload or sensor is needed;
- what role each participating unit should perform;
- how multiple units should be coordinated;
- when a unit should be re-tasked;
- when another unit should replace it;
- when capacity should be split across simultaneous events;
- how battery rotation and availability affect the mission;
- what evidence should be collected;
- when to escalate to a human;
- what happens next.

This is the coordination layer.

### Decision authority is centralized

**SwarmOS is the sole mission-level decision authority.**

A drone is a physical execution endpoint and evidence source. It reports telemetry, sensor observations, health and execution progress to SWARM, then executes the mission or retask SWARM issues.

A physical agent does not legitimately:

- select its own fleet mission;
- decide that a local observation should become a fleet action;
- elect or command another drone;
- allocate itself or peers;
- form an independently deciding sub-swarm;
- change the fleet objective without a SWARM decision.

The onboard autopilot still retains bounded local behavior necessary to keep the aircraft flying safely, including stabilization, actuator control, waypoint following, obstacle avoidance where available, geofence enforcement, low-battery RTL, lost-link behavior, and emergency landing/return behavior.

The distinction is deliberate:

> **SWARM decides what / who / where / when / why / what next. The autopilot executes safely and fails safe locally.**

This limits the legitimate authority of each cheap endpoint and keeps fleet reasoning observable and auditable in one place. It does **not** make a drone impossible to compromise: a compromised endpoint may still falsify telemetry or sensor data, ignore commands, or be manipulated through its flight controller or command link. Agent-originated data is therefore evidence, not authority.

---

## Why fleets matter

A single drone is an asset.

A coordinated fleet can become infrastructure.

Many lower-cost or replaceable units can create capabilities that one expensive unit cannot provide alone:

- wider geographic coverage;
- multiple simultaneous viewpoints;
- redundancy;
- faster response from the nearest available unit;
- battery rotation;
- graceful degradation when a unit fails;
- parallel missions;
- temporary concentration of several units on one important event;
- lower vendor dependence;
- easier replacement and scaling.

The economic thesis is not that cheap hardware is always better. It is that coordination can make ordinary, heterogeneous hardware substantially more useful as a system.

SWARM should therefore remain vendor-neutral wherever practical and avoid making proprietary airframes a prerequisite for the software thesis.

### Collective capability without local swarm brains

When one mission needs several physical agents, SWARM composes them centrally into a temporary **ExecutionGroup**.

For example:

```text
MISSION: investigate anomaly

SWARM forms execution group EG-42
  mav-002 → primary observation
  mav-004 → secondary viewpoint
  mav-006 → illumination
```

The execution group is a SwarmOS-owned logical object, not another autonomous decision authority. The drones do not negotiate roles among themselves. If a member degrades or fails, its telemetry/progress returns to SWARM and SWARM decides whether to replace, remove, rotate, or retask it.

That model is implemented today. The current PX4 SITL proof validates one logical objective decomposed into three role-specific child missions across three of four available agents, plus central replacement of an active failed member with the unused spare.

This is the intended meaning of “the union makes the strength”: intelligence belongs to the coordinated system, while individual physical units can remain comparatively simple and replaceable.

---

## The universal loop

Across use cases, SWARM is designed around the same loop:

1. **Receive a cue**  
   A request or signal arrives from an operator, software system, sensor, camera, previous patrol, external feed, or physical agent.

2. **Understand the task**  
   SWARM evaluates urgency, geography, confidence, required capabilities, operational constraints, and available capacity.

3. **Allocate the best unit or units**  
   SWARM considers distance, battery, payload, current mission, availability, geofence, mission priority, and any required redundancy or complementary roles.

4. **Dispatch and coordinate**  
   One or more physical agents receive SWARM-issued missions through the appropriate vendor adapters.

5. **Adapt centrally**  
   If conditions change, SWARM can re-task, replace, add, rotate, abort, or return units while preserving the mission objective.

6. **Observe and verify**  
   Agents produce telemetry, imagery, video, sensor readings, execution evidence, and geospatial context back to SWARM.

7. **Create an auditable result**  
   SWARM records what happened, which units were used, why decisions were made, and what evidence was produced.

8. **Escalate or conclude**  
   SWARM concludes the mission or an approved human/downstream system takes the next operational step where supervision is required.

This loop is the product primitive.

---

## What SWARM is today

SWARM currently exists as software, not as a deployed physical network.

The repository contains an end-to-end coordination system with:

- a domain core and mission model;
- fleet state and finite-state logic;
- centralized fleet-state mission allocation;
- multi-vendor adapter architecture;
- a MAVLink/PX4 adapter;
- simulator-driven multi-agent scenarios;
- an orchestrator;
- backend and real-time telemetry paths;
- an operator Console;
- autonomy and shadow-mode decision logic;
- structured allocation, runtime, execution-group and payload evidence;
- security and operational controls.

The live allocation path computes eligibility, exclusions, scores and ownership centrally in SwarmOS before dispatching physical agents. Physical adapters execute selected child work and report reality back.

The current runtime supports both simultaneous independent missions and first-class, SwarmOS-owned **ExecutionGroups** for one logical objective executed by multiple physical agents. SwarmOS forms the group, selects distinct members, assigns roles, creates per-agent child missions, aggregates completion, and centrally replaces a failed member without granting peer authority to the aircraft.

This multi-agent path has been validated live against four independent PX4 SITL instances through the real MAVLink backend runtime: one `COOPERATIVE_VERIFY` objective was decomposed into `PRIMARY_OBSERVER`, `SECONDARY_OBSERVER`, and `OVERWATCH` child missions executed by three distinct PX4 agents while a fourth remained spare. Every selected child produced `ON_STATION` only after `MISSION_ITEM_REACHED` evidence and `DONE` with acknowledged RTL. The parent objective itself was never dispatched to a physical adapter.

Live replacement has also been validated. The selected `SECONDARY_OBSERVER`, `mav-003`, was SIGKILLed while `EN_ROUTE`; SwarmOS observed explicit runtime failure, selected spare `mav-001` for the same role, dispatched a fresh child mission with replacement provenance, observed `MISSION_ITEM_REACHED`, received RTL acknowledgement, and completed the aggregate `ExecutionGroup`.

The final `/demo/intrusion` recording path has passed three consecutive clean authenticated rehearsals at approximately 62 seconds each, including a second event while mission 1 remained active, exact `BUSY` exclusion with the active mission id, a different second owner, simultaneous missions, payload cleanup, and acknowledged RTL.

The MAVLink/PX4 path remains SITL validation, not physical-aircraft bench or field proof.

That distinction must remain explicit in every external claim.

---

## The current proof: coordination without buying drones

The investor-readable coordination proof does not require SWARM to purchase a fleet. The multi-PX4 SITL path demonstrates dynamic reallocation across simultaneous events, one logical objective composed across multiple role-specific physical executors, and live centrally controlled replacement after an active executor disappears.

The definitive recording surface is `/demo/intrusion`, using the runbook in [`docs/bench/final-demo-rehearsal.md`](docs/bench/final-demo-rehearsal.md). The demo should make the coordination layer, not the simulated imagery, the main event.

The validated demo flow shows:

1. PX4 SITL vehicles available to SwarmOS;
2. an event entering the system;
3. SwarmOS evaluating eligibility, availability and score;
4. central selection and mission dispatch;
5. verified `ON_STATION` only after `MISSION_ITEM_REACHED`;
6. a bounded payload response with confirmed PX4 SITL light output and explicitly simulated speaker;
7. a second event while the first mission remains active;
8. the first owner excluded as `BUSY` with its exact active mission id;
9. a different second owner selected and both missions active concurrently;
10. cleanup and acknowledged RTL.

Separate bench evidence demonstrates the four-PX4 `ExecutionGroup` and live member replacement paths.

The demo must be labeled honestly as simulation/SITL. It should never imply physical flight when none occurred.

The objective is to make a reviewer understand one thing immediately:

**the autopilot flies the aircraft; SWARM decides what the fleet should do.**

---

## The first market is not yet decided

SWARM should not lock itself into wildfire, private estates, industrial security, inspection, or another vertical before evidence supports that choice.

The first wedge is now an explicit **customer-discovery question**, not a canonical product decision.

The correct first market should have most of these properties:

- a geographically bounded operating environment;
- frequent situations where someone must physically go and inspect or verify something;
- measurable cost or delay in the current workflow;
- enough operational frequency to demonstrate value quickly;
- a buyer with a clear budget owner;
- a credible path to supervised drone operations;
- repeatability across many sites;
- a reason why coordination of multiple mobile units is better than one manually operated drone.

Priority environments to investigate include:

- industrial sites and logistics yards;
- mines and quarries;
- energy infrastructure;
- ports and large compounds;
- large private or semi-private sites;
- infrastructure inspection and anomaly verification.

Wildfire remains a possible application, but it is **not** the default wedge or the identity of the company.

The founder should discover the wedge by asking operators where physical verification is slow, repetitive, expensive, dangerous, or poorly covered today.

---

## Customer-discovery question

The most useful opening question is not:

> Would you buy autonomous drone swarms?

It is:

> **What situations on your site currently require a person to physically go and check what is happening?**

Follow-up discovery should quantify:

- how often this happens;
- how long verification takes;
- who performs it;
- what it costs;
- what happens when verification is late;
- what tools are used today;
- whether a drone is already part of the workflow;
- who owns the budget;
- what regulatory or safety constraints matter;
- whether multiple simultaneous events or large-area coverage create a coordination problem.

The initial wedge should be earned from this evidence.

---

## What SWARM is not

SWARM is not:

- a consumer drone app;
- a proprietary-airframe thesis;
- a fixed-camera network;
- a dashboard that merely shows drone positions;
- a replacement for the onboard autopilot;
- a peer-to-peer swarm in which each aircraft independently decides fleet objectives;
- a claim that simulation equals field validation;
- a company whose identity depends on one unvalidated vertical;
- an autonomous weapons system.

SWARM may support dual-use, defense, emergency, industrial, infrastructure, conservation, and other applications over time, but expansion must follow product evidence, regulation, safety, and customer demand.

---

## Long-term vision

The long-term opportunity is larger than fleet management.

SWARM aims to give software a reliable way to request and coordinate **physical presence on demand**.

A future software system or AI agent should be able to express an objective such as:

`inspect(location, objective)`

or

`respond(event, constraints)`

and let SWARM determine which available physical agents, or which temporary combination of them, should perform it.

At sufficient scale, the network could include:

- aerial drones;
- docking and charging nodes;
- mobile sensors;
- ground robots;
- specialized inspection platforms;
- other autonomous machines exposed through compatible execution interfaces.

The end-state is not “more drones.”

It is a runtime for autonomous physical infrastructure: a distributed physical system with centralized mission intelligence that turns software intent into coordinated action in the real world.

---

## Expansion logic

SWARM should expand in this order:

1. **Prove coordination in simulation/SITL.**
2. **Find a painful, frequent first workflow through customer discovery.**
3. **Demonstrate the same coordination path on physical hardware, owned or borrowed.**
4. **Run a supervised pilot in a bounded environment.**
5. **Prove repeatable customer value.**
6. **Add multi-site, multi-vendor, and higher central coordination capabilities only when demanded by real deployments.**
7. **Expand into adjacent markets that reuse the same coordination primitive.**

The current software/SITL coordination milestone in step 1 includes dynamic multi-event allocation, first-class `ExecutionGroup` composition, live member replacement, and a deterministic final demo rehearsal. The next technical evidence gap is the physical-hardware bridge, not another speculative coordination feature.

More software is not automatically more progress. From the current state, field evidence and customer evidence are higher-value than adding speculative platform breadth.

---

## YC framing

For an accelerator or early investor, SWARM should be presented narrowly first and broadly second.

**What works today**

> SWARM is a real-time orchestration layer for physical agents. SwarmOS is the sole mission-level decision authority. The current PX4 SITL path validates dynamic allocation across active missions, first-class multi-agent `ExecutionGroup` composition across four PX4 instances, and central replacement of an active failed member with a spare.

**What we are proving next**

> The technical coordination demo is feature-frozen and rehearsed. The next engineering evidence gap is bridging the same control path to supervised physical hardware, while the first commercial workflow remains a customer-evidence question.

**What it can become**

> SWARM can become the coordination runtime that gives software autonomous presence in the physical world by composing many replaceable physical agents into one adaptive system.

The application must not pretend that the first market is already known if it is not. The strongest story is a technically capable founder who has built the coordination core, knows exactly what is still unproven, and is moving aggressively toward customer and physical evidence.

---

## Permanent truth rules

Every SWARM document, demo, application, and external claim must preserve these distinctions:

- **simulated** is not **SITL-validated**;
- **SITL-validated** is not **bench-validated**;
- **bench-validated** is not **field-proven**;
- **customer interview** is not **pilot commitment**;
- **pilot interest** is not **revenue**;
- a **possible vertical** is not a **validated wedge**;
- multiple physical agents in a fleet are not automatically one `ExecutionGroup`; group claims require explicit SwarmOS-owned composition evidence;
- **central decision authority** does not mean **a physical endpoint cannot be compromised**.

When documents conflict, this thesis is the strategic source of truth. Technical implementation/proof claims must be grounded in `docs/STATUS.md`, the accepted ADRs, and the corresponding `docs/bench/` evidence.

---

**Many units. One intention.**
