# SWARM OS

> Autonomous coordination + interoperability layer for heterogeneous drone fleets.
> **Many units. One intention.**

SWARM OS is the software layer that turns a heterogeneous fleet of off-the-shelf drones
(DJI, MAVLink/PX4, Autel, Parrot, Skydio) into a single coordinated system. The drones
remain replaceable. The coordination layer is the product.

The initial wedge is **wildfire early-detection on private high-value territories**
(villas, vineyards, resorts, agricultural land). The architecture generalizes to any
territorial-resilience use case.

## What SWARM OS actually does

DJI / PX4 / Skydio already ship full onboard autopilots — they handle stabilization,
waypoint following, RTL, obstacle avoidance for a *single* drone executing a *single*
mission. SWARM OS operates one layer above:

| Layer | Owner | Responsibility |
|---|---|---|
| Flight control | Vendor autopilot | PID, waypoint-to-waypoint, single-drone failsafes |
| **Mission & fleet** | **SWARM OS** | **Auction allocation, cross-vendor orchestration, anomaly-driven response, rotational coverage, operator UI** |

When SWARM dispatches `VERIFY(geo=g, sensor=THERMAL, hover=20s)`, the vendor autopilot
flies *how*; SWARM decides *who*, *when*, and *why*, and can re-task mid-flight if a
more critical anomaly arrives.

## Repo map

```
core/                domain layer — pure Python, no I/O (THE OS)
  swarm_core/        messages, missions DSL, FSM, allocator, geometry

adapters/            multi-vendor drone interoperability (THE MOAT)
  base.py            DroneAdapter Protocol
  simulated/         drives the 2D sim — used by `make demo`
  mavlink/           PX4 / ArduPilot / any MAVLink drone (MAVSDK-Python)
  dji_cloud/         DJI Dock + DJI Cloud API (REST + MQTT)
  dji_psdk/          DJI Payload SDK (onboard SoC) — stub
  autel/ parrot/ skydio/    stubs — typed against vendor protocols

sim/                 light Python 2D simulator (placeholder for Gazebo)
orchestrator/        coordination service (auction loop, fleet mgmt)
backend/             FastAPI app — REST + WebSocket telemetry
frontend/            Next.js operator dashboard

infra/               postgres+TimescaleDB init, redis config
scripts/             dev_up, demo_wildfire
docs/                architecture, vision, design-system, ADRs
docs/pdf/            original strategy PDFs
```

## Quickstart

```bash
git clone https://github.com/davidecapurr/swarm.git
cd swarm
cp .env.example .env

make setup     # python venv + deps + pnpm install
make infra     # postgres + redis via docker compose
make demo      # boots sim + orchestrator + backend + frontend
               # opens http://localhost:3000
```

Run the wildfire scenario manually:

```bash
./scripts/demo_wildfire.sh
```

## Testing

```bash
make test      # pytest (core, adapters, orchestrator, backend) + frontend vitest
make lint      # ruff + mypy + eslint + tsc
make audit     # pip-audit + npm audit + bandit
```

## Security

SwarmOS controls drones in the physical world; security is a hard
invariant, not aspirational. The full posture is documented in
[`SECURITY.md`](SECURITY.md) (disclosure policy + supported versions) and
[`docs/security/threat-model.md`](docs/security/threat-model.md) (STRIDE +
threat scenarios + controls). The incident response runbook lives at
[`docs/security/incident-response.md`](docs/security/incident-response.md).

Active controls — these are part of the product, not aspirational:

- Lockfiles committed (`frontend/package-lock.json`, `uv.lock`).
- `frontend/.npmrc` with `ignore-scripts=true` (no postinstall execution
  during install).
- GitHub Actions pinned by full 40-character SHA.
- Docker images pinned by `@sha256:` digest.
- CORS allowlist (env-driven via `SWARM_ALLOWED_ORIGINS`, never `*`).
- WebSocket Origin enforcement.
- Security headers on every HTTP response (CSP, X-Content-Type-Options,
  X-Frame-Options DENY, Referrer-Policy, Permissions-Policy, HSTS in
  prod).
- Pydantic strict mode on all Console-facing aggregates.
- Request body size limit (1 MB) and request timeout (30 s).
- Per-IP token-bucket rate limiter for action endpoints (Phase 1).
- CI: Dependabot, Dependency Review, CodeQL, Bandit, Semgrep, Trivy,
  gitleaks, ESLint security plugin, npm audit.
- Local: pre-commit hooks (gitleaks, detect-secrets, ruff, end-of-file,
  trailing whitespace, large file guard).

Report a vulnerability:
https://github.com/DavideCapurr/swarm/security/advisories/new

## For Claude Code sessions

[`CLAUDE.md`](CLAUDE.md) is the entry point for any Claude Code session in
this repo: terminology, hard rules, current phase, conventions. The full
development plan is at
[`docs/plan/swarmos-roadmap.md`](docs/plan/swarmos-roadmap.md). Execution
progress lives at [`docs/STATUS.md`](docs/STATUS.md).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for component diagrams and message
contracts. Key decisions are recorded as ADRs in [`docs/adr/`](docs/adr/).

## Roadmap

- **Commit 1 (now)** — full skeleton; `make demo` end-to-end; simulated + MAVLink +
  DJI Cloud adapters wired; other vendor adapters stubbed.
- **Commit 2** — design-system tokens from `SWARM-design-system-v1.pdf` applied to the
  frontend.
- **Phase 0 graduation** — promote the 2D sim to Gazebo + PX4 SITL for realistic flight
  dynamics; ROS2 only if/when proprietary drones come into scope (see `docs/adr/0002`).
- **Phase 1+** — real customer pilots, real DJI Dock deployments, ML-based anomaly
  classifier, multi-tenant backend.

The full strategic roadmap is in [`docs/vision.md`](docs/vision.md), distilled from
the founder documents in [`docs/pdf/`](docs/pdf/).

---

*Quiet. Precise. Already arrived.*
