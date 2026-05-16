# SwarmOS — execution status

This file tracks where we are in the
[`swarmos-roadmap.md`](plan/swarmos-roadmap.md) plan. Update it at the end
of every phase.

## Current state

| Phase | Description                                           | Status |
|-------|-------------------------------------------------------|--------|
| 0     | Repo discipline + security baseline + shared types    | **done** |
| 1     | SwarmOS Sim Kernel + endpoints + actions              | **done** |
| 2     | Console Operating Shell + routing + components        | **done** |
| 3     | Truth Layer (no DERIVED)                              | **done** |
| 4     | Persistence (Timescale + Alembic + audit)             | **done** |
| 5     | Real Adapter (MAVLink/PX4 via pymavlink)              | **in_progress** |
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

## Phase 1 — completed checklist

- [x] Added `swarm_os/` in-memory Sim Kernel:
      `state.py`, `fsm.py`, `sectors.py`, `awareness.py`, `scheduler.py`,
      `event_detector.py`, `command_bus.py`, `coordinator.py`
- [x] Added simulator projection integration at `adapters/simulator/runner.py`
- [x] Projected raw `FleetState`, `Telemetry`, `Anomaly`, and
      `MissionProgress` bus messages into Console-facing `UnitState`,
      `Sector`, `AwarenessBreakdown`, `AnomalyView`, `MissionView`, and
      typed `Event` records
- [x] Added Phase 1 REST endpoints: `/session`, `/awareness`, `/docks`,
      `/sectors`, `/units`, `/missions`, view-oriented `/anomalies`,
      filtered `/events`
- [x] Preserved legacy endpoints: `/fleet`, `/telemetry/latest`, `/events`
      fallback, and raw anomalies at `/anomalies/raw`
- [x] Added action endpoints: `/actions/verify`, `/actions/hold-patrol`,
      `/actions/dismiss`, `/actions/return`
- [x] Wired `X-Operator-Id` regex validation, per-IP/operator rate limiting,
      closed-enum `rejected_reason`, and 202 accepted command responses
- [x] Added WS dual-emission for legacy payloads plus
      `unit|dock|sector|awareness|mission|anomaly_view|event|operator`
      frames
- [x] Added targeted tests for SwarmOS mode rules, sector scoring, awareness,
      coordinator projections, command bus, snapshot endpoints, action
      validation, and 31st-call rate limiting
- [x] `make lint` green
- [x] `make test` green: 177 passed, 16 skipped; `swarm_os/` coverage ≥ 70%
- [x] `make audit` green: pip-audit clean, pnpm audit clean, Bandit no
      medium/high findings

Next: Phase 2 — Console Operating Shell. Do not start Phase 2 until the next
explicit phase request.

## Phase 2 — completed checklist

- [x] Lifted `ControlSurface` from `frontend/app/page.tsx` (314 LOC) into
      `frontend/components/TerritoryControl.tsx`; root `/` now serves the
      `(console)` route group.
- [x] Added state provider `frontend/lib/state.tsx` (`SwarmStateProvider` +
      `useSwarm()` + `useFocusAnomaly()` + `useUnit()`) wired to a single
      `SwarmSocket` + Phase 1 REST snapshots.
- [x] Added Phase 2 derivation helpers `frontend/lib/derive.ts` flagged
      `derived: true` (operating mode, verifier, primary dock, mode copy,
      anomaly copy) until Phase 3 emits the truth frames.
- [x] Extended `frontend/lib/api.ts` with all Console-facing aggregate
      types + new REST methods (`/session`, `/awareness`, `/docks`,
      `/sectors`, `/units`, `/missions`, view-oriented `/anomalies`,
      filtered `/events`, operator action posts).
- [x] Typed `frontend/lib/ws.ts` `WSMessage` union for the new kinds
      (`session|unit|dock|sector|awareness|mission|anomaly_view|event|operator`);
      LAN-aware URL resolution preserved.
- [x] Routed under `app/(console)/`: `layout.tsx` mounts provider + HeadBar
      + Footer; `page.tsx` renders `<TerritoryControl/>`; `/verify`,
      `/verify/[id]`, `/system`. Mobile under `app/m/`: `layout.tsx`,
      `page.tsx`, `[anomaly]/page.tsx`.
