# SWARM OS — Architecture

> Primary architecture entrypoint: [`docs/architecture/overview.md`](architecture/overview.md).
> This file contains the detailed architecture narrative.

## Central authority invariant

**SwarmOS decides. Physical agents execute. Console supervises.**

Mission-level authority is centralized in SwarmOS. Drones and other physical
agents report telemetry, observations and execution progress; they do not bid
for missions, choose their own objectives, command peers, or independently
retask the fleet.

The onboard autopilot still owns low-level flight execution and bounded safety
failsafes such as stabilization, waypoint following, geofence enforcement,
low-battery RTL and lost-link behavior. Those answer **how to fly safely**, not
**what the fleet should do**.

See [`docs/adr/0011-central-decision-authority.md`](adr/0011-central-decision-authority.md).

## System diagram

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│                                Console                                       │
│                 frontend/ — renders truth + sends operator intent             │
└────────────────────────────────▲─────────────────────────────────────────────┘
                                 │ REST + WebSocket
┌────────────────────────────────┴─────────────────────────────────────────────┐
│                                Backend                                       │
│           FastAPI projections, auth, persistence, WebSocket bridge            │
└────────────────────────────────▲─────────────────────────────────────────────┘
                                 │ bus
┌────────────────────────────────┴─────────────────────────────────────────────┐
│                                SwarmOS                                       │
│                                                                              │
│  cues / anomalies ──▶ understand ──▶ allocate ──▶ coordinate ──▶ audit       │
│                                  │                                           │
│                  sole mission-level decision authority                       │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │ SWARM-issued missions / retasks / payloads
                 ┌─────────────────┼─────────────────┐
                 ▼                 ▼                 ▼
          ┌────────────┐     ┌────────────┐     ┌────────────┐
          │ Adapter 01 │     │ Adapter 02 │     │ Adapter N  │
          └─────┬──────┘     └─────┬──────┘     └─────┬──────┘
                │                  │                  │
                ▼                  ▼                  ▼
          drone/autopilot    drone/autopilot    other machine
                │                  │                  │
                └──── telemetry / progress / evidence ┴──────▶ SwarmOS
```

## Layering rules

1. **`core/`** has zero I/O. It owns domain contracts and pure decision logic.
2. **`adapters/`** depend on `core/` plus vendor protocols/SDKs. They translate
   SWARM-issued execution commands and report reality. They must not import
   allocator, scheduler, autonomy or orchestrator decision modules.
3. **`orchestrator/`** depends on `core/` and `adapters/base`. It owns live fleet
   allocation, mission ownership and coordinated dispatch without importing
   vendor-specific implementations.
4. **`swarm_os/`** owns server-side state, policy, scheduling and deterministic
   autonomy decisions.
5. **`backend/`** exposes SwarmOS state and bridges bus truth to REST/WebSocket.
6. **`frontend/`** consumes only backend contracts. It never invents operational
   decisions.

Violating these layers means the layer has the wrong responsibility.

## Decision authority boundary

### SwarmOS decides

- whether an event requires a mission;
- which physical agent or agents are eligible;
- why a unit is excluded;
- candidate scores and winner selection;
- mission ownership and role assignment;
- retask, replacement, rotation, abort and return;
- payload-response policy;
- future multi-agent execution-group composition;
- follow-up escalation or conclusion.

### Physical agents execute and report

- stabilize and control the airframe;
- execute an already-issued waypoint/mission;
- apply local obstacle avoidance when available;
- capture sensors and emit telemetry;
- report progress/evidence;
- apply bounded safety failsafes.

An observation from an agent is input to SwarmOS, not permission for that agent
to create a fleet action.

## Current live allocation cycle

The current runtime is centralized even though the legacy candidate DTO is still
named `Bid` for compatibility.

1. A cue/anomaly reaches SwarmOS.
2. The orchestrator creates the mission objective.
3. SwarmOS snapshots canonical `FleetState` for the adapters it owns.
4. SwarmOS centrally excludes busy, unavailable or low-battery units.
5. SwarmOS computes each remaining candidate score from mission and fleet state.
6. SwarmOS selects the winner.
7. SwarmOS publishes a structured `AllocationDecision` containing candidates,
   exclusions, score breakdown and winner.
8. SwarmOS publishes the award and invokes the selected adapter's
   `execute_mission()` contract.
9. The adapter translates the command to the vendor/autopilot dialect and emits
   execution progress.
10. New telemetry/events return to SwarmOS. Any further retask/replacement is a
    new SwarmOS decision.

There is **no peer Contract Net negotiation in the current runtime** and no
agent-side mission election.

## Runtime message contracts

Canonical models live in `core/swarm_core/messages.py` plus the focused
allocation/runtime/payload modules.

| Type | Current topic/path | Producer | Consumer |
|---|---|---|---|
| `Telemetry` | `swarm:telemetry:<agent_id>` | adapter runner | backend / SwarmOS projections |
| `FleetState` | `swarm:fleet:state` | adapter/fleet runner | orchestrator + backend |
| `Anomaly` | `swarm:anomalies` | perception / cue source | orchestrator + backend |
| `AllocationDecision` | `swarm:allocations` | orchestrator | backend + Console |
| `Award` | `swarm:missions:award` | orchestrator | audit/backend path |
| `MissionProgress` | `swarm:missions:progress:<mission_id>` | selected adapter via orchestrator | backend |
| `MissionRuntimeEvent` | `swarm:missions:runtime` | orchestrator projection | backend + Console |
| `PayloadEvent` | `swarm:payload:events` | presence-response orchestrator | backend + Console |

`Bid` remains an internal compatibility-shaped candidate-score record. It is
computed inside SwarmOS and is not a permission surface exposed to an aircraft.

## Mission DSL

`PATROL`, `VERIFY`, `COVER`, `RELAY`, `RTL_DOCK` are defined in
`core/swarm_core/missions.py`.

Adapters translate a **selected SWARM mission** into a vendor dialect. For
example, the current MAVLink/PX4 path uploads waypoint missions, starts
`AUTO.MISSION`, observes mission progress and issues RTL. PX4 owns low-level
flight execution; it does not choose why or where the fleet should respond.

`COVER` describes a multi-unit objective but is intentionally rejected by the
MAVLink adapter: decomposition into per-agent work belongs above the adapter.
First-class dynamic execution groups remain a future SwarmOS capability rather
than an agent-side coordination mechanism.

## Agent FSM

```text
DOCKED ──takeoff──▶ TAKEOFF ──mission──▶ EN_ROUTE ──arrive──▶ ON_STATION
   ▲                                             │                 │
   │                                             ▼                 │
   ├────────── DOCKING ◀── LANDING ◀──── RTL ◀──┴─────────────────┘
   │                                             ▲
   └──────── local safety fail-safe when central control is unavailable ──────
