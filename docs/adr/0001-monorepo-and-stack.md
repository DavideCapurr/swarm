# ADR 0001 — Monorepo and stack

**Status**: Accepted
**Date**: 2026-05-13

## Context

Greenfield repo. The strategy PDFs prescribe Python + ROS2 + Gazebo + FastAPI +
TimescaleDB + web dashboard. We need to choose a layout and dependency set that
matches what SWARM OS *actually is* (a coordination + interoperability service),
not just the recommended capability catalog.

## Decision

- **Monorepo**, single git repository, separate top-level packages per concern:
  `core/`, `adapters/`, `sim/`, `orchestrator/`, `backend/`, `frontend/`.
- **Python 3.11+** for everything backend-shaped. Single `pyproject.toml` at the
  root, all packages installed editable.
- **Next.js 15 + TypeScript + Tailwind** for the operator dashboard.
- **PostgreSQL + TimescaleDB** for telemetry persistence (hypertable on `ts`).
- **Redis pub/sub** as the day-1 transport bus, abstracted behind
  `orchestrator/swarm_orchestrator/bus.py` for future swap.
- **Pydantic v2** for all domain messages — gives us validation, schema export,
  and clean `.model_dump()` for serialization across the bus.
- **MAVSDK-Python** and **paho-mqtt** as optional extras (only needed for
  MAVLink and DJI Cloud adapters respectively).

## Consequences

- One repo to clone, one `make demo` to run. Lowers contributor friction.
- Frontend and backend can be deployed independently later (containers from the
  same repo).
- The `pyproject.toml` editable install pattern means `from core.swarm_core ...`
  resolves uniformly across all packages.

## Alternatives considered

- **Polyrepo** — rejected: too much friction for one-person/small-team velocity
  at this stage.
- **Pure Python without TimescaleDB** — rejected: telemetry is high-rate
  time-series; we want hypertables now, not after a migration.
- **gRPC bus** — rejected for now: Redis pub/sub is operationally trivial and we
  retain the swap path through `bus.py`.