- [x] Added 17 new components (PDF §5.10):
      `HeadBar`, `Footer`, `RightRail`, `ActionRail`, `RiskState`,
      `NextPatrol`, `WeatherLock`, `LinkHealth`, `AnomalySummary`,
      `SectorLayer`, `RouteLayer`, `LiveFeedFrame`, `DockDetail`,
      `UnitReadiness`, `MobileAlertScreen`, `MobileAnomalyScreen`, plus
      the lifted `TerritoryControl`.
- [x] Added named inline SVG icon set `frontend/icons/index.tsx` (24px,
      stroke 1.5, round caps). No external icon kit.
- [x] `LiveFeedFrame` renders the honest `UNIT NNN VIEWPORT PENDING /
      STREAM OFFLINE` placeholder — never a stock clip.
- [x] Map overlays `SectorLayer` (sector polygons + risk band stroke) and
      `RouteLayer` (mission waypoints + observed tracks) render on the
      MapView via the children render-prop.
- [x] `ActionRail` wires `verify / hold-patrol / dismiss / return` to the
      Phase 1 action endpoints with operator-id header + outcome eyebrow.
      Advisory intents remain disabled with `intent only` copy.
- [x] WS cleanup: removed dual-emit of raw
      `telemetry|fleet|anomaly|progress` frames from `bus_consumer.py`;
      Console now reads only the projected Phase 1 frames. Legacy REST
      endpoints stay live for backwards compatibility.
- [x] Voice audit grep returns zero hits across `frontend/components` +
      `frontend/app`.
- [x] Brand audit grep returns only the design-system allowlist (inset
      highlight + state dot halos in `globals.css`).
- [x] `make lint` green: ruff + mypy + frontend `tsc --noEmit`.
- [x] `make test` green: 177 passed, 16 skipped.
- [x] `make audit` green: pip-audit clean, pnpm audit clean, Bandit no
      medium/high findings.

## Phase 3 — completed checklist

- [x] Extended `AwarenessBreakdown` to carry server-canonical `mode` +
      `verifying_agent` so the Console reads operating mode and the active
      verifier from a single truth frame. The `link_aggregate` factor is now
      part of the `factors` dict.
- [x] Added `DockState.primary` flag (server marks the canonical dock); the
      vineyard bootstrap stamps `dock-langhe-01` as primary.
- [x] Extended `OperatorCommand` with `accepted_at`, `in_flight_at`,
      `mission_id`, `ts` so the Console can render lifecycle progression.
- [x] Rewrote `swarm_os/awareness.py` to accept `mode` + `verifying_agent`
      and include them in the breakdown.
- [x] Rewrote `swarm_os/scheduler.py` with `_schedule_repatrols`: blind /
      stale sectors with confidence ≤ 0.35 get an auto-PATROL mission unless
      `state.hold_patrol` is set or another mission already covers the
      sector. Mission ids prefixed `auto-` for de-dup.
- [x] Rewrote `swarm_os/event_detector.py` as a stateful diff over
      `SwarmState`. Covers all 15 Phase 3 kinds:
      patrol_started, patrol_completed, sector_visited,
      anomaly_detected, anomaly_verifying, anomaly_verified,
      anomaly_dismissed, anomaly_escalated,
      operator_command_submitted, operator_command_completed,
      operator_command_rejected,
      dock_weather_lock, link_degraded, unit_battery_low, mission_failed.
- [x] Rewrote `swarm_os/command_bus.py` for the full lifecycle:
      `submitted → accepted → in_flight → completed | rejected | timed_out`.
      `submit()` is pure mutation; `tick()` advances commands based on the
      linked mission's phase + wall-clock deadlines. Audit log lives in
      `state.commands`. `HOLD_PATROL` flips `state.hold_patrol`.
- [x] Extended `swarm_os/coordinator.py`: `_refresh` runs scheduler +
      command tick + verifier propagation to anomalies, then the event
      detector diffs the new state. Added `apply_command()` for the action
      endpoints to use.
- [x] Promoted `COORDINATOR` to a module-level singleton in
      `swarm_os/__init__.py`; promoted `HUB` to `backend/app/hub.py`.
- [x] `backend/app/api/actions.py` now goes through `COORDINATOR.apply_command`
      and broadcasts the resulting WS frames via `HUB` — operator timeline
      updates land in the Console with no telemetry-tick delay.
