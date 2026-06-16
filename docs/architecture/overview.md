# SwarmOS Architecture Overview

`docs/architecture.md` remains the canonical long-form architecture dossier.
This page is the Phase 6.H overview entrypoint and index.

## System boundaries
- **SwarmOS**: all backend-side domains (`core/`, `swarm_os/`, `orchestrator/`, `adapters/`, `sim/`, `backend/`, `infra/`, `scripts/`).
- **Console**: operator-facing surface in `frontend/`; renders state and sends intent.

## Runtime components
1. Fleet adapters publish telemetry and execute mission intents.
2. Orchestrator performs allocation and scheduling.
3. Backend exposes REST + WebSocket projections.
4. Console consumes authenticated REST + WS projections.

## Product input model

The first product shape is SWARM Patrol Cell: drones provide mobile patrol
and verification for private territory without requiring SWARM-owned fixed
cameras, thermal towers or proprietary ground sensors in the MVP. Wildfire
is the first proof path, not the only event class; the same input and
verification architecture supports any bounded-territory incident that can
be handled through patrol, evidence capture and supervised escalation.

SwarmOS may prioritize missions from lightweight cues: weather/fire-risk
feeds, public satellite or hotspot signals where available, human reports,
guard/owner call-ins, previous drone patrol observations and stale-sector
routines. These cues are not operational truth; adapters and verification
missions turn them into telemetry, captures, event-class-specific evidence
packets and audited decisions.

## Deep links
- Full architecture: [`docs/architecture.md`](../architecture.md)
- Patrol Cell wedge: [`docs/product/patrol-cell.md`](../product/patrol-cell.md)
- ADRs: [`docs/adr/`](../adr)
- Observability: [`docs/observability/overview.md`](../observability/overview.md)
- Deployment: [`docs/ops/deploy.md`](../ops/deploy.md)
