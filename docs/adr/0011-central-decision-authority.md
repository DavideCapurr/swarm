# ADR 0011 — Hierarchical mission authority and thin physical agents

**Status**: Accepted  
**Date**: 2026-08-15  
**Amended**: 2026-08-26

## Context

SWARM's product thesis depends on many replaceable physical units acting as one
coordinated system. That does **not** require each unit to contain a separate
mission-level decision engine, nor does it require every adaptation to round-trip
through a central coordinator.

The useful boundary is the information and authority required by a decision.
Some changes can be handled safely with local information while preserving an
already-authorized objective. Other changes require knowledge of broader mission
priorities, shared capacity, capability trade-offs or objective-level constraints.
Those decisions belong at the SwarmOS layer.

The current runtime evaluates fleet state and chooses mission ownership in
SwarmOS. This ADR preserves that validated behavior while defining a less
absolute long-term boundary: mission-wide authority remains centralized, while
bounded local adaptation may exist below it when it cannot change mission intent
or consume shared mission authority.

## Decision

**SwarmOS owns authoritative mission-level decisions that require mission-wide
context, cross-agent or cross-capability trade-offs, objective changes, or
allocation of shared physical capacity. Physical agents execute assigned work
and may perform bounded local adaptation that preserves that authority boundary.**

A physical agent may be a drone, rover, robot or another compatible machine. It
reports observations and executes commands. Local behavior is legitimate only
when it stays inside an already-authorized objective and cannot independently
change which mission the fleet should pursue or how shared capacity is allocated.

### SwarmOS owns

SwarmOS is responsible for decisions such as:

- creating or accepting mission objectives;
- deciding whether an event requires action;
- selecting which agent or agents should respond when shared capacity is involved;
- computing eligibility, exclusions and allocation scores;
- assigning mission ownership and mission-level roles;
- resolving conflicts between objectives, priorities or scarce capabilities;
- deciding when a capability should be moved from one objective to another;
- changing mission targets or routes at the coordination layer when that changes
  mission intent or shared allocation;
- adding, replacing or removing agents when doing so requires fleet-wide state or
  a capability trade-off;
- deciding when to retask, abort, return or rotate an agent for mission reasons;
- deciding which mission-level payload response is appropriate and when;
- composing and dissolving multi-agent execution groups when composition consumes
  shared capacity;
- deciding escalation and other fleet-level follow-up actions.

These decisions must remain auditable in SwarmOS. A Console, adapter or physical
agent must not independently recreate them.

### Physical agents, local groups and adapters may own

An executor may perform the minimum local behavior necessary to execute a
SWARM-issued objective safely and robustly, including:

- stabilization and attitude control;
- motor/actuator control;
- following an already-issued waypoint or trajectory;
- local obstacle avoidance where the vendor autopilot provides it;
- sensor capture and telemetry production;
- reporting mission progress and execution evidence;
- enforcing geofence and altitude safety constraints;
- immediate low-battery, lost-link or equivalent safety failsafes;
- emergency landing/RTL behavior required to fail safe when central control is
  unavailable;
- bounded local adaptation when the required information is local, the objective
  and priority are unchanged, no other objective's capacity is consumed, and the
  action stays inside a policy or authority envelope previously issued by SwarmOS.

Examples of a future permissible local adaptation could include redistributing a
purely local role inside an already-authorized group when every affected member
has the required capability and no mission-wide trade-off is introduced.

This is deliberately narrower than mission authority. The test is not simply
"central versus decentralized". The test is whether the decision requires
mission-wide knowledge or changes authoritative ownership of objectives and
shared capabilities.

### Agents must not

An adapter, physical agent or local group must not independently:

- create or award a new fleet mission;
- select itself or another agent for a different objective;
- import or execute the central allocator;
- consume capacity owned by another objective;
- change global mission priority;
- substitute a materially different capability when that changes mission-level
  trade-offs;
- turn a local observation directly into a new fleet objective;
- change the mission objective outside a bounded authority envelope;
- form an autonomous sub-swarm with independent authority over shared fleet
  capacity.

## Decision escalation rule

A decision must escalate to SwarmOS when any of the following is true:

