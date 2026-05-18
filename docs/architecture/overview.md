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

## Deep links
- Full architecture: [`docs/architecture.md`](../architecture.md)
- ADRs: [`docs/adr/`](../adr)
- Observability: [`docs/observability/overview.md`](../observability/overview.md)
- Deployment: [`docs/ops/deploy.md`](../ops/deploy.md)
