# SwarmOS — execution status

This file tracks where we are in the
[`swarmos-roadmap.md`](plan/swarmos-roadmap.md) plan. Update it at the end
of every phase.

## Current state

| Phase | Description                                           | Status |
|-------|-------------------------------------------------------|--------|
| 0     | Repo discipline + security baseline + shared types    | **done** |
| 1     | SwarmOS Sim Kernel + endpoints + actions              | next |
| 2     | Console Operating Shell + routing + components        | pending |
| 3     | Truth Layer (no DERIVED)                              | pending |
| 4     | Persistence (Timescale + Alembic + audit)             | pending |
| 5     | Real Adapter (MAVLink or DJI — TBD)                   | pending |
| 6     | Production OS (policy, geofence, auth, SBOM, ops)     | pending |

## Phase 0 — completed checklist

- [x] Plan portability: `CLAUDE.md`, `docs/plan/swarmos-roadmap.md`,
      `docs/STATUS.md`, `docs/CONVENTIONS.md`
- [x] Security docs: `SECURITY.md`, `docs/security/threat-model.md`,
      `docs/security/incident-response.md`
- [x] Data contracts: `core/swarm_core/messages.py` extended with
      Console-facing aggregates (UnitState, DockState, Sector,
      AwarenessBreakdown, MissionView, AnomalyView, Event,
      OperatorCommand, Session) + supporting enums
- [x] `core/swarm_core/voice.py` with confidence-bound copy +
      `FORBIDDEN_WORDS`
- [x] `core/swarm_core/geometry.py` extended with `sector_grid` +
      `closest_sector` + `centroid`
- [x] `backend/app/security.py` utility scaffold (CORS, headers, regex,
      rate-limit, body/timeout limits, error_response)
- [x] `backend/app/main.py` updated: CORS allowlist + security middleware +
      WS origin check + structured error handlers
- [x] `frontend/.pnpmrc`, `.nvmrc`, `frontend/.nvmrc`
- [x] `frontend/package.json` engines field + eslint-plugin-security
- [x] `frontend/next.config.mjs` security headers
- [x] `frontend/eslint.config.mjs` with security plugin rules
- [x] `docker-compose.yml` digest-pinned + container hardening
- [x] `.github/workflows/lint.yml` + `test.yml` SHA-pinned + audit step +
      `permissions: contents: read`
- [x] `.github/dependabot.yml`
- [x] `.github/workflows/dependency-review.yml`
- [x] `.github/workflows/secret-scanning.yml` (gitleaks)
- [x] `.github/workflows/codeql.yml`
- [x] `.github/workflows/sast.yml` (bandit + semgrep)
- [x] `.github/workflows/image-scan.yml` (trivy)
- [x] `.pre-commit-config.yaml`
- [x] `uv.lock` committed (92 packages locked)
- [x] `pyproject.toml` pins tightened (upper bounds) + pytest bumped to
      9.0.3+ (CVE-2025-71176 fix)
- [x] `Makefile` `audit` target (pip-audit + pnpm audit + bandit)
- [x] `README.md` security section + links to CLAUDE.md and plan
- [x] Tests added: `test_messages_v1.py`, `test_voice.py`,
      `test_geometry_sectors.py`, `backend/tests/test_security.py`
- [x] Fuzz tests scaffold under `tests/fuzz/test_messages_fuzz.py`
- [x] `make lint` (ruff + mypy) green
- [x] `make test` green: 165 passed, 16 skipped
- [x] `pip-audit --skip-editable` clean
- [x] `bandit` clean (no medium+ issues across 4 059 LOC)
- [x] Voice audit grep returns zero hits
- [x] Brand audit grep returns only allowlisted hairline/dot-glow tokens

## Open decisions

- **Phase 5 vendor choice**: MAVLink (PX4/ArduPilot) vs DJI — to be decided
  with the user when we approach Phase 5. Either is supported by the
  adapter base.
- **Phase 5 MAVLink runtime**: MAVSDK-Python is deferred until Phase 5
  because its current protobuf pin failed Phase 0 audit on 2026-05-15.
  Re-evaluate a secure MAVLink runtime before live hardware execution.
- **Phase 6 deploy target**: Kubernetes vs compose-prod — to be decided
  based on customer requirements.
- **Phase 6 auth provider**: pure JWT vs OIDC bridge — TBD; default JWT.

## Last updated

2026-05-15: Phase 0 re-verified from code on GitHub main base. Runtime
refresh applied: Node 24 LTS, pnpm 11 via Corepack, Next.js 16.2.6,
React 19.2.6, uv frozen Python install, MAVSDK/protobuf removed from the
Phase 0-4 install surface, and PostCSS audit override applied through
pnpmfile. Next: Phase 1 — SwarmOS Sim Kernel.
