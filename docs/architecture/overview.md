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
   allocation, ownership, execution-group composition, replacement and
   coordination.
3. Backend exposes REST + WebSocket projections of SwarmOS truth.
4. Console consumes authenticated REST + WS projections and sends operator
   intent; it never invents an operational decision.

## Product input model

SWARM accepts cues from operators, software systems, sensors, cameras, previous
observations or other approved sources. A cue is input, not operational command
authority. SwarmOS decides whether it warrants action, which physical agent or
agents should respond, and what should happen next.

Edge/on-device perception may produce low-latency observations, but those
observations remain evidence sent to SwarmOS. They do not grant the physical
agent authority to allocate or retask the fleet.

## Multi-agent model

Collective capability is composed centrally through a SwarmOS-owned
`ExecutionGroup`. One logical objective can be decomposed into complementary
role-specific child missions assigned to distinct physical agents. The group is
a logical coordination object, not an autonomous sub-swarm.

The live PX4 SITL path has validated a three-role `COOPERATIVE_VERIFY` group
across three of four available agents, plus central replacement of an active
failed member with the unused spare. See the Phase 11 and Phase 12 bench
evidence below.

## Current proof links

- Dynamic multi-event allocation: [`phase10`](../bench/phase10-dynamic-multi-event-validation.md)
- Four-PX4 multi-agent `ExecutionGroup`: [`phase11`](../bench/phase11-execution-group-validation.md)
- Live PX4 member failure/replacement: [`phase12`](../bench/phase12-execution-group-live-failover.md)
- Final demo runbook and three clean takes: [`final demo rehearsal`](../bench/final-demo-rehearsal.md)

All PX4 claims above are SITL-scoped, not physical-aircraft proof.

## Deep links

- Full architecture: [`docs/architecture.md`](../architecture.md)
- Central decision authority: [`ADR 0011`](../adr/0011-central-decision-authority.md)
- Adapter contract: [`ADR 0003`](../adr/0003-drone-adapter-interface.md)
- Threat model: [`docs/security/threat-model.md`](../security/threat-model.md)
- ADRs: [`docs/adr/`](../adr)
- Observability: [`docs/observability/overview.md`](../observability/overview.md)
- Deployment: [`docs/ops/deploy.md`](../ops/deploy.md)
