# SWARM — Vision

> Strategic expansion of the canonical thesis in [`../swarm-thesis.md`](../swarm-thesis.md).
>
> This file is **not** a second source of truth. If it conflicts with `swarm-thesis.md`, the thesis wins.

## What SWARM is

SWARM is the coordination layer for autonomous physical response.

Today the agents are drones. The product sits above individual autopilots and decides which unit should respond, when, where, with what objective, how many agents are required, which role each receives, and what should happen as conditions change.

The drones are replaceable. The coordination system is the durable product thesis.

**Many units. One intention.**

## The immediate company state

The engineering system exists end-to-end in simulation and has a MAVLink/PX4 path validated against PX4 SITL.

The current SITL evidence includes dynamic allocation across simultaneous missions, first-class SwarmOS-owned multi-agent `ExecutionGroup` composition across four PX4 instances, live central replacement after an active PX4 executor is killed, and three consecutive deterministic final-demo rehearsal passes.

SWARM does not yet have physical-aircraft proof, a validated first market, a pilot, or revenue.

Those missing proofs matter more now than adding speculative platform breadth.

## The first wedge

The first commercial wedge is **not yet selected**.

Earlier versions of the project assumed private high-value land and wildfire-risk patrol would be the beachhead. That remains a possible application, but the company no longer treats it as a canonical decision without buyer evidence.

The wedge will be chosen through workflow-first customer discovery across environments such as:

- industrial sites and logistics yards;
- mines and quarries;
- energy infrastructure;
- ports and large compounds;
- infrastructure inspection;
- large private/semi-private sites;
- existing manual drone-service workflows.

The key question is:

> What situations currently require a person to physically go and check what is happening?

The best initial market should combine high frequency, real cost or urgency, a clear budget owner, feasible early operations, repeatability, and a meaningful advantage from coordinated mobile units.

## Current technical proof

The investor-facing technical proof is now feature-frozen for the demo.

The definitive `/demo/intrusion` path shows SwarmOS:

- evaluate eligible and excluded physical agents centrally;
- publish server-side scores and ownership;
- dispatch through the MAVLink/PX4 path;
- accept `ON_STATION` only after `MISSION_ITEM_REACHED`;
- execute a bounded payload response with confirmed PX4 SITL light output and explicitly simulated speaker;
- handle a second event while the first mission remains active;
- exclude the first owner as `BUSY` with its exact active mission id;
- select a different second owner;
- keep two missions active concurrently;
- clean up and return through acknowledged RTL.

Separate four-PX4 bench evidence proves one logical `COOPERATIVE_VERIFY` objective composed into three role-specific child missions, with one spare. A live failover proof kills one selected PX4 while `EN_ROUTE`; SwarmOS detects failure and centrally assigns the spare to the same role before the group completes.

The final recording runbook is [`bench/final-demo-rehearsal.md`](bench/final-demo-rehearsal.md). All of these claims remain explicitly SITL-scoped.

The next technical evidence gap is supervised physical hardware, not another demo feature.

## The coordination thesis

A single autonomous vehicle can execute a mission.

A fleet creates a harder problem:

- different positions;
- different batteries;
- different payloads;
- different vendors;
- multiple simultaneous objectives;
- changing priorities;
- failures and lost availability;
- limited human attention;
- the need to preserve coverage while tasks are active.

SWARM exists to resolve that layer.

The core loop is:

**cue → understand → allocate → compose → dispatch → adapt → verify → record → conclude/escalate**

That loop should remain portable across markets.

## Long-term vision

The long-term opportunity is not simply fleet-management software.

SWARM aims to make **physical presence programmable**.

A future software system or AI agent should be able to request an objective such as:

`inspect(location, objective)`

or

`respond(event, constraints)`

and allow SWARM to determine which available physical agents, or temporary combination of them, should carry it out.

At scale, that network could include:

- aerial drones;
- docking and charging nodes;
- mobile sensors;
- ground robots;
- specialized inspection platforms;
- other autonomous machines exposed through compatible coordination interfaces.

The end-state is a runtime for autonomous physical infrastructure: software intent translated into coordinated action in the real world.

## Why distributed fleets can matter

The system thesis is that coordination can create capabilities greater than a single premium asset:

- wider coverage;
- faster response from the nearest available unit;
- parallel tasks;
- multiple viewpoints;
- redundancy;
- battery rotation;
- graceful failure;
- lower dependence on one vendor;
- easier replacement and scaling.

This does not mean cheap hardware always wins. It means the value can shift from the sophistication of one machine to the orchestration of many capable machines.

## Platform expansion

The platform must be earned in sequence:

1. prove coordination in simulation/SITL;
2. discover one painful recurring workflow;
3. bridge the same control path to physical hardware;
4. run a supervised pilot;
5. prove repeatable customer value;
6. expand across sites, vendors and adjacent workflows;
7. generalize toward a broader physical-agent runtime.

The software/SITL coordination proof in step 1 is now materially complete for the current demo scope. Do not reopen it merely for presentation breadth.

## Potential application families

These are **possibilities**, not current market claims:

### Industrial / infrastructure

- anomaly verification;
- inspection;
- site awareness;
- post-incident checks;
- large-area operations.

### Energy

- solar / generation inspection;
- remote asset verification;
- event-driven checks.

### Logistics / ports

- yard visibility;
- perimeter or operational verification;
- simultaneous wide-area tasks.

### Emergency / resilience

- disaster mapping;
- wildfire detection/verification;
- search support;
- post-storm assessment.

### Conservation

- reserve patrol;
- anti-poaching observation;
- environmental monitoring.

### Defense / government

Potential later use is limited to lawful non-weapon coordination roles such as ISR, perimeter awareness, force protection, and other supervised sensing/verification workflows.

SWARM is not an autonomous weapons thesis.

## Permanent boundaries

- Never describe simulation as field evidence.
- Never describe SITL as physical-aircraft proof.
- Never call a possible market a validated wedge without customer evidence.
- Do not let a demo scenario become company identity by accident.
- Do not claim vendor neutrality is a moat by itself.
- Do not treat regulation or safety as details that can be ignored later.
- Do not build autonomous weapons or lethal targeting functionality.

## The company in three layers

### Today

> A real-time orchestration layer for physical agents, with centralized mission authority and a PX4 SITL-validated multi-agent execution path.

### First business

> A specific high-frequency physical-verification/response workflow selected from real customer evidence.

### End-state

> The runtime that lets software coordinate physical agents and create autonomous presence in the real world.

---

**Many units. One intention.**
