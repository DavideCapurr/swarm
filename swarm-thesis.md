# SWARM Startup Thesis

## One-line definition

SWARM is the coordination layer for autonomous physical response.

Today, the agents are drones. SWARM turns many distributed autonomous units into one coordinated system that can decide who should respond, when, where, and what happens next.

**Many units. One intention.**

---

## The company objective

Software can react instantly. Physical response still cannot.

When something important happens in the physical world, useful action is delayed by distance, fragmented information, limited human attention, dispatch latency, battery constraints, and uncertainty about what is actually happening.

SWARM exists to reduce that dead time.

The long-term objective is to create an autonomous physical-response layer: distributed agents, docking or charging infrastructure, sensors, and coordination software that can bring fast presence, visibility, verification, and eventually task execution to real-world events.

SWARM is not fundamentally a wildfire company, a security company, an inspection company, or a drone manufacturer.

Those are possible applications.

The core product is coordination.

---

## The core insight

The winning system is not necessarily one better drone.

The winning system can be the software that makes many replaceable units act like one operational network.

Individual autopilots already know how to stabilize, follow waypoints, avoid obstacles, return home, and execute a mission. SWARM operates one layer above them.

The autopilot flies **how**.

SWARM decides:

- which unit should respond;
- when it should launch;
- where it should go;
- which payload or sensor is needed;
- how multiple units should coordinate;
- when a unit should be re-tasked;
- when another unit should replace it;
- how battery rotation and availability affect the mission;
- what evidence should be collected;
- when to escalate to a human;
- what happens next.

This is the coordination layer.

---

## Why fleets matter

A single drone is an asset.

A coordinated fleet can become infrastructure.

Many lower-cost or replaceable units can create capabilities that one expensive unit cannot provide alone:

- wider geographic coverage;
- multiple viewpoints;
- redundancy;
- faster response from the nearest available unit;
- battery rotation;
- graceful degradation when a unit fails;
- parallel missions;
- lower vendor dependence;
- easier replacement and scaling.

The economic thesis is not that cheap hardware is always better. It is that coordination can make ordinary, heterogeneous hardware substantially more useful as a system.

SWARM should therefore remain vendor-neutral wherever practical and avoid making proprietary airframes a prerequisite for the software thesis.

---

## The universal loop

Across use cases, SWARM is designed around the same loop:

1. **Receive a cue**  
   A request or signal arrives from an operator, software system, sensor, camera, previous patrol, external feed, or another agent.

2. **Understand the task**  
   SWARM evaluates urgency, geography, confidence, required capabilities, operational constraints, and available assets.

3. **Allocate the best unit or units**  
   The system considers distance, battery, payload, current mission, availability, geofence, and mission priority.

4. **Dispatch and coordinate**  
   One or more agents receive missions through the appropriate vendor adapter.

5. **Adapt**  
   If conditions change, SWARM can re-task, replace, add, abort, or return units while preserving the mission objective.

6. **Observe and verify**  
   Agents produce telemetry, imagery, video, sensor readings, and geospatial context.

7. **Create an auditable result**  
   SWARM records what happened, which units were used, why decisions were made, and what evidence was produced.

8. **Escalate or conclude**  
   A human or an approved downstream system decides the next operational step where supervision is required.

This loop is the product primitive.

---

## What SWARM is today

SWARM currently exists as software, not as a deployed physical network.

The repository contains an end-to-end coordination system with:

- a domain core and mission model;
- fleet state and finite-state logic;
- auction-based mission allocation;
- multi-vendor adapter architecture;
- a MAVLink/PX4 adapter;
- simulator-driven multi-agent scenarios;
- an orchestrator;
- backend and real-time telemetry paths;
- an operator Console;
- autonomy and shadow-mode decision logic;
- evidence and audit primitives;
- security and operational controls.

The MAVLink/PX4 path has been validated against PX4 SITL. It has **not** yet been validated on physical aircraft in bench or field operation.

That distinction must remain explicit in every external claim.

---

## The next proof: coordination without buying drones

The next investor-readable proof does not require SWARM to purchase a fleet.

The immediate technical demo should use multiple PX4 SITL vehicles and make the coordination layer, not the visual simulation, the main event.

A strong demo should show:

1. several autonomous vehicles available at different locations and states;
2. a neutral real-world task entering the system, for example `VERIFY anomaly at sector C7`;
3. SWARM evaluating distance, battery, availability, capability, and constraints;
4. autonomous selection of the best unit;
5. real mission dispatch through the MAVLink/PX4 path;
6. a second event or changing condition while the first mission is active;
7. reallocation, replacement, escalation, or RTL without the operator manually choosing the aircraft;
8. an auditable explanation of why the system made each decision;
9. mission completion and fleet recovery.

The demo must be labeled honestly as simulation/SITL. It should never imply physical flight when none occurred.

The objective is to make a reviewer understand one thing immediately:

**the vehicles fly themselves; SWARM decides what the fleet should do.**

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

and let SWARM determine which available physical agents should perform it.

At sufficient scale, the network could include:

- aerial drones;
- docking and charging nodes;
- mobile sensors;
- ground robots;
- specialized inspection platforms;
- other autonomous machines exposed through compatible coordination interfaces.

The end-state is not “more drones.”

It is a runtime for autonomous physical infrastructure: a distributed system that turns software intent into coordinated action in the real world.

---

## Expansion logic

SWARM should expand in this order:

1. **Prove coordination in simulation/SITL.**
2. **Find a painful, frequent first workflow through customer discovery.**
3. **Demonstrate the same coordination path on physical hardware, owned or borrowed.**
4. **Run a supervised pilot in a bounded environment.**
5. **Prove repeatable customer value.**
6. **Add multi-site, multi-vendor, and higher-autonomy capabilities only when demanded by real deployments.**
7. **Expand into adjacent markets that reuse the same coordination primitive.**

More software is not automatically more progress. From the current state, field evidence and customer evidence are higher-value than adding speculative platform breadth.

---

## YC framing

For an accelerator or early investor, SWARM should be presented narrowly first and broadly second.

**What works today**

> SWARM coordinates autonomous drone fleets. We have an end-to-end multi-agent system and a PX4 SITL-validated MAVLink path that allocates missions based on fleet state and can adapt while missions are running.

**What we are proving next**

> We are building a short multi-drone SITL demo that makes autonomous allocation and re-tasking visible, while interviewing operators of large physical sites to identify the first high-frequency workflow worth deploying into.

**What it can become**

> SWARM can become the coordination runtime that gives software autonomous presence in the physical world.

The application must not pretend that the first market is already known if it is not. The strongest story is a technically capable founder who has built the coordination core, knows exactly what is still unproven, and is moving aggressively toward customer and physical evidence.

---

## Permanent truth rules

Every SWARM document, demo, application, and external claim must preserve these distinctions:

- **simulated** is not **SITL-validated**;
- **SITL-validated** is not **bench-validated**;
- **bench-validated** is not **field-proven**;
- **customer interview** is not **pilot commitment**;
- **pilot interest** is not **revenue**;
- a **possible vertical** is not a **validated wedge**.

When documents conflict, this thesis is the strategic source of truth.

---

**Many units. One intention.**