1. it changes the objective or success criteria;
2. it changes priority among objectives;
3. it reallocates an executor or capability between objectives;
4. it substitutes a capability whose operational meaning differs from the one
   already authorized;
5. it needs fleet-wide availability, constraints or mission context to choose
   correctly;
6. it crosses an authority, safety or policy boundary that was not delegated in
   advance.

If none of these conditions applies, a bounded local mechanism may handle the
adaptation if that mechanism is explicitly supported by the relevant adapter or
execution-group policy.

## Data from agents is evidence, not authority

Distributing bounded local adaptation does not make agent-originated state
trusted by default.

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

The security property provided by this ADR is:

> Compromising one physical agent does not grant that agent legitimate authority
> to change fleet objectives, priorities or shared-capacity allocation.

## Multi-agent execution groups

`ExecutionGroup` remains a **SwarmOS-owned logical coordination object** in the
current runtime.

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
adapter mission kind. SwarmOS decomposes it into child `VERIFY` missions before
dispatch. Physical adapters fail closed if an orchestration-only parent is sent
to them directly. `COVER` follows the same rule and is decomposed into per-agent
`PATROL` slices.

For a three-agent cooperative verification, SwarmOS can compose:

```text
ExecutionGroup
├── PRIMARY_OBSERVER   -> mav-002 -> child VERIFY
├── SECONDARY_OBSERVER -> mav-004 -> child VERIFY
└── OVERWATCH          -> mav-006 -> child VERIFY
```

### Current replacement behavior remains central

The implemented and validated replacement path remains unchanged by this ADR.
If a member fails, SwarmOS marks the role degraded and centrally selects a spare.
The failed member is retained in group history as `REPLACED`; the replacement
records `replaces_agent_id` and receives a fresh child mission.

No peer-local replacement mechanism is implemented or claimed today. A future
local replacement path would be permitted only if it satisfies the bounded-local
rules above and is separately implemented, audited and validated.

### Payload authority remains role-scoped in SwarmOS

For cooperative intrusion verification, only `PRIMARY_OBSERVER` is authorized by
the central presence-response policy to execute the bounded light/speaker
response. Secondary observers and overwatch remain observation roles. This is a
SwarmOS policy decision, not an agent-side capability choice.

## Runtime boundary

The current control loop remains:

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

The long-term boundary is hierarchical rather than centralization for its own
sake: keep adaptation as local as the required information and delegated
authority allow, and escalate when the consequence is mission-wide.

## Consequences

- SWARM remains the authoritative layer for objectives, priorities and shared
  physical-capacity allocation.
- Vendor adapters stay replaceable and do not become independent fleet brains.
- Local autonomy is not artificially suppressed when it can improve resilience
  without changing mission intent.
- Cross-capability substitution and cross-objective reassignment remain visible,
  explainable and auditable at the SwarmOS layer.
- A compromised endpoint has a bounded legitimate authority surface.
- Central SwarmOS availability remains important, but future bounded local
  adaptation can reduce unnecessary dependence on it for purely local recovery.
- The architecture can remain hierarchical as fleets become larger and more
  heterogeneous.

## Enforcement

- `adapters/base.py` defines adapters as SWARM-issued mission executors.
- Adapter implementations must not import allocator, scheduler, autonomy or
  orchestrator decision modules unless a future ADR explicitly introduces a
  bounded local mechanism.
- Architecture tests enforce the current dependency boundary.
- Physical adapters reject orchestration-only parent objectives.
- Current single-agent allocation decisions are computed by the orchestrator
  from canonical fleet state and published as structured truth frames.
- Execution-group composition and lifecycle are published as structured
  `swarm:execution-groups` truth frames and projected to REST/WebSocket clients
  without frontend recomputation.
- Local autopilot failsafes remain explicitly permitted.
- Any future local adaptation mechanism must define its authority envelope and
  escalation conditions and must not silently expand the claims of the current
  runtime.

## Validation boundary

This amendment changes the architecture boundary, not the validated runtime
claim. Existing tests and PX4 SITL evidence still demonstrate central allocation
and central execution-group replacement. No peer-local mission redistribution is
implemented or field-validated today.

Future local adaptation must be tested separately for bounded authority,
escalation behavior, determinism/auditability and failure containment before it
is described as implemented behavior.