- [x] Added `/commands` REST endpoint.
- [x] Frontend `derive.ts` reduced to formatting-only:
      `formatClock`, `fallbackAwareness`, `describeMode`,
      `describeAnomalyKind`, `describeBand`. The `Derived<T>`,
      `MaybeDerived<T>`, `truth`, `derived`, `deriveOperatingMode`,
      `deriveVerifier`, `pickPrimaryDock` exports are gone.
- [x] Frontend `state.tsx` exposes `mode`, `verifier`, `primaryDock` as
      plain values — read from `awareness.mode`, `awareness.verifying_agent`,
      `dock.primary`.
- [x] Removed all `· derived` eyebrow renders from `HeadBar`,
      `TerritoryControl`, `AnomalySummary`, `NextPatrol`,
      `MobileAlertScreen`, `MobileAnomalyScreen`, `WeatherLock`, and
      `verify/[id]/page.tsx`.
- [x] Added `frontend/components/CommandTimeline.tsx` to render the operator
      timeline; mounted under `ActionRail` in `TerritoryControl`.
- [x] Added `frontend/lib/api.ts` type extensions:
      `AwarenessBreakdown.mode`, `AwarenessBreakdown.verifying_agent`,
      `DockState.primary`, `OperatorCommand.{accepted_at,in_flight_at,
      mission_id,ts}`, `api.commands()`.
- [x] Added 15 Phase 3 tests in `swarm_os/tests/test_phase3.py` covering
      truth-layer assertions, scheduler, full command lifecycle,
      event detector coverage, and the no-FORBIDDEN-WORDS guarantee on
      Phase 3 event bodies.
- [x] `make lint` green: ruff + mypy 83 source files + tsc.
- [x] `make test` green: 192 passed, 16 skipped; `swarm_os/` per-module
      coverage 88-100%.
- [x] `make audit` green: pip-audit clean, pnpm audit clean, Bandit no
      medium/high (5 low) across 6 040 LOC.
- [x] Voice + brand audit greps return zero hits in product code.

## Phase 4 — completed checklist

- [x] Added SQLAlchemy ORM models in `backend/app/db/models.py` for the
      seven Phase 4 tables: `sessions`, `events`, `telemetry`, `missions`,
      `anomalies`, `operator_commands`, `sector_visits`. Portable types
      only — Timescale specifics live in the migration.
- [x] Added Alembic config (`alembic.ini`) + env (`backend/app/db/migrations/env.py`)
      + script template + initial migration
      `20260516_0001_phase4_initial.py` that creates every table and, on
      Postgres, declares `telemetry` + `events` as Timescale hypertables
      plus a 30-day retention policy on `telemetry`.
- [x] Added async session helpers in `backend/app/db/session.py`:
      `init_persistence` / `shutdown_persistence` / `get_sessionmaker`
      with SSL enforced via `connect_args={"ssl": "require"}` whenever
      `SWARM_ENV != "dev"` and the URL is Postgres.
- [x] Added async `Repository` in `backend/app/db/repository.py` with
      dialect-aware upsert (`ON CONFLICT DO UPDATE` for both Postgres and
      SQLite), best-effort writes (logged + swallowed on failure), and a
      `MAX_QUERY_LIMIT=1000` ceiling on reads.
- [x] Module-level `_REPOSITORY` swappable via `set_repository` /
      `get_repository` so tests can inject an in-memory aiosqlite engine
      and the FastAPI lifespan can install the live one.
- [x] Wired persistence into `backend/app/bus_consumer.py`: each
      Telemetry / FleetState / Anomaly / MissionProgress flowing through
      the coordinator is also persisted, plus the tail of the events
      deque (idempotent via PK upsert).
- [x] Wired persistence into `backend/app/api/actions.py`: every
      OperatorCommand (accepted + rate-limited) lands in the audit log.
- [x] Added historical endpoints in `backend/app/api/routes.py`:
      `/events?from=&to=&kind=&sector=&agent=` reads from DB when range
      is supplied, `/missions/{id}/history` returns the per-mission event
      timeline, `/operator-commands?operator_id=` returns the audit log
      (with the same `op-[a-z0-9]{4,32}` regex guard as the action
      endpoints).
