# SWARM OS

> Autonomous coordination + interoperability layer for heterogeneous drone fleets.
> **Many units. One intention.**

## Read this first

[`swarm-thesis.md`](swarm-thesis.md) is the canonical startup thesis for SWARM.

It defines what SWARM is, the problem it solves, why the coordination layer
matters, the long-term vision, the first wedge, the dual-use defense boundary,
the low-cost fleet economics, and the product boundaries.

**When any other product, roadmap, architecture, or strategy document conflicts
with it, `swarm-thesis.md` is the source of truth.**

SWARM OS is the software layer that turns a heterogeneous fleet of off-the-shelf drones
(DJI, MAVLink/PX4, Autel, Parrot, Skydio) into a single coordinated system. The drones
remain replaceable. The coordination layer is the product.

The initial product shape is **SWARM Patrol Cell** for private high-value
territories (villas, vineyards, resorts, agricultural land): mobile drone
patrol, verification, evidence and escalation without requiring SWARM-owned
fixed cameras, thermal towers or proprietary ground sensors in the MVP.
Wildfire-risk patrol is the first beachhead, but the same loop can support
intrusion, unknown person/vehicle, missing-person search inside a bounded
site, post-storm damage checks, asset anomalies, manual verification requests
and stale-sector checks. The architecture generalizes to any
territorial-resilience use case that reuses this loop.

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

For the first product shape, SWARM treats weather/fire-risk feeds, public
satellite or hotspot signals, human reports, guard/owner call-ins, previous
drone patrol observations and stale-sector routines as cues. Drones act as
mobile sensors and response units: they patrol priority sectors, verify cues
from useful vantage points and create an auditable evidence packet.

## Repo map

```
core/                domain layer — pure Python, no I/O (THE OS)
  swarm_core/        messages, missions DSL, FSM, allocator, geometry

adapters/            multi-vendor drone interoperability (THE MOAT)
  base.py            DroneAdapter Protocol
  simulated/         drives the 2D sim — used by `make demo`
  mavlink/           PX4 / ArduPilot adapter via pymavlink (Phase 5 CI-verified)
  dji_cloud/         DJI Dock + DJI Cloud API (REST + MQTT)
  dji_psdk/          DJI Payload SDK (onboard SoC) — stub
  autel/ parrot/ skydio/    stubs — typed against vendor protocols

sim/                 light Python 2D simulator (Gazebo/PX4 SITL remains a bench gate)
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

make setup               # python venv + deps + pnpm install
make bootstrap-auth-dev  # local DB/Redis passwords + JWT + 3 operators
make infra               # postgres + redis via docker compose
make demo                # boots sim + orchestrator + backend + frontend
                         # opens http://localhost:3000 — log in via /login
```

`make bootstrap-auth-dev` is idempotent: it first runs
`make bootstrap-dev-env` to generate local-only Postgres/Redis passwords,
then generates a random `SWARM_JWT_SECRET` if `.env` doesn't already carry
one, and writes
`infra/config/operators.yaml` with three local accounts (all share the
password `swarm-dev`):

| operator id      | role      | MFA at login         |
|------------------|-----------|----------------------|
| `op-viewer01`    | viewer    | no                   |
| `op-operator01`  | operator  | no                   |
| `op-commander01` | commander | yes — scan TOTP URI  |

The commander's TOTP URI is written to
`infra/config/operators.yaml.commander-totp.txt` for one-time
enrolment in any standard authenticator (Aegis / 1Password / FreeOTP /
Google Authenticator). Both files are gitignored; never commit them.
The drone-day checklist
[`docs/ops/drone-day-checklist.md`](docs/ops/drone-day-checklist.md)
§2.C documents the real production provisioning flow. See
[`docs/security/auth.md`](docs/security/auth.md) for the full auth
design.

Run a specific Phase 7 scenario in one command (each boots the same
sim + backend + Console stack with the matching YAML, autonomy
baseline enabled, and a background metrics collector that dumps an
audit-log snapshot to `docs/bench/artifacts/`):

```bash
make demo-wildfire-sim   # SMOKE → FIRE, autonomy R1 + R2
make demo-intrusion-sim  # perimeter intrusion, autonomy R1
make demo-search-sim     # missing-person search, autonomy R1
```

`make demo` and `./scripts/demo_wildfire.sh` still work and delegate
to `demo-wildfire-sim`.

Production deploys (Kubernetes via Helm, single-node via
`docker-compose.prod.yml`) are documented in
[`docs/ops/deploy.md`](docs/ops/deploy.md); the migrations runbook lives at
[`docs/ops/migrations.md`](docs/ops/migrations.md). Hardware-day external
assets (DNS, TLS, Sigstore, off-site backup) are catalogued in
[`docs/ops/drone-day-checklist.md`](docs/ops/drone-day-checklist.md) §2.E.

