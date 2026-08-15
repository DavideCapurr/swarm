# SWARM

> **SWARM is a real-time orchestration layer for physical agents.**
>
> **SwarmOS decides. Physical agents execute.**

The world changes. SWARM reallocates physical agents in real time.

SwarmOS is the sole mission-level decision authority. Physical agents report state, observations, progress, and execution evidence; SwarmOS decides which objective to pursue, which agents are eligible, how many are needed, which roles they receive, who owns each mission, when to replace or retask an agent, and which fleet-level or payload action happens next.

A physical agent can be a drone, rover, robot, or another compatible machine. Today, the live autopilot integration path in this repository is MAVLink/PX4 **SITL**. No physical-aircraft deployment is claimed.

## Why SWARM exists

Individual autopilots already solve the local problem of keeping one machine operating safely: stabilization, waypoint following, obstacle avoidance where available, geofencing, low-battery behavior, lost-link behavior, and RTL.

SWARM solves the fleet problem above that layer:

- which physical agent or agents should respond;
- which units are ineligible and why;
- how many agents one objective requires;
- which role each agent should perform;
- how active missions share limited fleet capacity;
- when an agent should be replaced, retasked, returned, or removed;
- which payload action is authorized;
- how the fleet should react when conditions change.

That is why SWARM is not simply “AI drone software.” The physical endpoints do not contain independent fleet brains and do not negotiate mission ownership with peers. SwarmOS owns the mission-level decision loop and the audit trail.

## What works today

The current repository contains an end-to-end coordination runtime with centralized fleet allocation, mission ownership, multi-agent `ExecutionGroup` composition, live replacement, MAVLink/PX4 execution, backend truth projections, and the `/demo/intrusion` operator Console.

The strongest validated paths are:

| Proof | Result | Evidence |
|---|---|---|
| Dynamic multi-event allocation | event 2 arrives while the first PX4 mission is still active; SwarmOS selects a different available PX4 and both missions overlap | [`phase10-dynamic-multi-event-validation.md`](docs/bench/phase10-dynamic-multi-event-validation.md) |
| Verified arrival semantics | `ON_STATION` requires final `MISSION_ITEM_REACHED`; timeout fails closed | [`phase9-multi-sitl-validation.md`](docs/bench/phase9-multi-sitl-validation.md) |
| Bounded payload response | PX4 SITL output is confirmed before light state is reported; speaker remains explicitly simulated | [`payload-presence-sitl-validation.md`](docs/bench/payload-presence-sitl-validation.md) |
| Multi-agent `ExecutionGroup` | one `COOPERATIVE_VERIFY` objective is decomposed into 3 role-specific child missions across 3 of 4 PX4 SITL agents | [`phase11-execution-group-validation.md`](docs/bench/phase11-execution-group-validation.md) |
| Live member failure + replacement | selected `mav-003` is SIGKILLed while `EN_ROUTE`; SwarmOS selects spare `mav-001` for the same role; replacement reaches `MISSION_ITEM_REACHED`, receives RTL ACK, and the group completes | [`phase12-execution-group-live-failover.md`](docs/bench/phase12-execution-group-live-failover.md) |
| Final investor-demo rehearsal | 3 consecutive clean takes, ~62 s each, with event 2 arriving while mission 1 is still active, exact `BUSY` exclusion with active mission id, different second owner, concurrent missions, cleanup, and acknowledged RTL | [`final-demo-rehearsal.md`](docs/bench/final-demo-rehearsal.md) |

These are **SITL/runtime proofs**, not physical-aircraft field proofs.

## Architecture

```text
operators / software / sensors / observations
                    │
                    ▼
                 SwarmOS
       understand + decide + allocate
       compose + replace + retask + audit
                    │
        SWARM-issued child missions
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
    adapter      adapter      adapter
       │            │            │
       ▼            ▼            ▼
 physical agent physical agent physical agent
       │            │            │
       └── telemetry / progress / evidence ──► SwarmOS
```