- [x] FastAPI lifespan in `backend/app/main.py` calls
      `init_persistence()`, backfills the in-memory event deque with the
      last 200 rows from the DB so Console history survives a restart,
      and disposes the engine on shutdown.
- [x] `/health` now reports `persistence: bool` so the Console can render
      whether history is live.
- [x] `infra/postgres/init.sql` reduced to extension setup (`timescaledb`
      + `uuid-ossp`); Alembic owns every CREATE TABLE.
- [x] `Makefile`: added `db-migrate` (`alembic upgrade head`) +
      `db-revision`; `backend` target depends on `db-migrate` so the
      schema is current before uvicorn boots.
- [x] `scripts/dev_up.sh`: waits for Postgres, then runs Alembic before
      starting sim/backend/frontend.
- [x] Security additions: DB credentials remain env-driven
      (`${POSTGRES_USER:-swarm}` etc., no secrets in compose);
      `secrets-scanning` workflow already in place from Phase 0; SSL
      enforced via `connect_args` for prod Postgres URLs.
- [x] Added `aiosqlite>=0.20,<1` to dev deps so tests cover the full
      persistence path without a Postgres daemon (lock refreshed).
- [x] Tests: `backend/tests/test_persistence.py` (14 unit tests covering
      every `write_*` / `list_*` path, upsert dedup, time-range + filter
      semantics, limit clamp, no-op when disabled),
      `backend/tests/test_persistence_api.py` (8 endpoint tests including
      `/missions/{id}/history` SQL-injection guard with payload
      `'; DROP TABLE events;--`),
      `backend/tests/test_persistence_integration.py` (4 integration
      tests: BusConsumer → DB round-trip for telemetry + anomaly +
      events, action endpoint audit log, lifespan-style event backfill),
      `backend/tests/test_db_session.py` (6 SSL/env tests),
      `backend/tests/test_alembic_migration.py` (Alembic upgrade →
      downgrade → upgrade on sqlite to catch schema breakage in CI).