## Testing

```bash
make test      # pytest (core, adapters, orchestrator, backend) + frontend vitest
make lint      # ruff + mypy + eslint + tsc
make audit     # pip-audit + pnpm audit + bandit
```

## Security

SwarmOS controls drones in the physical world; security is a hard
invariant, not aspirational. The full posture is documented in
[`SECURITY.md`](SECURITY.md) (disclosure policy + supported versions) and
[`docs/security/threat-model.md`](docs/security/threat-model.md) (STRIDE +
threat scenarios + controls). The incident response runbook lives at
[`docs/security/incident-response.md`](docs/security/incident-response.md).

Active controls — these are part of the product, not aspirational:

- Lockfiles committed (`frontend/pnpm-lock.yaml`, `uv.lock`).
- `frontend/.pnpmrc` with `ignore-scripts=true` (no postinstall execution
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
  gitleaks, ESLint security plugin, pnpm audit.
- Local: pre-commit hooks (gitleaks, detect-secrets, ruff, end-of-file,
  trailing whitespace, large file guard).

Report a vulnerability:
https://github.com/DavideCapurr/swarm/security/advisories/new


## Documentation map

- Canonical startup thesis: [`swarm-thesis.md`](swarm-thesis.md)
- Architecture overview: [`docs/architecture/overview.md`](docs/architecture/overview.md)
- Product wedge: [`docs/product/patrol-cell.md`](docs/product/patrol-cell.md)
- REST API snapshot: [`docs/api/openapi.yaml`](docs/api/openapi.yaml)
- WebSocket contract: [`docs/api/ws-contract.md`](docs/api/ws-contract.md)
- Operator guide: [`docs/operator/manual.md`](docs/operator/manual.md)
- Operator training: [`docs/operator/training.md`](docs/operator/training.md)
- Operator acceptance runbook: [`docs/operator/acceptance.md`](docs/operator/acceptance.md)
- Ops runbook index: [`docs/ops/runbook.md`](docs/ops/runbook.md)
- Security disclosure: [`docs/security/disclosure.md`](docs/security/disclosure.md)
- External pen-test scope: [`docs/security/pentest-scope.md`](docs/security/pentest-scope.md)
- Compliance baseline: [`docs/compliance/gdpr.md`](docs/compliance/gdpr.md), [`docs/compliance/retention.md`](docs/compliance/retention.md), [`docs/compliance/dpa-template.md`](docs/compliance/dpa-template.md), [`docs/compliance/drone-regulations.md`](docs/compliance/drone-regulations.md)
- Developer onboarding + release: [`docs/dev/onboarding.md`](docs/dev/onboarding.md), [`docs/dev/release-process.md`](docs/dev/release-process.md)
- Phase 7+ execution roadmap: [`docs/plan/swarm-roadmap-evidence-to-scale.md`](docs/plan/swarm-roadmap-evidence-to-scale.md)
- CV baseline (Phase 7.D): [`docs/cv/phase-7d.md`](docs/cv/phase-7d.md)

## For Claude Code sessions

[`CLAUDE.md`](CLAUDE.md) is the entry point for any Claude Code session in
this repo: terminology, hard rules, current phase, conventions. The full
Phase 0-6 development plan is at
[`docs/plan/swarmos-roadmap.md`](docs/plan/swarmos-roadmap.md). Current
Phase 7+ execution order is at
[`docs/plan/swarm-roadmap-evidence-to-scale.md`](docs/plan/swarm-roadmap-evidence-to-scale.md).
Execution progress lives at [`docs/STATUS.md`](docs/STATUS.md).

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for component diagrams and message
contracts. Key decisions are recorded as ADRs in [`docs/adr/`](docs/adr/).

## Roadmap

- **Phase 0-6** — technical foundation already tracked in
  [`docs/STATUS.md`](docs/STATUS.md); Phase 5 PX4/SITL and hardware
  evidence are still explicit de-risk items.
- **Phase 7** — finish the repeatable Patrol Cell simulation proof now,
  with wildfire-risk as the first front door and intrusion/search as
  extension demos.
- **Phase 8-10** — evidence sprint: customer discovery, flight-path/bench
  proof, future-batch application pack and the BIEF founder decision gate.
- **Phase 11+** — supervised field proof, pilot path, capital and the later
  platform/scale phases only after the first evidence supports them.

The full strategic roadmap is in [`docs/vision.md`](docs/vision.md), distilled from
the founder documents in [`docs/pdf/`](docs/pdf/).

---

*Quiet. Precise. Already arrived.*
