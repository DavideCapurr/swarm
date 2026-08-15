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

The live runtime evaluates fleet state and chooses mission ownership in SwarmOS.
This ADR makes that behavior a permanent architecture invariant and defines how
multi-agent execution composes capability without introducing subordinate
mission-level brains.

## Decision

**SwarmOS is the sole mission-level decision authority. Physical agents are
thin executors.**

A physical agent may be a drone, rover, robot or another compatible machine. It
reports observations and executes commands, but it does not decide what the
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
- composing and dissolving multi-agent execution groups;
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

`ExecutionGroup` is a **SwarmOS-owned logical coordination object**, not another
brain.

A group records:

- one parent mission objective;
- the required member count;
- each role assigned by SwarmOS;
- the selected physical agent for each role;
- the child mission sent to that agent;
- the centrally computed allocation score and breakdown;
- member lifecycle state;
- replacement provenance when a member fails;
- the aggregate group lifecycle.

The parent `COOPERATIVE_VERIFY` objective is deliberately not an executable
adapter mission kind. SwarmOS must decompose it into child `VERIFY` missions
before dispatch. Physical adapters fail closed if an orchestration-only parent
is sent to them directly. `COVER` follows the same rule and is decomposed into
per-agent `PATROL` slices.

For a three-agent cooperative verification, SwarmOS can compose:

```text
ExecutionGroup
├── PRIMARY_OBSERVER   -> mav-002 -> child VERIFY
├── SECONDARY_OBSERVER -> mav-004 -> child VERIFY
└── OVERWATCH          -> mav-006 -> child VERIFY
```

The member agents execute only their own child task. They do not discover,
negotiate, elect or command the other members.

### Formation is fail-closed

SwarmOS plans the full required group before dispatching any child mission. If
there are not enough eligible agents, the group is marked `FAILED` with
`INSUFFICIENT_ELIGIBLE_CAPACITY` and zero partial child missions are launched.

Agents already busy, carrying a current mission, below the battery threshold or
otherwise unavailable are not eligible. A physical agent can occupy only one
role in the same group.

### Replacement remains central

If a member publishes `FAILED`, or its executor crashes and terminates without a
successful terminal result, SwarmOS marks that role degraded and centrally
selects a spare. The failed member is retained in group history as `REPLACED`;
the replacement records `replaces_agent_id` and receives a fresh child mission.

No failed member elects its replacement and no peer takes over by itself.
Replacement attempts are bounded per role and fail closed when no eligible spare
exists.

### Payload authority remains role-scoped in SwarmOS

For cooperative intrusion verification, only `PRIMARY_OBSERVER` is authorized by
the central presence-response policy to execute the bounded light/speaker
response. Secondary observers and overwatch remain observation roles. This is a
SwarmOS policy decision, not an agent-side capability choice.

## Runtime boundary

The control loop is:

```text
physical agents / sensors
        │
        │ observations, telemetry, progress
        ▼
      SwarmOS
  understand + decide
 allocate + coordinate
 compose ExecutionGroup
        │
        │ child missions, retasks, payload commands
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
- A group can degrade and be repaired by a centrally selected spare without
  changing the parent objective.
- Central SwarmOS availability, integrity and telemetry trust become critical
  system concerns and must be engineered accordingly.

## Enforcement

- `adapters/base.py` defines adapters as SWARM-issued mission executors.
- Adapter implementations must not import allocator, scheduler, autonomy or
  orchestrator decision modules.
- Architecture tests enforce that dependency boundary.
- Physical adapters reject orchestration-only parent objectives.
- Current single-agent allocation decisions are computed by the orchestrator
  from canonical fleet state and published as structured truth frames.
- Execution-group composition and lifecycle are published as structured
  `swarm:execution-groups` truth frames and projected to REST/WebSocket clients
  without frontend recomputation.
- Local autopilot failsafes remain explicitly permitted as the safety exception.

## Validation boundary

Unit/integration tests must prove group formation, deterministic unique role
assignment, fail-closed insufficient capacity, central replacement, executor
exception handling and role-scoped payload authority. Hardware/SITL claims must
be documented separately and only after the corresponding run is observed; this
ADR does not convert untested physical behavior into a claim.
