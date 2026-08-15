# SWARM OS

> Autonomous coordination + interoperability layer for heterogeneous drone fleets.
> **Many units. One intention.**

## Read this first

[`swarm-thesis.md`](swarm-thesis.md) is the canonical startup thesis for SWARM.

It defines the company-level problem, the coordination-layer thesis, the long-term vision, the current proof level, and the rules for choosing a first market.

**When another product, roadmap, architecture, or strategy document conflicts with it, `swarm-thesis.md` is the source of truth.**

SWARM OS turns a heterogeneous fleet of off-the-shelf autonomous aircraft into one coordinated system. The drones remain replaceable. The coordination layer is the product.

The first commercial wedge is **not yet fixed**. Wildfire, private-land patrol, industrial security, inspection, energy infrastructure, logistics, mining, and other environments are hypotheses to test, not company identity. The next market phase is customer discovery around frequent, expensive physical-verification workflows.

## What SWARM OS actually does

DJI / PX4 / Skydio and other vendors already ship onboard autopilots. They handle stabilization, waypoint following, RTL, obstacle avoidance, and other single-aircraft flight functions.

SWARM OS operates one layer above:

| Layer | Owner | Responsibility |
|---|---|---|
| Flight control | Vendor autopilot | How a single aircraft flies |
| **Mission & fleet** | **SWARM OS** | **Who responds, when, where, why, with which asset, and what happens next** |

A mission can arrive from an operator, software system, sensor, previous observation, or other cue. SWARM evaluates the fleet and allocates the best available unit or units based on mission priority, distance, battery, capability, current task, and operational constraints.

The current allocator is auction-based. The architecture is vendor-neutral through adapters.

## Current proof level

SWARM is currently a software and simulation/SITL system, not a deployed physical fleet.

What exists today:

- domain core, mission DSL and FSM;
- auction-based mission allocation;
- heterogeneous adapter architecture;
- simulated adapter;
- MAVLink/PX4 adapter;
- orchestrator and fleet management;
- FastAPI backend and WebSocket telemetry;
- Next.js operator Console;
- persistence and audit history;
- autonomy/shadow-mode logic;
- CV-backed simulation scenarios;
- security and operations baseline.

The MAVLink/PX4 path has been **PX4 SITL-validated** for connect, telemetry ingest, mission dispatch and RTL. It is **not yet bench- or field-validated on physical aircraft**.

That distinction is intentional and must remain explicit.

## Next technical demo

The next investor-readable demo is a **multi-vehicle PX4 SITL coordination demo**. It does not require SWARM to buy drones.

The demo target is:

1. several PX4 SITL vehicles start in different positions and states;
2. a neutral task such as `VERIFY anomaly at sector C7` enters SWARM;
3. SWARM evaluates distance, battery, availability and capability;
4. SWARM selects the aircraft autonomously;
5. the mission is dispatched through the MAVLink/PX4 path;
6. a second event or state change occurs while the first mission is active;
7. SWARM re-tasks, replaces, adds or returns units without manual aircraft selection;
8. the Console shows why each decision was made;
9. the mission completes and the fleet returns to an available state.

The point of the demo is not to make simulation look like real flight. It is to make the coordination layer undeniable.

**The aircraft fly themselves. SWARM decides what the fleet should do.**

Existing wildfire / intrusion / search scenarios remain useful regression and product-demonstration fixtures, but wildfire is no longer the canonical first wedge.

## Repo map

```text
core/                domain layer — pure Python, no I/O
  swarm_core/        messages, missions DSL, FSM, allocator, geometry

adapters/            multi-vendor interoperability
  base.py            DroneAdapter Protocol
  simulated/         simulation adapter
  mavlink/           PX4 / ArduPilot via pymavlink
  dji_cloud/         DJI Dock + Cloud API
  dji_psdk/          DJI Payload SDK stub
  autel/ parrot/ skydio/    typed vendor stubs

sim/                 Python simulation environment
orchestrator/        coordination service
backend/             FastAPI REST + WebSocket telemetry
frontend/            Next.js operator Console
infra/               Postgres/TimescaleDB + Redis
scripts/             development, demo and validation scripts
docs/                architecture, product, evidence, ops, YC and strategy docs
```

## Quickstart

```bash
git clone https://github.com/davidecapurr/swarm.git
cd swarm
cp .env.example .env

make setup
make bootstrap-auth-dev
make infra
make demo
```

`make demo` boots the simulation, orchestrator, backend and frontend and opens the Console at `http://localhost:3000`.

Existing scenario commands:

```bash
make demo-wildfire-sim
make demo-intrusion-sim
make demo-search-sim
```

These are demonstration scenarios, not declarations of the first commercial market.

## Testing

```bash
make test
make lint
make audit
```

The repository uses typed claims and evidence gates. A simulated result must not be described as physical validation, and a SITL result must not be described as bench or field validation.

## Security

SwarmOS coordinates systems that can act in the physical world, so security is treated as a product constraint rather than a later add-on.

The baseline includes lockfiles, pinned CI actions and images, CORS and WebSocket origin enforcement, security headers, strict input models, request limits, rate limiting, dependency scanning, CodeQL/Bandit/Semgrep/Trivy/gitleaks and documented threat/incident-response processes.

See:

- [`SECURITY.md`](SECURITY.md)
- [`docs/security/threat-model.md`](docs/security/threat-model.md)
- [`docs/security/incident-response.md`](docs/security/incident-response.md)

## Strategy and execution

- Canonical startup thesis: [`swarm-thesis.md`](swarm-thesis.md)
- Live execution status: [`docs/STATUS.md`](docs/STATUS.md)
- Architecture overview: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- Evidence-to-scale roadmap: [`docs/plan/swarm-roadmap-evidence-to-scale.md`](docs/plan/swarm-roadmap-evidence-to-scale.md)
- YC readiness: [`docs/yc/readiness-and-gaps.md`](docs/yc/readiness-and-gaps.md)
- YC application draft: [`docs/yc/application-draft.md`](docs/yc/application-draft.md)
- Customer discovery: [`docs/yc/customer-discovery-kit.md`](docs/yc/customer-discovery-kit.md)
- PX4/SITL evidence: [`docs/bench/phase9-sitl-validation.md`](docs/bench/phase9-sitl-validation.md)

## Product discipline

From the current state, the highest-value next evidence is not speculative platform breadth.

The priority is:

1. make multi-agent coordination obvious in a short PX4 SITL demo;
2. discover a high-frequency first workflow through real operator interviews;
3. validate the same control path on borrowed, partnered, or later purchased physical hardware;
4. earn the first supervised pilot;
5. expand the platform only from real deployment evidence.

The long-term vision remains much larger than drones: a coordination runtime that gives software reliable physical presence and agency through distributed autonomous machines.

---

*Quiet. Precise. Already arrived.*