```

FSM state is operational evidence. It does not grant an agent decision authority.

## Safety exception

Centralized mission authority must not remove the autopilot's ability to keep the
aircraft safe when communication or central software fails.

Allowed local reflexes include:

- lost-link RTL;
- low-battery RTL;
- geofence enforcement;
- altitude limits;
- emergency land/return behavior;
- low-level stabilization and obstacle avoidance.

SwarmOS must know these declared failsafes so it can reason about what a unit may
do when the link is unavailable.

## Security implication

Central authority reduces the legitimate authority of each endpoint; it does not
make a drone impossible to compromise. A compromised unit can still falsify
telemetry or sensor data, ignore commands, or be directly manipulated at the
flight-controller/link layer.

Agent-originated data is therefore semi-trusted evidence. Freshness, rate, range
and policy checks remain required. Stronger attestation/corroboration may be
added later only when implemented and validated.

The concrete invariant is:

> Compromising one physical agent must not grant that agent legitimate authority
> to allocate or command the rest of the fleet.

## Multi-agent execution groups

When SWARM needs several cheap agents to create one larger capability, the group
is a **SwarmOS-owned logical execution object**.

Example:

```text
MISSION: inspect anomaly

SwarmOS forms execution group EG-42
  mav-002 → primary observation
  mav-004 → secondary viewpoint
  mav-006 → illumination
```

The drones do not negotiate those roles. If `mav-002` degrades, its telemetry
returns to SwarmOS and SwarmOS decides whether `mav-008` should replace it.

This is how collective capability can scale without putting a separate fleet
brain on every cheap physical agent.

## Persistence

PostgreSQL/Timescale-backed persistence and audit remain backend concerns. The
runtime decision remains server-owned whether or not a given decision is
persisted synchronously.

## Frontend

Console is a truth renderer and intent surface. It may show:

- fleet state and mission ownership;
- anomalies and evidence;
- structured allocation candidates/exclusions/scores;
- mission runtime evidence;
- payload execution evidence.

It must not calculate a winner, infer a physical payload result, or invent a
mission transition that SwarmOS did not publish.

## Migration paths

- **Transport** — Redis pub/sub may later move to NATS/MQTT or another transport;
  decision authority remains in SwarmOS.
- **Simulation** — kinematic sim and PX4 SITL may graduate to physical hardware;
  adapter authority does not expand.
- **Perception** — inference may occur centrally or at the edge for latency. An
  edge model may emit an observation/cue, but that observation is still input to
  SwarmOS; it does not itself allocate or command the fleet.
- **Fleet scale** — future cells/execution groups are logical partitions managed
  by SwarmOS, not autonomous sub-swarms with independent mission authority.
