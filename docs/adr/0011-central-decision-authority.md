# ADR 0011 — Central decision authority and thin physical agents

**Status**: Accepted  
**Date**: 2026-08-15

## Context

SWARM's product thesis depends on many replaceable physical units acting as one
coordinated system. That does **not** require each unit to contain a separate
mission-level decision engine.

Delegating fleet decisions to individual aircraft would create several problems:

- a compromised unit could gain authority beyond its own airframe;
- different vendors could make conflicting mission choices;
- reasoning and audit would be fragmented across devices;
- fleet behavior would be harder to reproduce, explain and supervise;
- cheap, replaceable hardware would need more onboard intelligence than the
  product thesis requires.

The current live runtime already evaluates fleet state and chooses mission
ownership in SwarmOS. This ADR makes that behavior a permanent architecture
invariant.

## Decision

**SwarmOS is the sole mission-level decision authority. Physical agents are
thin executors.**

A physical agent may be a drone, rover, robot or another compatible machine.
It reports observations and executes commands, but it does not decide what the
fleet should do.

### SwarmOS owns

SwarmOS is responsible for decisions such as:

- creating or accepting mission objectives;
- deciding whether an event requires action;
- selecting which agent or agents should respond;
- computing eligibility, exclusions and allocation scores;
- assigning mission ownership and roles;
- selecting mission targets and routes at the coordination layer;
- adding, replacing or removing agents from an active response;
- deciding when to retask, abort, return or rotate an agent;
- deciding which payload action is appropriate and when it should execute;
- composing and dissolving future multi-agent execution groups;
- deciding escalation and other fleet-level follow-up actions.

These decisions must remain auditable in SwarmOS. A Console, adapter or physical
agent must not independently recreate them.

### Physical agents and adapters own

An agent is allowed to perform the minimum local behavior necessary to execute a
SWARM-issued objective safely and report reality back to SwarmOS, including:

- stabilization and attitude control;
- motor/actuator control;
- following an already-issued waypoint or trajectory;
- local obstacle avoidance where the vendor autopilot provides it;
- sensor capture and telemetry production;
- reporting mission progress and execution evidence;
- enforcing geofence and altitude safety constraints;
- immediate low-battery, lost-link or equivalent safety failsafes;
- emergency landing/RTL behavior required to fail safe when central control is
  unavailable.

These are **flight/execution safety decisions**, not mission decisions. They
answer "how do I execute this command safely?" rather than "what should the
fleet do next?".

### Agents must not

An adapter or physical agent must not:

- create or award a fleet mission;
- elect itself or another agent for a mission;
- import or execute the central allocator;
- command or retask peer agents;
- turn a local observation directly into a fleet action;
- form an autonomous sub-swarm with independent mission authority;
- change the mission objective without a SwarmOS command, except for a bounded
  local safety failsafe.

## Data from agents is evidence, not authority

Centralized decision authority limits the blast radius of a compromised agent,
but it does **not** make an aircraft impossible to hack.

A compromised agent may still:

- falsify telemetry;
- falsify or manipulate sensor output;
- ignore a command;
- execute unsafe low-level behavior if its autopilot or command link is
  compromised.

SwarmOS therefore treats agent-originated state as semi-trusted operational
input. Existing rate, range, freshness and policy checks remain required. Future
cross-agent corroboration, attestation or stronger hardware identity may improve
trust, but they must not be claimed until implemented and validated.

The security property provided by this ADR is narrower and concrete:

> Compromising one physical agent does not grant that agent legitimate
> mission-decision authority over the rest of the fleet.

## Multi-agent execution groups

A future `ExecutionGroup` is a **SwarmOS-owned logical object**, not another
brain.

For example, SwarmOS may decide that a mission requires:

- `mav-002` → primary observation;
- `mav-004` → secondary viewpoint;
- `mav-006` → illumination.

The member agents execute their assigned roles. They do not negotiate those
roles among themselves. If one agent degrades or fails, telemetry returns to
SwarmOS and SwarmOS decides whether and how to replace it.

This preserves the economic thesis of many simple, replaceable machines while
allowing collective capability to emerge from central coordination.

## Runtime boundary

The intended control loop is:

```text
physical agents / sensors
        │
        │ observations, telemetry, progress
        ▼
      SwarmOS
  understand + decide
 allocate + coordinate
        │
        │ missions, retasks, payload commands
        ▼
physical agents / autopilots
   execute + fail safe
```

The onboard autopilot remains authoritative over low-level flight safety. SwarmOS
remains authoritative over mission intent and fleet coordination.

## Consequences

- Vendor adapters stay simpler and more replaceable.
- Fleet reasoning remains centralized, observable and auditable.
- A compromised endpoint has a smaller legitimate authority surface.
- Cheap physical agents can rely on commodity autopilots rather than duplicating
  the fleet intelligence stack onboard.
- Multi-agent capability is composed by SwarmOS, not by autonomous peer
  negotiation.
- Central SwarmOS availability, integrity and telemetry trust become critical
  system concerns and must be engineered accordingly.

## Enforcement

- `adapters/base.py` defines adapters as SWARM-issued mission executors.
- Adapter implementations must not import allocator, scheduler, autonomy or
  orchestrator decision modules.
- Architecture tests enforce that dependency boundary.
- Current allocation decisions are computed by the orchestrator from canonical
  fleet state and published as structured truth frames.
- Local autopilot failsafes remain explicitly permitted as the safety exception.
