# SwarmOS Architecture Overview

`docs/architecture.md` is the detailed architecture dossier. This page is the
short architecture entrypoint and index.

## System boundaries

- **SwarmOS**: all backend-side domains (`core/`, `swarm_os/`, `orchestrator/`,
  `adapters/`, `sim/`, `backend/`, `infra/`, `scripts/`).
- **Console**: operator-facing surface in `frontend/`; renders state and sends
  intent.

## Authority invariant

**SwarmOS decides. Physical agents execute. Console supervises.**

Physical agents are thin executors at the mission layer. They report telemetry,
observations and progress, then execute missions/retasks chosen by SwarmOS. They
do not allocate themselves, choose fleet objectives, command peers, or form an
independent mission-decision layer.

Onboard autopilots retain low-level flight control and bounded safety failsafes
such as stabilization, obstacle avoidance, geofence enforcement, low-battery
RTL and lost-link behavior.

See [`ADR 0011`](../adr/0011-central-decision-authority.md).

## Runtime components

1. Fleet adapters report telemetry/evidence and execute **SWARM-issued** mission
   commands through vendor/autopilot protocols.
2. SwarmOS orchestrator/policy/scheduler perform mission-level decisions,
   allocation, ownership and coordination.
3. Backend exposes REST + WebSocket projections of SwarmOS truth.
4. Console consumes authenticated REST + WS projections and sends operator
   intent; it never invents an operational decision.

## Product input model

SWARM accepts cues from operators, software systems, sensors, cameras, previous
observations or other approved sources. A cue is input, not operational command
authority. SwarmOS decides whether it warrants action, which physical agent or
agents should respond, and what should happen next.

Edge/on-device perception may eventually produce low-latency observations, but
those observations remain evidence sent to SwarmOS. They do not grant the
physical agent authority to allocate or retask the fleet.

## Multi-agent model

Collective capability should be composed centrally. A future execution group may
contain several cheap physical agents with different roles, but the group is a
SwarmOS-owned logical object rather than an autonomous sub-swarm that makes its
own mission decisions.

## Deep links

- Full architecture: [`docs/architecture.md`](../architecture.md)
- Central decision authority: [`ADR 0011`](../adr/0011-central-decision-authority.md)
- Adapter contract: [`ADR 0003`](../adr/0003-drone-adapter-interface.md)
- Threat model: [`docs/security/threat-model.md`](../security/threat-model.md)
- ADRs: [`docs/adr/`](../adr)
- Observability: [`docs/observability/overview.md`](../observability/overview.md)
- Deployment: [`docs/ops/deploy.md`](../ops/deploy.md)