**SwarmOS decides:** objective, eligibility, allocation, required agent count, roles, mission ownership, replacement, retasking, payload actions, and fleet-level response.

**Physical agents execute:** low-level flight/motion control, already-issued mission primitives, sensor capture, telemetry, execution evidence, and bounded local safety failsafes.

`ExecutionGroup` is a SwarmOS-owned logical object. It is not an autonomous sub-swarm. SwarmOS forms the group, assigns distinct agents to roles, creates per-agent child missions, aggregates lifecycle state, and centrally selects replacements when required.

See [`docs/architecture.md`](docs/architecture.md) and [`ADR 0011 — Central decision authority`](docs/adr/0011-central-decision-authority.md).

## Demo

The definitive demo surface is **`/demo/intrusion`**. The legacy dashboard at `/` is separate and is intentionally left unchanged.

The final recording runbook is [`docs/bench/final-demo-rehearsal.md`](docs/bench/final-demo-rehearsal.md). Do not replace it with a second incompatible runbook.

The demo deliberately separates runtime truth from visualization:

### Backend/runtime truth

The Console renders server-published allocation and execution truth, including:

- eligible and excluded units;
- exclusion reasons such as `BUSY` and the exact active mission id;
- server-side scores and score breakdown;
- winner and mission ownership;
- `EN_ROUTE`, verified `ON_STATION`, and completion evidence;
- `ExecutionGroup` composition and replacement history;
- structured payload state and execution mode.

### Simulated visualization

- stock CCTV/drone imagery is visualization only;
- imagery/video must remain labeled simulated;
- speaker playback remains `SIMULATED`;
- PX4 light output may be described as confirmed only where the runtime actually observed the configured SITL output state;
- no physical lamp, speaker, aircraft, or field deployment is implied.

## Product thesis

The system is designed so that **many simple, inexpensive physical agents can be composed dynamically into a larger capability**. The claim is architectural, not an assertion that cheaper hardware always produces lower total operating cost.

The coordination layer remains vendor-neutral where practical: adapters translate SwarmOS-issued work into vendor/autopilot protocols without gaining mission authority.

The long-term target is broader than drones: a runtime that can coordinate heterogeneous physical agents while keeping mission-level intelligence centralized, observable, and auditable.

## Repo map

```text
core/                domain contracts and pure decision models
swarm_os/            server-side state, scheduling and policy
orchestrator/        centralized allocation, dispatch and ExecutionGroups
adapters/            thin vendor/autopilot execution boundary
sim/                 simulation environment
backend/             FastAPI, persistence and WebSocket projections
frontend/            operator Console
scripts/             development, demo and validation probes
docs/                architecture, status, operations and evidence
```

## Quickstart

```bash
git clone https://github.com/DavideCapurr/swarm.git
cd swarm
cp .env.example .env

make setup
make bootstrap-auth-dev
make infra
make demo
```

`make demo` boots the local system and Console at `http://localhost:3000`.

Scenario fixtures remain available:

```bash
make demo-wildfire-sim
make demo-intrusion-sim
make demo-search-sim
```

These scenarios are fixtures, not claims about a validated first market.

## Validation and claim boundaries

```bash
make test
make lint
make audit
```

Permanent distinctions:

- simulated ≠ SITL-validated;
- SITL-validated ≠ physical bench or field proof;
- PX4 output confirmation ≠ proof of a physical payload;
- central mission authority ≠ an unhackable endpoint;
- local autopilot safety reflexes ≠ fleet-level mission autonomy.

For the current execution state, see [`docs/STATUS.md`](docs/STATUS.md). For the authoritative demo evidence, start with [`docs/bench/final-demo-rehearsal.md`](docs/bench/final-demo-rehearsal.md), [`docs/bench/phase11-execution-group-validation.md`](docs/bench/phase11-execution-group-validation.md), and [`docs/bench/phase12-execution-group-live-failover.md`](docs/bench/phase12-execution-group-live-failover.md).