- [x] `make lint` green: ruff + mypy 95 source files + tsc.
- [x] `make test` green: 225 passed, 16 skipped (33 net new Phase 4
      tests on top of Phase 3's 192).
- [x] `make audit` green: pip-audit clean, pnpm audit clean, Bandit no
      medium/high (5 low) across 7 609 LOC.
- [x] Voice + brand audit greps return zero hits in Phase 4 product code.

## Open decisions

- **Phase 5 vendor choice**: **resolved** — MAVLink (PX4/ArduPilot) via
  `pymavlink`. DJI consumer SDK was rejected for the demo bench because
  (a) the Mobile/MSDK runtime requires Android distribution + DJI dev
  account approval, (b) the Cloud API requires a Dock/Enterprise unit
  the bench does not have, and (c) `pymavlink` is a self-contained pure-
  Python decoder that has no protobuf transitive dep — the blocker that
  ruled out MAVSDK on 2026-05-15 does not apply. The DJI stubs remain in
  the tree (`adapters/dji_psdk/`, `adapters/dji_cloud/`) for a future
  enterprise integration.
- **Phase 5 MAVLink runtime**: **resolved** — `pymavlink>=2.4.40,<3` is
  the wire-protocol library; the adapter is implemented directly on top
  of `mavutil.mavlink_connection` (no MAVSDK, no gRPC, no protobuf).
- **Phase 6 deploy target**: Kubernetes vs compose-prod — to be decided
  based on customer requirements.
- **Phase 6 auth provider**: pure JWT vs OIDC bridge — TBD; default JWT.

## Phase 4 — post-readiness fixes (2026-05-16)

A readiness audit before Phase 5 surfaced four blockers that were not caught
by the initial Phase 4 review. All fixed on
`claude/verify-phase4-completion-qiLsH`:

- [x] **Timescale-compatible `events` PK**: `EventRow` PK changed from `id`
      to composite `(id, ts)`. Timescale requires every UNIQUE / PRIMARY KEY
      index to include the partitioning column; without `ts`,
      `create_hypertable('events', 'ts', ...)` rejects with
      `cannot create a unique index without the column "ts"`. The SQLite
      test path was blind to this because hypertables are skipped on
      non-Postgres dialects. `repository.write_events` upsert key updated
      to match.
- [x] **`greenlet` declared explicitly**: `pyproject.toml` now pins
      `sqlalchemy[asyncio]>=2.0,<3`; the `asyncio` extra makes the
      `greenlet` dependency explicit instead of relying on SQLAlchemy's
      transitive resolution. `uv.lock` regenerated.
- [x] **`scripts/dev_up.sh` fail-fast on Alembic**: removed the
      `|| echo "...continuing"` mask; a broken schema now stops the boot
      instead of silently leaving the audit log dropping rows.
- [x] **Frontend lifecycle-script guard fixed**: renamed
      `frontend/.pnpmrc` → `frontend/.npmrc` (pnpm reads `.npmrc`, not
      `.pnpmrc`, so `ignore-scripts=true` was being silently ignored).
      `make setup-frontend` also explicitly passes `--ignore-scripts` as
      belt-and-suspenders.

Verification after fixes:
- `make lint` green (ruff + mypy 95 source files + tsc).
- `make test` green: 225 passed, 16 skipped.
- `make audit` green: pip-audit clean, Bandit 5 low / 0 medium / 0 high.
- Alembic upgrade on aiosqlite produces `PRIMARY KEY (id, ts)` on `events`.
- **Caveat**: real Timescale container validation could not run in this
  session (Docker Hub rate limit on `timescale/timescaledb` pull). The PK
  fix is provably correct per Timescale's documented constraint and the
  schema-level check above. CI on a clean network should run
  `alembic upgrade head` against the pinned Timescale image as the final
  gate before Phase 5.

## Phase 5 — in progress (started 2026-05-16)

Branch `claude/add-mavlink-adapter-kyTd1`. Vendor: MAVLink / PX4 via
`pymavlink`.

Planned scope (see `docs/plan/swarmos-roadmap.md` §Phase 5):
- Rewrite `adapters/mavlink/adapter.py` on top of `pymavlink` (replace
  the MAVSDK stub that was a Phase 0 blocker because of vulnerable
  protobuf pins).
- `adapters/mavlink/fake_endpoint.py`: in-process UDP MAVLink server so
  the conformance suite runs in CI with no SITL container.
- `adapters/mavlink/runner.py`: out-of-process producer symmetric to
  `sim.swarm_sim.runner`, booted from `SWARM_VENDORS=...,mavlink`.
- `core/swarm_core/streams.py`: strict `StreamDescriptor` model + URL
  allowlist (`rtsps://`, `https://` only).
- `core/swarm_core/rate_limit.py`: `TelemetryRateLimiter` (sanity Hz
  cap = 50, per Phase 5 security additions in the roadmap).
- Backend WS `stream` frame + `LiveFeedFrame` consumption.
- Mission DSL → MAVLink mapping (PATROL/VERIFY → MISSION_ITEM_INT
  upload, RTL_DOCK → `MAV_CMD_NAV_RETURN_TO_LAUNCH`, RELAY → loiter,
  COVER → reject — decomposed upstream).
- Safety enforcement: geofence pre-upload validation + heartbeat
  watchdog (link loss > 3 s → cancel + RTL).
- `docs/adapters/mavlink-setup.md`: SITL + real-radio bring-up.

Out of scope (deferred to Phase 6 or later):
- Real PX4 SITL container in CI (fake endpoint covers the contract;
  SITL is the hardware-bench acceptance gate).
- DJI Mobile / DJI Cloud adapters (stubs stay).
- Sigstore provenance check for `pymavlink` (Phase 6 supply chain).
- mTLS adapter ↔ bus (Phase 6 hardening).
- Video frame streaming via MAVLink (out of scope — video is RTSP from
  the gimbal; the adapter advertises an external URL via
  `StreamDescriptor` and `stream_video()` remains a no-op).

## Last updated

2026-05-16: Phase 5 started on branch `claude/add-mavlink-adapter-kyTd1`
(vendor decision: MAVLink/PX4 via `pymavlink`). Phase 4 post-readiness
fixes on branch `claude/verify-phase4-completion-qiLsH`. Phase 4
originally completed on branch `claude/phase-4-persistence-OGUJm`.
Phase 2 was completed on branch `claude/phase-2-start-CMUg1`. Phase 1
was completed at GitHub main commit
`2390f872908a4a52588287a3865b3da96c785750`.
