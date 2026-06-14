# SwarmOS — execution status

This file tracks where we are in the
[`swarmos-roadmap.md`](plan/swarmos-roadmap.md) plan. Update it at the end
of every phase.

Phase 7+ execution order is now in
[`swarm-roadmap-evidence-to-scale.md`](plan/swarm-roadmap-evidence-to-scale.md).
It replaces the older "all sim software before field/market proof" draft
for current execution.

## Current state

| Phase | Description                                           | Status |
|-------|-------------------------------------------------------|--------|
| 0     | Repo discipline + security baseline + shared types    | **done** |
| 1     | SwarmOS Sim Kernel + endpoints + actions              | **done** |
| 2     | Console Operating Shell + routing + components        | **done** |
| 3     | Truth Layer (no DERIVED)                              | **done** |
| 4     | Persistence (Timescale + Alembic + audit)             | **done** |
| 5     | Real Adapter (MAVLink/PX4 via pymavlink)              | **CI-ready; SITL attempted/not validated; hardware pending** |
| 6     | Production OS (policy, geofence, auth, SBOM, ops)     | **done** — 6.A/6.B/6.C/6.D/6.E/6.F/6.G/6.H/6.I/6.J all complete |
| 7     | Software MVP base in simulazione (3 scenari + autonomy baseline + CV) | **done** — 7.A done (scenarios + loader); 7.B done (autonomy baseline kernel + scenario opt-in); 7.C done (Console AUTO eyebrow + autonomy chip + persistence); 7.D done (CV baseline opt-in via `sim/swarm_sim/cv/` + manifest + fixtures + integrity gate); 7.E code-complete (`make demo-{wildfire,intrusion,search}-sim` + baseline metrics collector); 7.F code-complete (DS Spread 24 + Plain Voice v1 + AUTO marker on viewport callout + RecentSection); 7.G manual end-to-end gate green on Python 3.13 (lint/test/audit clean: 726 passed/19 skipped; demo wildfire boot evidence + 5 desktop + 2 mobile screenshots in `docs/yc/screenshots/`; a11y sweep report in `docs/yc/m1-a11y-report.md`; pitch VO script in `docs/yc/m1-vo-script.md`); **WS1 (2026-05-29) closed the live verify-loop** — `apply_mission_progress(DONE)` promotes VERIFYING→VERIFIED so R2 auto-ESCALATE fires on the wildfire FIRE follow-up (`by_rule.R2==1`), and AUTO attribution persists past command completion (`findLatestAutonomyCommand`); `make lint/test/audit` green (751 py / 61 fe). **WS2 (2026-05-31)** added the honest in-Console autonomy metrics surface (`frontend/lib/metrics.ts` mirroring `scripts/scenario_metrics.py` + `AutonomyMetrics.tsx` in QuietPanel, CSS/SVG-only, every readout `(sim)`, no red) and parametrized `scripts/m1_capture_screenshots.py` by `--scenario {wildfire,intrusion,search}` (intrusion/search = standby/R1-verify/VERIFIED, operator-owns-escalation); `pnpm test` 86 fe passed (metrics.ts 100% lines). The 3-scenario live capture + `phase-7e-{intrusion,search}` metrics artifacts and the `.mov` screen-recording (plan §1f) remain the same manual founder-machine step. |
| 8     | Wedge + customer validation | **next** — run discovery before broadening software scope |
| 9     | PX4/SITL + hardware bench de-risk | **next in parallel after Phase 7 demo** — Phase 5 hardware claim remains pending |
| 10    | Summer evidence pack + BIEF/YC future-batch decision | **planned** — YC Summer 2026 is not the target |

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
- **Phase 6 deploy target**: **resolved** — both paths shipped in Phase
  6.E. `docker-compose.prod.yml` for single-node bench/customer-pilot
  deploys, Helm chart at `infra/helm/swarmos/` for Kubernetes. The
  per-customer choice is documented in `docs/ops/deploy.md`; the repo no
  longer pre-decides one over the other.
- **Phase 6 auth provider**: **resolved** — pure JWT HS256 (Phase 6.C);
  OIDC bridge deferred to Phase 6.E as an optional addition when a
  customer needs SSO. See [`docs/security/auth.md`](security/auth.md).

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

## Phase 5 — CI-ready; bench validation still pending

Vendor: MAVLink / PX4 via `pymavlink`. Branch
`codex/phase5-bench-security-gates`.

- [x] Rewrote `adapters/mavlink/adapter.py` on top of `pymavlink` (no
      protobuf, no gRPC, no MAVSDK). Adapter speaks
      MAVLink wire protocol directly via `mavutil.mavlink_connection`.
- [x] Hardened lifecycle and protocol readiness: `connect()` now fails
      closed unless a non-GCS HEARTBEAT arrives before timeout; failed
      connects disconnect/cleanup and raise `MAVLinkConnectionError`.
      `health()` reports `link_quality=0.0` until a real heartbeat exists.
- [x] Implemented real mission upload handshake:
      `MISSION_COUNT` → wait for `MISSION_REQUEST_INT` / `MISSION_REQUEST`
      → send only the requested item → tolerate duplicate requests
      idempotently → require final `MISSION_ACK(MAV_MISSION_ACCEPTED)`.
      Missing or rejected ACKs raise adapter-specific errors.
- [x] `COMMAND_LONG` now requires the matching `COMMAND_ACK` and raises
      on timeout or non-accepted result. `set_safety()` verifies fence
      enable through ACK and parameter writes through `PARAM_VALUE`.
      `SET_MODE(AUTO.MISSION)` waits for a matching HEARTBEAT before
      mission start, and mission start itself requires `COMMAND_ACK`.
- [x] `request_capture()` no longer fabricates synthetic `mavlink://...`
      URIs. It returns the configured allowlisted `MAVLINK_STREAM_URL` as
      the capture/stream reference, or raises `MAVLinkCaptureUnavailable`
      when no real stream is configured.
- [x] `adapters/mavlink/fake_endpoint.py`: in-process UDP MAVLink
      server that pretends to be a PX4 autopilot. Emits HEARTBEAT (1
      Hz), GLOBAL_POSITION_INT (10 Hz), SYS_STATUS (1 Hz); enforces the
      real mission request loop, duplicates the first request to catch
      blind item streaming, rejects out-of-order items, can withhold or
      reject final ACKs for negative tests, verifies COMMAND_ACK and
      PARAM_VALUE behavior, and auto-advances MISSION_CURRENT after
      accepted MISSION_START. No PX4 SITL / Gazebo required for CI.
- [x] `adapters/mavlink/runner.py`: in-process backend runner for Phase 5
      dev/demo boot, with a standalone `python -m adapters.mavlink.runner`
      entrypoint kept for bench debugging. Publishes `swarm:telemetry:<aid>`,
      `swarm:fleet:state`, `swarm:streams:<aid>`. Env-driven config
      (`MAVLINK_CONNECTION`, `MAVLINK_AGENT_ID`, `MAVLINK_MODEL`,
      `MAVLINK_STREAM_URL`, `MAVLINK_RATE_LIMIT_HZ`).
- [x] `core/swarm_core/streams.py`: strict `StreamDescriptor` model +
      URL allowlist enforcement (`rtsps://`, `https://` only). Rejects
      `http`, `rtsp`, `rtmp`, `file`, `javascript`, `data`, CRLF/NUL
      injection. `available=False` forbids carrying a URL or protocol
      (no ambiguous descriptors).
- [x] `core/swarm_core/rate_limit.py`: `TelemetryRateLimiter` per-agent
      sliding-window cap (default 50 Hz, the roadmap pin).
- [x] `backend/app/bus_consumer.py`: backend-side telemetry sanity cap
      using the same per-agent limiter, so a malicious or buggy adapter
      cannot bypass rate limiting by publishing directly to `swarm:*`.
- [x] `backend/app/fleet.py`: `SWARM_VENDORS` env parsing
      (case-insensitive, dedup, unknown vendors fail-fast via
      `UnknownVendor`). Requested in-process vendor boot failures now
      raise `VendorBootError`; `SWARM_VENDORS=mavlink` and
      `SWARM_VENDORS=simulator,mavlink` fail fast if MAVLink cannot boot.
      The simulator runs as its own subprocess.
- [x] Backend WS `stream` frame: `BusConsumer._consume_streams`
      subscribes to `swarm:streams:*`, re-validates the URL allowlist
      (defense in depth), stores the descriptor on `SwarmState.streams`
      and broadcasts `{"kind":"stream"}` to every WS client. Snapshot
      frames include streams for reconnects.
- [x] Frontend: `lib/api.ts` adds `StreamDescriptor` + client allowlist
      `isAllowedStreamUrl`; `lib/ws.ts` adds the `stream` kind;
      `lib/state.tsx` maintains `streams: Record<agent_id,
      StreamDescriptor>`; `components/LiveFeedFrame.tsx` renders a real
      `<video>` element when the descriptor is `available` and the URL
      passes the allowlist, otherwise the honest viewport placard. The
      `/verify/[id]` page threads the verifier's descriptor through.
- [x] Mission DSL → MAVLink mapping: PATROL/VERIFY upload via
      `MISSION_COUNT`, requested-only `MISSION_ITEM_INT` /
      `MISSION_ITEM`, final accepted `MISSION_ACK`, then
      `SET_MODE(AUTO.MISSION)` + `MAV_CMD_MISSION_START`; RTL_DOCK →
      `MAV_CMD_NAV_RETURN_TO_LAUNCH`; RELAY →
      `MAV_CMD_NAV_LOITER_UNLIM`; COVER → `UnsupportedMission`.
- [x] Safety enforcement: `set_safety` uploads FENCE_POINTs +
      `DO_FENCE_ENABLE`, writes `BAT_LOW_THR` / `MIS_TAKEOFF_ALT`.
      Defense-in-depth: every waypoint is geofence + max-alt checked
      before upload; rejected missions raise `RejectedMission` and
      never reach the wire. Heartbeat watchdog: HEARTBEAT absence > 3 s
      collapses `link_quality` to 0 and marks any active mission
      cancelled so the mission loop fails closed into RTL.
- [x] `docs/adapters/mavlink-setup.md`: PX4 SITL bring-up,
      real-hardware checklist (Holybro X500 / 3DR Quad Zero, SiK
      radio), firmware params (SYS_AUTOSTART, BAT_*, MIS_*, GF_*),
      `MAVLINK_STREAM_URL` allowlist note, troubleshooting.
- [x] `scripts/dev_up.sh`: honors `SWARM_VENDORS`; the simulator
      subprocess is launched only when `simulator` is in the list, so
      `SWARM_VENDORS=mavlink` boots a MAVLink-only fleet.

### CI verification on this branch

Gate run from this branch on 2026-05-16:

```
$ make lint   # green: ruff + mypy over 110 source files + frontend tsc
$ make test   # green: 341 passed, 16 skipped; frontend tsc
$ make audit  # green: pip-audit clean, pnpm audit clean, Bandit 0 medium/high,
              # pymavlink integrity gate passed offline
```

The conformance suite (`AdapterConformanceTests`) runs against the
MAVLink adapter wired to the strict `FakeMAVLinkEndpoint`. Phase 5 CI
coverage now includes:

- no-endpoint and no-heartbeat connect failure;
- request/response mission upload, duplicate requests, timeout, and
  rejected final `MISSION_ACK`;
- missing/rejected `COMMAND_ACK`;
- fence enable ACK and `PARAM_VALUE` confirmation;
- honest capture behavior with and without `MAVLINK_STREAM_URL`;
- MAVLink-only and mixed-vendor boot failure;
- backend-side telemetry rate limiting;
- strict stream URL allowlist and frontend offline viewport behavior.

No MAVSDK, gRPC, or Python protobuf dependency is present in the Python
lockfile; `pymavlink` remains the only MAVLink runtime dependency.

### Phase 5 readiness gates and Phase 6 entry criteria

- Real PX4 SITL is **not validated** on this branch. The local environment
  had no PX4 install and no HEARTBEAT on `udp:localhost:14540`; the probe
  artifact is `docs/bench/artifacts/2026-05-16-sitl-probe.json`, and the
  evidence note is `docs/bench/phase5-validation.md`. Do not claim SITL
  validation until the checklist in `docs/adapters/mavlink-setup.md`
  passes for the exact commit.
- Real hardware is **not validated**. No USB/radio PX4 device was available
  in this environment. Hardware remains pending until the bench checklist
  has command output or clear artifacts for the exact commit.
- `pymavlink` package integrity is now an enforced local/CI gate:
  `make audit` runs `scripts/verify_pymavlink_integrity.py`, which verifies
  the `uv.lock` PyPI artifact hashes, the `pyproject.toml` optional extra,
  the installed version, and 195 installed wheel `RECORD` sha256 entries
  without network access. Outside scope: publisher identity and Sigstore
  signing certificates, which require an upstream attestation policy before
  production.
- Secure adapter-bus transport now fails closed for Phase 6/prod entry:
  `SWARM_ENV=prod` or `SWARM_REQUIRE_SECURE_BUS=1` requires `REDIS_URL` to
  use `rediss://` plus existing `REDIS_TLS_CA_CERTS`,
  `REDIS_TLS_CERTFILE`, and `REDIS_TLS_KEYFILE` files. In secure mode the
  backend, simulator runner, and standalone MAVLink runner refuse the
  `InMemoryBus` fallback if Redis is missing or insecure. Phase 6 owner:
  Platform/SRE must provision the Redis mTLS service, client cert rotation,
  and deployment secret mounts before production/out-of-process adapters are
  allowed.
- Telemetry rate limiting is no longer deferred at the Phase 5 boundary:
  both adapter-side and backend-side caps are implemented and tested.
- DJI Mobile / DJI Cloud adapters remain stubs in `adapters/dji_*` for a
  future enterprise integration.
- Video frame streaming **via MAVLink** remains out of scope. Video is on
  its own RTSPS / HLS pipe; the adapter advertises the URL via
  `StreamDescriptor`, `request_capture()` returns only a real configured
  stream URI, and `stream_video()` remains a no-op.

### Bench validation (attempted; pending — not claimed)

PX4 SITL was attempted with the repo probe, but it did not validate because
no PX4 endpoint emitted HEARTBEAT on `udp:localhost:14540` in this
environment. Hardware validation was not run. Current evidence lives in
`docs/bench/phase5-validation.md` and
`docs/bench/artifacts/2026-05-16-sitl-probe.json`.

Before calling Phase 5 bench-validated, run the acceptance checklist in
`docs/adapters/mavlink-setup.md`:

1. PX4 SITL emits HEARTBEAT on UDP 14540 and SwarmOS boots with
   `SWARM_VENDORS=mavlink MAVLINK_CONNECTION=udp:localhost:14540`.
2. Fleet and telemetry frames appear on Redis with `link_quality > 0`.
3. VERIFY mission upload shows requested-only `MISSION_ITEM_INT` frames
   and final accepted `MISSION_ACK`.
4. Arm, mission start, RTL, fence enable, and param writes have ACK/value
   evidence in PX4/QGroundControl logs.
5. Console remains honest: offline viewport with no stream URL, real
   `<video>` only for allowlisted `https://` / `rtsps://` stream URL.

## Phase 6 — in_progress

Branch: `claude/phase-6-production-os`. Strategy: deliver every Phase 6
block in code form so the system is "code-complete to Phase 6" before the
hardware arrives. The hardware-day actions (real PX4 SITL, real radio,
real weather API keys, signing keys, TLS domain, customer acceptance) are
catalogued in [`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md)
and flipped on the day the drones are acquired.

Sub-block progress:

- [x] **6.A** Safety policy engine (geofence runtime, battery + link
      thresholds, weather lock stub, mission priority) — **done**.
      `swarm_os/policy.py` is the side-effect-free decision point;
      `swarm_os/safety.py` carries thresholds, `PolicyDecision`,
      `SafetyAction`, the `WeatherProvider` Protocol, and the
      `LocalStubWeatherProvider`. `swarm_os/sites.py` loads
      `infra/config/sites/<site_id>.yaml` (with an in-code fallback
      for the legacy vineyard-01 site). Wired through scheduler
      (auto-PATROL gated), command bus (operator VERIFY/RETURN
      validated against geofence + thresholds + weather), and
      coordinator (auto-RTL queued on low battery / low link; dock
      `weather_lock` refreshed from the provider). 53 new tests across
      geometry (8), safety + sites (14), policy unit (21), and
      Phase 6.A integration (11). Real-provider integration
      (OpenWeather, Aviationweather), NOTAM/NFZ feed, and TLS-bound
      live tests are catalogued in
      [`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md)
      §2.A/§2.B and remain pending until the drones and external
      assets arrive.
- [x] **6.B** Multi-site + runtime config — **done**.
      `SwarmState.from_site_config(site_config)` factory builds a
      site-aware state (session.site_id, policy, sector grid centre,
      docks all derive from the config); `SwarmState.vineyard()` is now
      a backward-compatible wrapper that reads `SWARM_SITE_ID` from the
      env. Hot reload via `POST /admin/reload-site-config` swaps the
      SiteConfig + PolicyEngine on the live state under
      `state.lock`, preserves the existing WeatherProvider binding
      (so production providers survive reloads), appends a `system`
      Event to the audit log, and broadcasts it on the WS hub.
      Transitional `X-Admin-Token` header gate (env var
      `SWARM_ADMIN_TOKEN`) — replaced by JWT commander scope in 6.C.
      Out of scope this block: simultaneous multi-site multiplexing
      in one instance (one site at a time is what the demo + bench
      need; multi-site multiplexing is a Phase 7 concern, recorded in
      [`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md));
      `patrol_cadence_s` / `allowed_mission_kinds` / `operator_allowlist`
      schema fields (deferred to 6.C where the RBAC model lives).
      19 new tests across site-aware factory (10) and admin endpoint
      (9). Full suite still green: 414 passed, 16 skipped.
- [x] **6.C** Operator auth + RBAC + MFA — **done**.
      Pure JWT HS256 (no OIDC bridge): 15 min access, 8 h refresh,
      rotation on every refresh, all via `pyjwt>=2.8` (now pinned
      explicitly in `pyproject.toml`). Three-role hierarchy
      `viewer < operator < commander` enforced server-side by
      `require_role` FastAPI dependencies — viewer gates every GET,
      operator gates `/actions/*`, commander+MFA gates `/admin/*`.
      The transitional `X-Operator-Id` header gate and the 6.B
      `X-Admin-Token` shim were both retired; the operator identity
      rides on the JWT `sub`. MFA via TOTP (RFC 6238, stdlib hmac +
      hashlib; no third-party MFA library) is mandatory for the
      commander role at login and the `mfa=true` claim is
      re-checked on every commander endpoint so a stolen non-MFA
      token can't be elevated. Password hashes use PBKDF2-HMAC-SHA256
      with 600 000 iterations (OWASP 2023). The operator identity
      store is a strictly-validated YAML on disk
      (`infra/config/operators.yaml`, gitignored, env override
      `SWARM_OPERATORS_CONFIG`). Revocation list is in-process today
      (Redis-backed swap deferred to 6.E with the secure-bus
      rollout); refresh rotation revokes the spent JTI immediately,
      so a leaked refresh can't be replayed. WebSocket upgrade
      requires a valid access token via `?token=` query (default for
      the Console) or `Sec-WebSocket-Protocol: bearer, <jwt>`.
      Auth audit lands as `system` events on every login (success +
      failure), refresh, logout, and revocation — broadcast on WS,
      persisted via the bus consumer.
      Backend surface: `backend/app/auth/` package (passwords, mfa,
      store, jwt, revocation, deps, audit, ws_auth, cli) +
      `backend/app/api/auth_routes.py` (`/auth/login`,
      `/auth/refresh`, `/auth/logout`, `/auth/me`). Frontend:
      `lib/auth.tsx` (AuthProvider + token storage + silent
      refresh), `components/AuthGate.tsx` (redirect when
      anonymous), `app/login/page.tsx` (minimal design-system login
      page with optional TOTP field), Authorization header on every
      REST call and `?token=` on the WS upgrade. CLI helpers:
      `python -m backend.app.auth.cli hash-password|new-mfa|verify`.
      Hardware-day actions (JWT secret provisioning, MFA enrolment,
      optional OIDC bridge, HttpOnly cookie pipe for refresh,
      Redis-backed revocation, pen-test) are catalogued in
      [`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md)
      §2.C; design + runbook in
      [`docs/security/auth.md`](security/auth.md).
      97 new tests across `test_auth_passwords.py` (10),
      `test_auth_mfa.py` (10), `test_auth_jwt.py` (14),
      `test_auth_store.py` (14), `test_auth_revocation.py` (7),
      `test_auth_routes.py` (21), `test_rbac.py` (16),
      `test_ws_auth.py` (5), plus migrations of the Phase 1 / 4 /
      6.B test files onto the JWT auth fixtures. Full suite: 514
      passed, 16 skipped.
- [x] **6.D** Observability stack — **done**.
      Prometheus exposition on a private `CollectorRegistry`
      (`backend/app/observability/metrics.py`) covering the roadmap
      minimum: `swarm_units_online` (Gauge), `swarm_anomalies_pending`
      (Gauge), `swarm_actions_total{action,outcome}` (Counter),
      `swarm_ws_clients` (Gauge), `swarm_mission_duration_seconds`
      (Histogram), `swarm_http_request_duration_seconds{route,method,status}`
      (Histogram), plus a `swarm_auth_failures_total{reason}` counter
      wired from `backend/app/api/auth_routes.py`. `/metrics` is
      gated by `require_commander` by default with an optional
      `SWARM_METRICS_IP_ALLOWLIST` (comma-separated CIDR list) for
      in-cluster Prometheus scrapers. `prometheus-client>=0.20,<1`
      is pinned explicitly in `pyproject.toml` and locked.
      Structured JSON logs via structlog: `configure_logging()` wires
      a `ProcessorFormatter` so stdlib + native structlog both emit
      JSON to stdout, with a redactor processor in the chain that
      scrubs sensitive keys (`password`, `totp`, `mfa_secret`,
      `refresh_token`, `access_token`, `authorization`, `cookie`,
      `api_key`, `private_key`, …) and strips JWT-like substrings.
      `RequestIDMiddleware` mints / validates `X-Request-ID`,
      propagates it to the response header, and binds it to the
      structlog context so every log line within the request carries
      the id. `RequestLatencyMiddleware` populates the latency
      histogram with `(route, method, status)` labels via the
      FastAPI route template (bounded cardinality).
      `/ready` is a new public endpoint with active probes for DB
      (`SELECT 1` on the repository sessionmaker), Redis (`PING` on
      the bus client; in-memory bus is treated as `ok`), and the
      auth singletons. 200 with `{"status":"ready","checks":{db,redis,auth}=ok}`
      or 503 `degraded` with the failing subsystem flagged `down`.
      No stack traces in the payload.
      OpenTelemetry tracing is shipped as an optional extra
      (`pyproject.toml` `[project.optional-dependencies.otel]`,
      not pulled by default). `backend/app/observability/tracing.py`
      reads `SWARM_OTLP_ENDPOINT` and no-ops if absent or if the
      extra wasn't installed — keeping the audit surface flat for
      the default deploy.
      Dashboards + alerts: `infra/grafana/dashboards/swarmos-overview.json`
      (units online, anomalies pending, REST p95, actions/sec, WS
      clients, auth failures, REST latency by route);
      `infra/grafana/alerts.yml` with rules for units offline,
      anomaly backlog, link health < 0.5, auth failure rate, dock
      weather lock long, REST latency p95, and readiness probe
      failing. No red severity band (design system §5.2 — amber for
      escalation).
      Migrated logger usage to structlog at the key wired points:
      `main.py`, `bus_consumer.py`, `auth/jwt.py`, `auth/store.py`,
      `api/auth_routes.py`, `api/admin.py`, `ws/telemetry.py`. The
      rest of the codebase continues to use stdlib `logging` and
      lands in the JSON formatter via the `ProcessorFormatter`
      foreign chain — no migration needed.
      27 new tests across `backend/tests/test_metrics.py` (9),
      `backend/tests/test_ready.py` (7), `backend/tests/test_request_id.py`
      (6), `backend/tests/test_structlog_redaction.py` (5).
      Full suite: **541 passed, 16 skipped** (vs Phase 6.C
      baseline 514 / 16). `make lint` green (ruff + mypy 149 files
      + tsc), `make audit` green (pip-audit clean, pnpm audit clean,
      Bandit 0 medium/high, pymavlink integrity PASS). Design note +
      runbook in [`docs/observability/overview.md`](observability/overview.md);
      drone-day deploy items in
      [`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md)
      §2.D.
- [x] **6.E** Deployment + infra-as-code — **done** (code-complete).
      Container images for backend, frontend, and backup, all
      multi-stage, digest-pinned, non-root (uid 10001 / 1001), and
      read-only-rootfs-compatible (`backend/Dockerfile`,
      `frontend/Dockerfile`, `infra/backup/Dockerfile`). `frontend/next.config.mjs`
      switched to `output: "standalone"` so the runtime stage carries
      only `.next/standalone` + `.next/static` + `public/`. Root
      `.dockerignore` keeps secrets, `.venv`, `node_modules`, IaC
      dirs, and tests out of every build context.
      Single-node production deploy via `docker-compose.prod.yml`:
      pg + redis + backend + frontend + nginx TLS terminator
      (`infra/proxy/nginx.conf` + `entrypoint.sh`) + Let's Encrypt
      certbot sidecar (`infra/proxy/certbot/renew.sh`, SIGHUP reload
      via shared pid namespace, no docker socket exposed) + backup
      sidecar. `TLS_MODE=self-signed` escape hatch keeps `make demo`-
      style boots interactive on a bench without ACME. Hardening
      posture mirrors `docker-compose.yml`: no-new-privileges,
      `cap_drop: [ALL]` + minimal `cap_add` for nginx, mem/cpu limits,
      read-only rootfs with tmpfs writes.
      Kubernetes raw manifests under `infra/k8s/` and a parameterised
      Helm chart at `infra/helm/swarmos/` (Chart.yaml + values.yaml +
      `values-vineyard-01.yaml` overlay + 11 templates). Both deploy
      paths emit Deployment + Service + Ingress (ingress-nginx +
      cert-manager) + Secret + ConfigMap + HPA (2..10 on CPU 70% /
      mem 75%) + NetworkPolicy (default-deny + explicit allows for
      kube-system probes, ingress-nginx, Prometheus, Postgres, Redis,
      and outbound 443 for weather/OTLP) + Pod Security Standards
      `restricted` namespace + CronJob `pg_dump | gpg` daily backup
      with 30-day retention. ServiceMonitor + Grafana
      datasource provisioning closes the 6.D drone-day items.
      cert-manager ClusterIssuers for Let's Encrypt staging + prod
      under `infra/cert-manager/`.
      CI: `.github/workflows/image-build.yml` builds backend +
      frontend + backup on every PR/branch push, with Trivy now a
      **blocking** gate (`exit-code: "1"` for HIGH/CRITICAL, owns
      the published images per the plan's graduation from Phase 0's
      report-only posture). On `v*` tag pushes the images are
      published to GHCR with SBOM + provenance attestations.
      `.github/workflows/image-sign.yml` signs each pushed image via
      `cosign sign --yes` keyless OIDC against Sigstore (drone-day
      §2.E binds the real identity). Both workflows use SHA-pinned
      external actions per the security baseline.
      Backup pipeline: `scripts/backup_postgres.sh` (`pg_dump | gpg
      --encrypt`, retention-pruning, fingerprint check, no plaintext
      intermediate); `scripts/restore_postgres.sh` requires
      `--i-understand-this-overwrites` to prevent foot-guns. The
      script is mirrored byte-for-byte in
      `infra/helm/swarmos/files/backup_postgres.sh` so the CronJob's
      ConfigMap and the local `make` target stay in sync (test
      enforces parity).
      Docs: `docs/ops/deploy.md` (topology, image build/sign, k8s
      Helm install, compose-prod boot, canary via Helm rolling +
      `helm rollback`); `docs/ops/migrations.md` (additive-first
      rules, Job-based prod migrations, Timescale gotchas, restore
      drill). `docs/ops/drone-day-checklist.md` §2.E expanded with
      every remaining external asset (DNS, real Let's Encrypt prod,
      GHCR creds, Sigstore identity, image-pull secret,
      NetworkPolicy CNI, StorageClass, GPG recipient, off-site
      sync, quarterly restore drill, Grafana datasource URL,
      HttpOnly cookie pipe, Redis mTLS material).
      Makefile: `docker-build` / `helm-template` / `helm-lint` /
      `backup-dump-dry` targets. `docker-compose.yml` carries an
      inline note pointing at the production paths. README §Quickstart
      gains a one-liner linking `docs/ops/deploy.md`.
      14 new tests in `tests/test_phase6e_deploy.py`: chart metadata,
      template completeness, values-key reference closure, overlay-
      key sanity, raw k8s manifest parse, Pod Security Standards
      assertions, compose-prod digest pinning, backup-script byte-
      identity, restore-script guard flag, Dockerfile digest pinning,
      Dockerfile non-root, CI workflow SHA pinning. Full suite:
      555 passed, 16 skipped (vs Phase 6.D baseline 541 / 16).
      `make lint` green (ruff + mypy 149 files + tsc), `make audit`
      green (pip-audit clean, pnpm audit clean, Bandit 0 medium/high,
      pymavlink integrity PASS). Voice + brand audit greps return
      zero hits in product code + new docs.
      **Caveat (drone-day)**: this branch did not run `docker build`
      end-to-end or `helm template` against a real cluster — the
      execution container has no docker daemon and no helm/kubectl
      binary. The smoke test in `tests/test_phase6e_deploy.py`
      validates the offline-checkable invariants; CI on a clean
      runner is the gate before the first production deploy.
- [x] **6.F** Performance + scale — **done** (code-complete).
      In-process p95 smoke (`tests/load/test_load_inproc.py`): a real
      `BusConsumer` + `InMemoryBus` + `WSHub` driven by 50 agents at
      1 Hz × 5 s. Three assertions cover the SLO: `unit` frame p95
      < 200 ms, REST p95 < 100 ms across `/awareness`, `/units`,
      `/anomalies`, `/missions` with 0 × 5xx, and a 200-unit burst that
      exercises the `TelemetryRateLimiter` (`dropped_total` must
      advance + the consumer must never raise). Each marked
      `@pytest.mark.load_smoke` — `make load-smoke` runs the trio in
      ~13 s.
      Out-of-process driver (`tests/load/driver.py`,
      `python -m tests.load.driver` / `make load-soak`) auths via
      `POST /auth/login`, publishes telemetry through Redis at the
      configured rate, opens N WS subscribers, and pounds REST.
      Writes `tests/load/results/last.json` with p50/p95/p99 and
      publish/receipt counts; exits non-zero on any breach.
      Chaos drills shipped as runnable scripts (not in `make test`):
      `scripts/chaos/redis_pause.sh` pauses Redis for 8 s, asserts 0
      `/health` failures; `scripts/chaos/backend_kill.sh` SIGTERMs
      uvicorn, restarts it, and asserts the WS reconnect via
      `tests.chaos.ws_probe` lands within 6 s.
      CI: a new `load-smoke` job in `.github/workflows/test.yml` runs
      the in-process smoke on every push, plus a weekly soak
      (`.github/workflows/load-test.yml`, schedule
      `17 4 * * 1`, also `workflow_dispatch`) that boots Timescale +
      Redis as service containers, runs `bootstrap-auth-dev`,
      starts the backend, then drives 500 msg/s × 5 min and uploads
      the results JSON for triage. Every external action is
      SHA-pinned. No new dependencies (`httpx`, `websockets`, `redis`
      are already core deps). Documentation in
      `docs/ops/performance.md`. Plan: `docs/plan/phase-6f.md`.
      **Caveat**: in this execution environment we ran only the
      in-process smoke (3/3 passing in 13 s, full suite still
      558 passed / 16 skipped). The chaos scripts depend on Docker
      Compose and a running backend — they're code-complete and
      ready for the dev stack; the gate before flipping 6.G is a
      manual `make chaos-redis` + `make chaos-backend` run plus one
      successful weekly `load-test` workflow run.
- [x] **6.G** Resilience + DR — **done** (code-complete).
      Fleet-wide emergency stop intent `EMERGENCY_RTL_ALL`: extended
      `core/swarm_core/messages.OperatorAction`, taught
      `swarm_os/command_bus.py` to dispatch one priority-200
      `RTL_DOCK` mission per airborne unit (skipping `DOCKED` /
      `OFFLINE` / `ERROR`), force-fail any conflicting non-RTL
      missions on those units, pin `state.hold_patrol=True`, and
      stamp `state.emergency_active_at`. Coordinator suppresses the
      auto-RTL safety action for units already carrying an emergency
      mission so the audit log can't double-count the event.
      Backend endpoint `POST /actions/emergency-rtl-all` gated by
      `require_commander` (re-checks the `mfa=true` claim on every
      call); body is a strict `EmergencyRtlAllBody` with
      `confirm: Literal[True]` + a literal phrase
      `RETURN ALL UNITS`; dedicated 1/min/operator `RateLimiter`;
      rejection still audited; SYSTEM event "emergency rtl all
      triggered by op-xxx · N unit(s) returning · safety policy
      bypassed" appended + WS-broadcast; metric
      `swarm_actions_total{action="emergency_rtl_all",outcome=...}`
      labelled. Safety policy gate intentionally bypassed for the
      emergency intent (a low battery is *why* we're stopping) and
      the bypass is recorded in the audit event.
      Frontend: `lib/api.ts` adds `emergency_rtl_all` to
      `OperatorAction`, ships `api.emergencyRtlAll(phrase)` +
      exported `EMERGENCY_CONFIRMATION_PHRASE`; new component
      `components/EmergencyStop.tsx` (Launch Amber, no red, no
      external modal library) mounted in `HeadBar` between the
      pending pill and the operator badge; commander-only,
      two-stage inline confirmation (typed phrase must match),
      Esc-to-close, auto-reset after a terminal outcome,
      `CommandTimeline` label updated.
      DR runbook `docs/ops/disaster-recovery.md` (RTO 1 h / RPO
      5 min table, scenarios S1..S5, drill cadence, emergency
      stop reference). Failover *patterns* shipped as reference
      configs only — `infra/redis/sentinel-example.yaml` (3
      sentinels, quorum 2, mTLS, amber-only alerts) and
      `infra/postgres/patroni-example.yaml` (3 nodes, ETCD,
      WAL archive, async streaming, amber-only alerts). Monthly
      backup drill at `scripts/backup_restore_drill.sh`
      (`make backup-drill`): sidecar Postgres, reuses Phase 6.E
      `backup_postgres.sh` + `restore_postgres.sh` byte-for-byte
      so the drill matches prod, asserts Alembic head + audit row
      counts, exit code is the drill PASS/FAIL. Drone-day items
      catalogued in `docs/ops/drone-day-checklist.md` §2.G (real
      Sentinel cluster, real Patroni / managed-RDS replica, WAL
      archive, off-site backup sync, monthly drill cadence,
      quarterly DR-site failover rehearsal, GPG recipient rotation,
      pen-test of the emergency stop endpoint, runbook handover).
      32 new tests across `swarm_os/tests/test_phase6_emergency.py`
      (8: target validation, RTL-per-airborne-unit, safety bypass,
      hold_patrol + timestamp side-effects, scheduler halts,
      conflicting missions force-failed, idempotency,
      auto-RTL suppression),
      `backend/tests/test_emergency_rtl.py` (14: anonymous → 401,
      viewer/operator/no-MFA commander → 403, body shape
      validation, wrong/missing phrase → 400, extra fields → 422,
      happy path dispatch, audit event body, WS broadcast via the
      hub, 1/min rate limiter, metrics increment, voice-clean
      audit body), `tests/test_phase6g_dr.py` (10: DR runbook
      sections + cross-links, Sentinel/Patroni YAML parse + HA
      shape + amber-only alerts, drill script `set -eu` + guard
      flag, Makefile target, endpoint registered + commander dep,
      enum + canonical-target constants, emergency priority above
      auto-RTL). Full suite: **580 passed, 16 skipped** (vs Phase
      6.F baseline 558 / 16). `make lint` green (ruff + mypy 151
      files + tsc), `make audit` green (pip-audit clean, pnpm
      audit clean, Bandit 0 medium/high, pymavlink integrity
      PASS). Voice + brand audit greps return zero hits in
      product code + new docs + new infra example configs.
- [x] 6.H Documentation — done (2026-05-18). Added docs/architecture/overview.md, docs/api/openapi.yaml, docs/api/ws-contract.md, docs/operator/manual.md, docs/operator/training.md, docs/ops/runbook.md, docs/security/disclosure.md, docs/compliance/gdpr.md, docs/compliance/drone-regulations.md, docs/dev/onboarding.md, docs/dev/release-process.md; updated README docs map; added docs-validation test (tests/test_phase6h_docs.py).
- [x] 6.I Compliance + data protection — **done** (2026-05-18, branch
      `claude/phase-6-planning-X3ICw`).
      Documentation: expanded `docs/compliance/gdpr.md` with the data
      controller / processor posture, the canonical PII inventory
      (operator_id in `operator_commands` + audit-event bodies,
      authentication secrets in `operators.yaml`, request-log IP),
      a textual data-flow diagram, the data-subject-rights matrix
      (Art. 15–22), the DPIA reference inputs, and the breach-
      notification flow. New canonical retention table at
      `docs/compliance/retention.md` (telemetry 30 d, events 365 d,
      operator_commands 7 y, sessions 365 d, sector_visits 365 d,
      camera-frames drone-day, backups 30 d). New Article 28 processor
      agreement template at `docs/compliance/dpa-template.md` (parties,
      sub-processors annex, audit rights, termination obligations).
      Expanded `docs/compliance/drone-regulations.md` with the
      responsibility split table, jurisdictional reference (EASA, CAA,
      FAA, FOCA), the runtime controls SwarmOS enforces (geofence,
      battery, link, weather, NOTAM hook), the pre/in/post-flight log
      expectations, and the site-level camera-payload policy.
      Backend: new Alembic migration
      `20260518_0002_phase6i_retention.py` adding a 365-day Timescale
      retention policy to `events` (Postgres-only; no-op on SQLite).
      New compliance router `backend/app/api/compliance.py` exposing
      `POST /admin/export` (Art. 15 — returns every persisted row that
      references the subject in JSON form, audit event + WS broadcast,
      1/min/operator rate limiter) and `POST /admin/forget` (Art. 17
      — anonymises `operator_commands.operator_id` to the deterministic
      pseudonym `op-erased-<sha256_short>`, audit row preserved per
      Art. 17(3)(b)/(e), idempotent, blocks re-anonymisation). Both
      gated by `require_commander` (re-checks `mfa=true` claim on every
      call) and validate `operator_id` against the established regex.
      Three new repository helpers: `export_operator`,
      `anonymize_operator`, `prune_old_rows` (application-level
      retention for non-hypertable tables).
      Tests: 31 new tests in `backend/tests/test_phase6i_compliance.py`
      (auth + RBAC + MFA gates, body validation, happy path, audit
      emission, WS broadcast, rate limiter, metrics, voice-clean audit
      copy, pseudonym determinism, repository-helper independence) and
      9 new tests in `tests/test_phase6i_compliance_docs.py` (doc
      existence, doc voice-clean, retention numbers match the
      migration, retention table cites `operator_commands` 7 y,
      compliance router uses canonical phrase + pseudonym prefix,
      README cites both new docs, gdpr.md references the endpoint
      surface + Art. 15 / Art. 17, drone-regulations.md calls out
      operator responsibility). Full suite: **611 passed, 16 skipped**
      (vs Phase 6.H baseline 580 / 16). `make lint` green (ruff + mypy
      154 files + tsc), `make audit` green (pip-audit clean, pnpm
      audit clean, Bandit 0 medium / 0 high, pymavlink integrity
      PASS). Voice + brand audit greps clean on every new file.
      Drone-day items (DPA execution, DPO appointment, retention
      window confirmation with legal, controller-side DSAR procedure,
      quarterly retention audit, camera-payload site policy, NOTAM
      integration credentials, DSAR endpoint pen-test, aircraft +
      pilot registration, insurance, annual DPIA review) catalogued
      in `docs/ops/drone-day-checklist.md` §2.I.
      Anti-overreach honoured: no PDF report generation, no
      self-service DSAR portal, no external NOTAM / weather feed
      wired, no new tables, no operator-store mutation coupled to
      `/admin/forget`.
- [x] 6.J Testing finale — **done** (2026-05-19, branch
      `claude/phase-6j-planning-9YCmF`).
      End-to-end suite at `tests/e2e/` (anomaly lifecycle
      PENDING → VERIFYING → VERIFIED → ESCALATION → RETURN → DOCKED via
      the real bus + coordinator + FastAPI surface, no internal mocks;
      parity guard `tests/test_phase6j_testing.py` greps for
      `unittest.mock` / `Mock(` / `MagicMock(` against real code lines).
      Backend coverage gate raised to 80% with `backend/` added to the
      `--cov` scope (Makefile + `.github/workflows/test.yml`); load +
      chaos samples deselected because instrumentation distorts their
      p95 SLO. New `[tool.coverage.run]` block omits tests/, sim/,
      migrations, and the hardware-only vendor adapters. Coverage on
      the included scope: **88.37%** (vs 80% gate).
      Frontend Vitest + Testing Library + jsdom landed for the 70%
      critical-path gate scoped to `lib/auth.tsx`, `lib/api.ts`,
      `lib/ws.ts`, `components/EmergencyStop.tsx`,
      `components/AuthGate.tsx`; 36 tests across 5 files, statements
      76.5% / branches 82.7% / functions 73.5% / lines 76.5%.
      `pnpm-lock.yaml` regenerated; `ignore-scripts=true` and frozen
      lockfile invariants preserved.
      Monthly chaos drill at `.github/workflows/chaos-test.yml`
      (`cron: "23 6 1 * *"`): docker-compose postgres + redis,
      backend on host, runs `scripts/chaos/backend_kill.sh` then
      `scripts/chaos/redis_pause.sh`, uploads probe logs.
      OWASP ZAP baseline at `.github/workflows/zap-baseline.yml`
      (PR + push to main + workflow_dispatch, no schedule): ZAP image
      pinned by digest
      `sha256:8770b23f9e8b49038f413cb2b10c58c901e5b6717be221a22b1bcab5c9771b8a`,
      HIGH-only fail gate via `scripts/ci/zap_fail_on_high.py`
      (stdlib-only), 30-day report artifact.
      Process docs: `docs/security/pentest-scope.md` (in/out-of-scope,
      credentials policy, CVSS v3.1, SLA matrix, retest cycle),
      `docs/operator/acceptance.md` (10 scenarios mapped 1-to-1 to the
      e2e transitions, sign-off table). Drone-day items (real external
      pen-test execution, live operator acceptance on a customer site,
      prod-domain ZAP scan, prod-cluster chaos drill, coverage-drift
      watch) catalogued in `docs/ops/drone-day-checklist.md` §2.J.
      README docs map links the two new files.
      Tests: 2 new e2e + 15 new doc-parity, plus 36 frontend vitest
      tests; full backend suite **625 passed, 16 skipped, 3 deselected**
      (vs 611 / 16 baseline). `make lint` green, `make audit` green,
      voice + brand audit clean on every new file.

External-asset gates (weather API key, JWT signing key, TLS domain,
Sigstore identity, NOTAM feed, MFA TOTP provider) are deliberately not
"required to be done in this branch"; they are captured in the drone-day
checklist and gated on hardware acquisition.

## Phase 7 — entry criteria (pre-flight, 2026-05-19)

Phase 7 ("Software MVP base in simulazione") begins fresh:
`sim/scenarios/`, `swarm_os/autonomy.py` baseline, Console `AUTO`
eyebrow, CV baseline, `make demo-*` targets. Before declaring Phase 6
ready and starting Phase 7, the readiness audit specified in
`CLAUDE.md` ("When the user asks for a readiness check on a phase")
was re-run from a clean state on branch
`claude/fix-phase-7-prep-OeSvj`. Evidence (not claims):

- `rm -rf .venv && uv sync --frozen --extra dev --extra mavlink
  --extra dji` → clean install; 92+ packages locked.
- `pnpm install --frozen-lockfile --ignore-scripts` → clean;
  `.npmrc` `ignore-scripts=true` honored.
- `ruff check .` → `All checks passed!`
- `mypy core adapters orchestrator sim backend swarm_os` →
  `Success: no issues found in 154 source files`.
- `tsc --noEmit` → green (engine warning Node 22 vs declared 24 — CI
  consumes `.nvmrc=24`, local web container ships 22; warning only).
- `pytest -q -m "not load_smoke and not chaos" --cov-fail-under=80`
  → **625 passed, 16 skipped, 3 deselected**; coverage **88.37%**
  (vs 80% gate).
- `vitest run --coverage` → **36 passed / 5 files**; coverage
  76.5% statements / 82.7% branches (vs 70% gate).
- `pip-audit --skip-editable` → "No known vulnerabilities found".
- `bandit -r … --severity-level medium` → 0 medium / 0 high (23 low).
- `scripts/verify_pymavlink_integrity.py` → PASS, version 2.4.49,
  36 wheels, 176 record hashes verified offline.
- `pnpm audit --audit-level=high` → 0 high / 0 critical (2 moderate
  in dev-only transitive deps — `vitest@2.1.9` → `vite@5.4.21`
  + `esbuild@0.24.0`; below `make audit` gate threshold; fixing
  requires bumping to vitest 3+ and is queued for a separate
  branch alongside the Phase 7 frontend tweaks).

Real infra exercised inside the session:

- Postgres 16 booted natively (no docker daemon in the web
  container); Timescale extension is **not available** locally so
  `alembic upgrade head` against the pinned `timescale/timescaledb`
  image remains a CI-only gate (caveat consistent with Phase 4
  post-readiness note). Same caveat as before — *not* claimed as
  validated here.
- Redis 7 booted natively; bus + WS hub paths exercise the in-memory
  bus in tests and the real Redis client driver in the load-smoke
  suite.

Doc + script audit (`CLAUDE.md` rule 3 — failure-swallowing patterns):

- `scripts/dev_up.sh` → fail-fast Alembic step; no `|| true` masks
  on critical paths.
- `scripts/backup_restore_drill.sh` → `set -eu`; `|| true`/`|| echo
  0` are diagnostic-only (row-count trend metrics; schema parity is
  asserted via `alembic current` vs `alembic heads`).
- `scripts/chaos/*` → `|| true` only in cleanup traps.
- `.github/workflows/sast.yml` → semgrep stays advisory; comment
  updated to reflect Phase 6 completion + the registry-pinning
  deferral. Blocking SAST/supply-chain gates are bandit, ruff,
  pip-audit, pnpm audit, Trivy (image-scan).

Doc fixes shipped with this audit:

- STATUS table row 6 → `done` (was `in_progress` with a stale
  duplicate counter that contradicted the rest of the file).
- Open decisions → Phase 6 deploy target marked **resolved** (both
  `docker-compose.prod.yml` and the Helm chart shipped in 6.E;
  per-customer choice lives in `docs/ops/deploy.md`).
- 6.J update typo "630 passed" → "625 passed" (matches the re-run
  evidence above and the earlier section in this file).

Phase 7 is unblocked. Hardware-day and external-asset items
remain catalogued in `docs/ops/drone-day-checklist.md`.

## Last updated

2026-06-14: **Phase 7 extension — Anomaly Evidence Layer** on branch
`feature/anomaly-evidence-layer`. Each anomaly now carries its **provenance**
(`AnomalySource`: drone CV / thermal satellite / fire detector) and the
**triggering signal** (`AnomalyEvidence`: metric / value / baseline / unit +
a server-built `headline`), modelled honestly in the sim and flagged
`simulated: true` — SwarmOS decides, the Console only renders it.

- **Contract** (`core/swarm_core/messages.py`): `AnomalySource` enum +
  strict `AnomalyEvidence` model; nullable `evidence` on `Anomaly` (permissive)
  and `AnomalyView` (strict). `voice.evidence_headline()` builds the
  confidence-bound one-liner server-side (FORBIDDEN_WORDS-clean; unit-tested).
- **Honest sim** (`sim/swarm_sim/`): `ScriptedAnomalyCfg` gains `source` +
  `signal` (new `SignalCfg`); `IgnitionEvent` threads `source` +
  `EvidenceSignal`; `perception.build_evidence()` fills evidence on both the
  Mock (thermal/fire-detector scripted values) and CV (real YOLO label+score
  → `object_score`) paths. Coordinator projects `evidence` onto `AnomalyView`
  (one line). Scenarios declare provenance: wildfire SMOKE→drone_cv,
  FIRE→thermal_sat (47 °C vs 18 °C baseline); intrusion/search → drone_cv.
- **Persistence** (`backend/app/db/`): additive nullable `anomalies.evidence`
  JSON column + Alembic `0005_anomaly_evidence` (up/down round-trip tested on
  sqlite); `repository.write_anomaly` serialises it.
- **Console** (`frontend/`): `AnomalySource`/`AnomalyEvidence` types + 3 named
  inline SVG source glyphs (`IconThermalSat`/`IconFireDetector`/`IconDroneCv`);
  `describeSource`/`formatEvidence`/`anomalyCallout` in `derive.ts`; map
  per-source marker glyph + evidence-led callout
  (`THERMAL SAT · +29°C OVER BASELINE · DETECTED`); amber low-opacity
  `HeatOverlay` for `temperature_c` anomalies (state cue, no red/glass);
  shared `EvidenceBlock` on the verify detail + Control summary; mobile
  plain-voice reason line.
- **Gates**: `make lint` green (ruff + mypy 184 files + tsc); `make test`
  green (Python **778 passed / 23 skipped**; frontend **105 passed**, incl.
  new evidence/headline/callout/EvidenceBlock/HeatOverlay tests). Live
  end-to-end on the wildfire scenario: backend serves both anomalies with
  evidence; Console renders per-source callouts + glyphs, the verify
  `EVIDENCE` block (SOURCE/SENSOR/MEASUREMENT/READING), and the mobile reason
  line. **Caveat**: the amber `HeatOverlay` (and every maplibre overlay,
  incl. the pre-existing `SectorLayer`) could not be visually confirmed in
  the sandbox because the map `load` event doesn't complete without glyph-CDN
  egress; `HeatOverlay` is a structural twin of the proven `SectorLayer` and
  its selection logic is unit-tested.

2026-05-31: **Phase 7 WS2 — demo breadth: honest autonomy metrics +
3-scenario capture tool** on branch `claude/loving-wozniak-5i7QC` (plan
`docs/plan/ws2-demo-breadth.md`, parent §Workstream 2). Surfaces the
*same* numbers the Phase 7.E bench collector records, live in the Console,
computed client-side from audit frames already in `useSwarm()` — every
value traces to a real audit record (no DERIVED, no new backend endpoint).

- **2b** `frontend/lib/metrics.ts` (new, pure) mirrors
  `scripts/scenario_metrics.py`: anomaly→decision + decision→dispatch
  p50/p95 via **nearest-rank with banker's rounding** (`roundHalfToEven`,
  NOT `Math.round` — the n=5/p50 `2.5→2` parity gotcha), plus
  `by_rule`/`by_status`/totals. `frontend/components/AutonomyMetrics.tsx`
  (new, CSS/SVG-only — no chart lib) reuses QuietPanel's `SectionLabel`
  idiom + tokens, self-gates on `autonomyEnabled`, labels every readout
  `(sim)`, renders an honest empty state (`— awaiting autonomy`, never
  `0 ms`), accents limited to orbital-blue/ash/platinum (no red). Mounted
  after `PerformanceSection` in `QuietPanel.tsx` (gated so non-autonomy
  sites render zero diff). `lib/metrics.ts` added to
  `vitest.config.ts` `coverage.include`.
- **2a** `scripts/m1_capture_screenshots.py` parametrized by
  `--scenario {wildfire,intrusion,search}` with a data-driven per-scenario
  beat list. Wildfire keeps its 5-beat arc (filenames unchanged);
  intrusion/search get 3 beats — `01-standby`, `02-<kind>-r1-verify`,
  `03-verified` — the human-on-the-loop arc (confidence 0.71/0.55 stays
  under the R2 0.80 floor, so the operator owns escalation; no R2 wait).
  Reuses the existing `wait_until` + login/map scaffolding. **No
  scenario/threshold edits** (per-scenario thresholds are Phase 8.B).

Evidence (in-container, fresh `make setup` venv on this branch):
- `pnpm test` ✅ — **86 frontend passed / 1 todo** (15 files); new
  `lib/metrics.test.ts` (20) proves percentile parity incl. the n=5/p50
  half-to-even case + `not.toBe(Math.round)`, by_rule null→`unspecified`,
  both latency deltas, negative-delta drop, empty→`{null,null,0}`,
  earliest-event vs `detected_at` fallback agreement;
  `components/__tests__/AutonomyMetrics.test.tsx` (5) asserts rendered
  values, `(sim)` labels, the `awaiting` empty state, null when disabled,
  and no `/red/` class. `lib/metrics.ts` 100 % lines / 88.9 % branch.
- `make lint` ✅ — ruff clean (incl. the parametrized capture script),
  mypy clean, `tsc --noEmit` clean.
- Expected artifact `by_rule` once 2a is captured: wildfire
  `{R1, R2}`; intrusion/search `{R1}` only (no R2) — the negative control.

Still manual (founder machine — needs a headed browser for real WebGL +
the Docker stack, same constraint as WS1's `.mov`): the live 3-scenario
capture (`make demo-{intrusion,search}-sim` + the tool `--scenario …`),
the `phase-7e-{intrusion,search}-*.json` metrics artifacts, and the
cross-check that the live `Autonomy (sim)` panel matches each artifact's
`latencies_ms` (the 2b parity test makes this true). The
`docs/yc/m1-a11y-report.md:84-89` mobile AUTO-chip note stays tracked
until the new captures confirm it (else Phase 8.A).

2026-05-29: **Phase 7 WS1 — live verify-loop fix + AUTO attribution
persistence** on branch `claude/dazzling-shannon-CDca7` (plan
`docs/plan/pre-yc-build-plan.md` §Workstream 1). Closes the load-bearing
demo defect: R2 auto-ESCALATE never fired on a live run because nothing
promoted an anomaly VERIFYING→VERIFIED when the *executed* VERIFY mission
completed (the `cmd-*` bookkeeping mission never runs; the orchestrator
runs its own uuid mission and publishes that `MissionProgress`). CI was
green only because the integration test manually forced `state=VERIFIED`.

- **1a** `swarm_os/coordinator.py` — `apply_mission_progress` now promotes
  VERIFYING→VERIFIED (ts=now) on a `phase==DONE` + `kind=="VERIFY"`
  mission, resolving the target by VERIFYING state (+ sector/geo when the
  mission carries them) via new `_promote_verified_anomaly` /
  `_anomaly_for_verify_mission`. Guards: promote only from VERIFYING (never
  clobber DISMISSED/ESCALATED/PENDING/already-VERIFIED, so a late or
  duplicate completion can't resurrect a resolved anomaly); a FAILED
  mission leaves it VERIFYING (no PENDING bounce → no R1 loop). Promotion
  runs *before* `_refresh`, so R2 observes the fresh VERIFIED on a *later*
  tick once the 10 s idle floor elapses — never same-tick.
- **1b** `docs/yc/m1-vo-script.md` — climax reworded to the honest
  two-detection arc (FIRE is a *separate* 0.88 anomaly that auto-verifies
  then auto-escalates after the idle floor; not a rising single marker).
  Forbidden-word grep clean.
- **1c** `swarm_os/tests/test_phase7b_integration.py` — removed both manual
  `state=VERIFIED` forcings; drive `apply_mission_progress(DONE)` through
  the production path instead. New:
  `test_verify_mission_done_promotes_anomaly_then_r2_escalates_end_to_end`
  (the test that would have caught the bug — pins the tick-ordering
  contract), `test_failed_verify_mission_leaves_anomaly_verifying`,
  `test_done_verify_mission_does_not_resurrect_dismissed_anomaly`.
- **1d** `frontend/lib/autonomy.ts` — added `findLatestAutonomyCommand`
  (most-recent autonomy command regardless of terminal status; reads a real
  audit record, not DERIVED fabrication). Switched `AnomalySummary.tsx`,
  `MobileAnomalyScreen.tsx`, `app/(console)/verify/[id]/page.tsx`, and
  `Map.tsx` from `findActiveAutonomyCommand` → `findLatestAutonomyCommand`
  so the AUTO chip persists on the terminal ESCALATED callout (the money
  shot the VO points at). `findActiveAutonomyCommand` kept + tested.
- **1e** Demo timing verified: `sim/scenarios/wildfire_owner_land.yaml`
  already has FIRE at `after_s: 25` (the plan's recommended value) and the
  collector `--duration` default (60 s) spans R2 at ≈t37-40. No change.

Evidence (commands run from a fresh `make setup` venv on this branch):
- `make lint` ✅ — ruff clean, mypy clean (181 source files), `tsc
  --noEmit` clean.
- `make test` ✅ — **751 python passed / 19 skipped / 3 deselected**,
  coverage **88.75 %** (≥80 gate); **61 frontend passed** (autonomy.ts
  100 % covered).
- `make audit` ✅ — pip-audit "No known vulnerabilities found", pnpm audit
  2 moderate (below the `--audit-level=high` fail threshold), bandit 0
  medium/high, audit-config 42 passed, pymavlink + cv-asset integrity PASS.
- **by_rule.R2 == 1 confirmed.** An in-process run of the *real*
  `SwarmCoordinator` + autonomy + command-bus through the wildfire
  two-detection arc yields `auto_decisions.by_rule == {R1: 2, R2: 1}`
  (computed identically to `scripts/scenario_metrics.py`), with
  `a-smoke=verified` (stays — below the 0.80 R2 floor) and
  `a-fire=escalated`. Artifact:
  `docs/bench/artifacts/phase-7-ws1-verifyloop-inprocess.json`
  (provenance-tagged `source: in-process … no backend/Docker`). The same
  arc is asserted continuously by the new end-to-end regression test.

Pre-existing branch-gate fixes folded in so the gates are runnable (this
branch predates `main`'s #73/#75 and was red on `make lint`/`make test`
before WS1): `frontend/components/Map.tsx` maplibre-gl v5
`canvasContextAttributes` nesting (fixes tsc TS2353 + a silently-dropped
M1-capture flag); `pyproject.toml` scoped ruff per-file-ignore for the
`scripts/m1_*.py` capture/debug utilities + dead-`noqa`/f-string cleanups;
`sim/swarm_sim/cv/tests/test_default_unchanged.py` aligned to 7.G's
wildfire `cv_enabled: false`. All identical to the validated fixes already
on `main`.

Still manual (plan §1f — NOT a code gate; needs a local Docker stack +
screen recorder, unavailable in this remote container): the live
`make demo-wildfire-sim` HTTP-backend `phase-7e-*` artifact and the
`docs/yc/videos/demo-01-sim-wildfire.mov` recording. WS2
(breadth/metrics) intentionally NOT started this session.

2026-05-26: Phase 7.F Console DS Spread 24 + Plain Voice v1 landed on
`main` via merged PR #72 (commit `19a91ce`) plus a follow-up fix-up on
`main` that re-surfaces the **AUTO marker on the viewport callout** and
in the QuietPanel `Recent action` row. The redesign canon (viewport
not dashboard, one calm right rail, no decorative shadow, 85 %
monochrome) ships intact; the demo-critical regression — the in-map
anomaly callout no longer naming SwarmOS as the decider when R1/R2
fired — is closed. Diff: `frontend/components/Map.tsx` (now takes
`commands?: OperatorCommand[]`, computes `findActiveAutonomyCommand`
per anomaly, prepends `auto · r1/r2 · ` to the callout text and flips
border + leader + colour to Orbital Blue `#7BE7FF` while the autonomy
command is non-terminal; auto attribute removed cleanly when the
command completes), `frontend/components/TerritoryControl.tsx` (passes
`commands` from `useSwarm()` to `MapView`),
`frontend/components/QuietPanel.tsx` (RecentSection takes
`recentAuto` + `recentRule` and renders an `auto · r1` prefix in
Orbital Blue when the latest command is `source === "autonomy"`),
`frontend/components/SceneHeader.tsx` (doc-comment locking the
hardcoded `simulation · wildfire scenario` badge until Phase 8 adds
`Session.environment`; runtime gating is out of scope here because it
would need an Alembic migration). New test
`frontend/components/__tests__/QuietPanel.test.tsx` (2 cases —
auto-source surfaces the eyebrow with rule, operator-source omits
it). Vitest gate: 54 passed / 54 (was 52, +2 from the new tests).
`pnpm exec tsc --noEmit` clean. Side fixes folded into the same patch
to keep `make {lint,test,audit}` all green on `main` (the Phase 7.F
merge had drifted the brand gate + introduced a WS isolation flake):
(1) **ruff drift** — `ruff 0.15.13` upgraded `tests/test_phase7e_demo.py`
+ `sim/swarm_sim/world.py` + `sim/swarm_sim/cv/tests/test_detector.py`
+ 3 fixable + 3 hand-fixes for `UP017`/`RUF046`/`N806`/`SIM117` so the
ruff gate compiles cleanly on the locally-installed minor; no semantic
change. (2) **brand-audit drift** — the Phase 7.F merge moved
`autonomy · baseline` from `HeadBar.tsx` to `QuietPanel.tsx` but
`tests/test_phase7c_brand.py::test_headbar_renders_autonomy_chip_with_connected_state`
still asserted the old location; renamed to
`test_quietpanel_renders_autonomy_chip` and re-pointed at the new file
+ `data-testid="autonomy-ghost"`. (3) **WS broadcast isolation bug** —
`WSHub.broadcast` (`backend/app/ws/telemetry.py`) only caught
`WebSocketDisconnect`/`RuntimeError`, so an `anyio.ClosedResourceError`
from a zombie `TestClient` socket lingering on the module-level
`HUB` singleton crashed the live broadcast mid-loop, taking the
e2e anomaly-lifecycle test down whenever it ran after a backend WS
suite. Patch: catch `anyio.ClosedResourceError` +
`BrokenResourceError` (treat as `WebSocketDisconnect`) and clear
`HUB._clients` in `tests/e2e/conftest.py::_reset_state` so a fresh
client list starts every e2e test. (4) **starlette PYSEC-2026-161** —
`uv lock --upgrade-package starlette` bumped `starlette` from `1.0.0`
to `1.1.0`; no app-level code change required, `make audit` now green
(`Found 0 known vulnerabilities` modulo the disputed `PYSEC-2025-183`
already on the ignore list). Final gate snapshot:
`make lint` ✅, `make test` ✅ (726 python passed / 19 skipped /
3 deselected + 54 frontend passed), `make audit` ✅.
Acceptance gates for the YC demo —
SMOKE callout at `t≈10 s` with confidence eyebrow, callout flips to
`auto · r1 · unit … · verifying` at `t≈12 s`, FIRE escalation
callout at `t≈25 s`, `auto · r2 · …` at `t≈35 s`, QuietPanel
`time to action` ≠ "—" once R1 is accepted, `cycles done`
increments after the verify completes — are now reachable from
the redesigned Control. The hands-on `make demo-wildfire-sim`
end-to-end gate (browser screenshots at every beat) remains the
final step before flipping the Phase 7 row to `done`; it lives on
the local Docker stack and is the user's manual exercise. Out of
scope per playbook §10: `Session.environment` runtime field
(Phase 8), per-scenario thresholds (8.B), shadow / A-B (8.B-bis),
detection-bbox overlay (8.D / 10), autonomy-first default (8.A).

2026-05-25: Phase 7.E `make demo-*` code-complete on branch
`claude/loving-feynman-yxQqU`. Three one-command targets shipped:
`make demo-wildfire-sim`, `make demo-intrusion-sim`,
`make demo-search-sim`. Implementation is shell + Makefile + a
read-only metrics collector — no new backend surface, no new Python
or JS dependency. Parametric script `scripts/demo_scenario.sh`
(`set -euo pipefail`, no `|| true` masks) exports `SIM_SCENARIO` and
delegates infra/sim/backend/Console boot to the existing
`scripts/dev_up.sh`; `scripts/demo_wildfire.sh` reduced to a thin
back-compat wrapper so `make demo` still works. New collector
`scripts/scenario_metrics.py` logs in as `op-viewer01` (provisioned
by `make bootstrap-auth-dev`), sleeps `--duration` seconds (default
60), snapshots `/commands` + `/events`, and writes
`docs/bench/artifacts/phase-7e-<scenario>-<utcts>.json` with
autonomy-decision counts by rule (R1/R2/R3) + by status, event
counts by kind, and the audit window. `/metrics` is deliberately
out of scope (commander+MFA gated); the SwarmOS audit log is the
gate's source-of-truth and is already populated by Phase 7.B + 7.C
(`OperatorCommand.source="autonomy"`, `Event.source="autonomy"`,
`OperatorCommand.rule`). 18 new smoke tests in
`tests/test_phase7e_demo.py` (Makefile shape, executable bits,
fail-fast shell, scenario YAML opt-in, collector `--help` smoke,
artifact-path isolation) — all green. Plan in
`docs/plan/phase-7e.md`. Hands-on end-to-end gate (3× `make demo-*`
runs with screenshot of `AUTO · R1`/`R2` chips + artifact JSON with
`auto_decisions.by_rule.R1 >= 1`) remains the final step before
flipping the table row to `done`; it requires a local Docker stack
and is documented in the plan file §Verifica. Out of scope per
roadmap §10: no Console inversion to observatory-default (8.A), no
per-scenario thresholds (8.B), no shadow / A-B (8.B-bis), no
detection-bbox overlay (8.D / 10).

2026-05-21: Phase 7.D CV baseline landed on branch
`claude/cv-baseline-sim-zOUAx`. New `sim/swarm_sim/cv/` package
(`detector.py` lazy-imports `ultralytics`+`torch`; `perception_cv.py`
is a drop-in for `MockPerception`; `weights.py` owns the manifest →
download → sha256 → cache flow; `manifest.json` pins HTTPS urls,
sha256, size, license per asset; `fixtures/` carries 12 CC0 32x32 PNG
placeholders authored by SwarmOS plus `LICENSES.md` with per-file
provenance; `_generate.py` regenerates the placeholders via stdlib
`zlib` only). Opt-in `[cv]` extra in `pyproject.toml`
(ultralytics 8.3, torch 2.4, opencv-headless 4.10, Pillow, numpy);
`make setup` deliberately does NOT install it (~2 GB wheels) so the
default contributor experience and the prod image
(`backend/Dockerfile`, `docker-compose.prod.yml`) stay
AGPL-free. Scenario opt-in via `perception.cv_enabled: true` in the
three owner-land YAMLs; `Scenario.build_world()` branches on the flag.
New `scripts/verify_cv_assets_integrity.py` mirrors
`scripts/verify_pymavlink_integrity.py` (offline, sha256-only, no
network); wired into `make audit` via the always-on
`audit-cv-integrity` step (fixture provenance is verified even without
the `[cv]` extra). New `make setup-cv` / `make test-cv` /
`make cv-generate-fixtures` targets. Default `make test` deselects
the `cv_baseline` + `cv_baseline_realistic` markers so the gate stays
green without the extra. Tests: 5 test files under
`sim/swarm_sim/cv/tests/` (manifest schema/integrity/offline gate ×
12 cases; detector smoke + determinism × 2; CVPerception seam ×
4; wildfire e2e × 1; default-unchanged × 5). Docs:
`docs/cv/phase-7d.md` (asset classes, fixture flow, drone-day pin
flow, license posture, anti-overreach), AGPL-3.0 perimeter section
added to `docs/security/threat-model.md`, README docs map points at
`docs/cv/phase-7d.md`. Out of scope per the plan: per-scenario
thresholds (8.B), shadow / A-B mode (8.B-bis), detection-bbox overlay
in Console (8.D / 10), `make demo-*` (7.E), training loop (10.A), live
RTSP / WebRTC ingestion (11 / 14), detection-history table (16). Last
verified locally: `python sim/swarm_sim/cv/fixtures/_generate.py` → 12
PNGs (6 fire + 6 person_aerial) ; `python scripts/verify_cv_assets_integrity.py`
→ `cv assets integrity: PASS fixtures=12 weights_cached=0
samples_cached=0 network=not-used`. Full `make lint && make test &&
make audit` from a clean `.venv` requires the existing `make setup`
infrastructure (uv + node + frontend pnpm) and is the pre-merge gate;
the `cv_baseline` suite is gated by `pytest.importorskip("ultralytics")`
so the default `make test` suite is unchanged.

2026-05-21: Phase 7.C Console "AUTO" eyebrow + observatory surface
landed on branch `claude/execute-eager-robin-plan-H9ppE`. Backend:
`Session.autonomy_enabled` (Phase 7.B boot-time gate surfaced to the
Console), `Event.source` (operator vs. autonomy projection on the
audit log), `OperatorCommand.rule` (structured "R1"/"R2"/"R3" label
on autonomy decisions — forward-compatible with 8.B-bis shadow,
8.C override soft, 8.D rule-level eyebrows, 10.I A/B). New
``SwarmState.set_autonomy_enabled`` helper keeps state +
session in lockstep across the env-var path (`SWARM_AUTONOMY_BASELINE=1`
in `main.py`) and the scenario-YAML path (sim runner). Event
detector emits "autonomy verify dispatched · R1" / "autonomy
escalate dispatched · R2" / "autonomy dismiss dispatched · R3" on
the OPERATOR-kind timeline, voice-clean. Alembic migration 0004
adds ``events.source`` (server_default 'operator') and
``operator_commands.rule`` (nullable); repository writes + reads
both. Frontend: HeadBar inline ``autonomy baseline`` chip
(StatusPill connected variant — Orbital Blue halo), CommandTimeline
``AUTO · {rule}`` chip on autonomy rows, EventFeed ``auto`` kind
label (Orbital Blue), AnomalySummary / verify panel /
MobileAnomalyScreen all carry ``AUTO · {action}`` while a
non-terminal autonomy command targets the focus anomaly via a new
shared selector ``frontend/lib/autonomy.ts``. 27 new tests (13
backend + 14 frontend including 5 selector unit tests); full
backend suite **701 passed / 16 skipped / 3 deselected** (vs 684
baseline), backend coverage 88.64% (≥ 80% gate), frontend vitest
**49 passed**, critical-path coverage 77.3% lines / 83.1% branches
(≥ 70% / 60% gate). `make lint` (ruff + mypy 168 files + tsc),
`make audit` (pip-audit clean, pnpm audit at gate, Bandit 0
medium/high, pymavlink integrity PASS) all green. Voice + brand
audit greps return zero hits in product code. No new dependencies
in `pyproject.toml` or `package.json`; no inversion of the Console
default (8.A scope); no per-scenario thresholds (8.B scope); no CV
runtime (7.D scope); no `make demo-*` (7.E scope). Manual smoke
end-to-end with `SWARM_AUTONOMY_BASELINE=1 make demo` requires a
local Docker stack and is deferred to the next demo session — the
in-process integration tests already exercise the wildfire R1+R2
path end-to-end.

2026-05-20: Phase 7.B autonomy baseline landed on branch
`claude/autonomy-baseline-sim-X51Id`. Three new deterministic rules in
`swarm_os/autonomy.py` (R1 auto-VERIFY at conf>=0.50 + age>=2 s, R2
auto-ESCALATE at conf>=0.80 + idle>=10 s, R3 auto-DISMISS at
conf<0.30 + age>=30 s) dispatch through the existing operator
command bus via a new lock-free `submit_locked` helper — same
audit log, same Phase 6.A policy gate (geofence / battery / link /
weather), same MissionView lifecycle. `OperatorCommand.source`
distinguishes "operator" vs "autonomy" rows; Phase 7.C will read
this field for the Console `AUTO` eyebrow. Additive Alembic
migration `0003_phase7b_command_source.py` (portable SQLite +
Timescale; default 'operator' backfills the 614 historical rows).
The three scenario YAMLs opt in via `autonomy_baseline: true`; the
sim runner stamps `state.autonomy_enabled = True` in-process and
the backend reads `SWARM_AUTONOMY_BASELINE` from the env for the
cross-process `make demo` path. ESCALATE was an unwired enum value
— now wired in `command_bus._validate_target` + `_apply` (state
transition only, no mission spawned). pyjwt PYSEC-2025-183 disposed
via `--ignore-vuln` (disputed by supplier, no fix; SwarmOS enforces
SWARM_JWT_SECRET >= 32 bytes through `make bootstrap-auth-dev`).
Tests: 22 unit (rule boundaries, debounce, idle, stale, idempotency,
voice-clean, sentinel-outside-API-regex) + 10 integration
(coordinator end-to-end against each scenario YAML; wildfire reaches
ESCALATED via autonomy alone, intrusion/search stay VERIFIED below
0.80) + 6 backend (source persistence + migration round-trip) + 2
scenario (autonomy_baseline schema field). Full suite **684 passed
/ 16 skipped / 3 deselected** (vs 641 baseline, +43 new).
`make lint` + `make audit` green; voice/brand audit clean on every
new file. Out of scope (Phase 8+ explicitly): per-scenario
thresholds, WAIT decision, shadow mode, override soft, kill switch,
runtime admin toggle for `autonomy_enabled`. Out of scope for 7.B
specifically: Console `AUTO` eyebrow (7.C), `make demo-*` targets
(7.E), CV inference (7.D).

2026-05-19: Phase 7-prep readiness audit on branch
`claude/fix-phase-7-prep-OeSvj`. Re-ran the full gate from a clean
`.venv` per the `CLAUDE.md` readiness rules. Results: `make lint`
green, `pytest` 625 passed / 16 skipped / 3 deselected (cov 88.37%),
`vitest` 36 passed (cov 76.5% / 82.7%), `pip-audit` clean, `bandit`
0 medium/high, `pnpm audit --audit-level=high` clean (2 moderate in
dev-only `vitest@2.1.9 → vite@5.4.21 / esbuild@0.24.0` deferred —
bump to vitest 3+ tracked separately), pymavlink integrity PASS.
Doc fixes: Phase 6 marked `done` in the status table (the row had a
stale duplicated counter that contradicted the rest of the file),
"Phase 6 deploy target" open decision marked **resolved** (both
deploy paths shipped in 6.E), "Last updated" typo 630 → 625
(matches the actual pytest output). `sast.yml` semgrep comment
updated to reflect Phase 6 completion + the registry-pinning
deferral; semantics unchanged. No code logic touched. Phase 7
("Software MVP base in simulazione" — 3 scenari + autonomy
baseline + CV + `make demo-*`) is unblocked.

2026-05-19: Phase 6.J testing finale completed on branch
`claude/phase-6j-planning-9YCmF`. Added end-to-end suite at
`tests/e2e/` (anomaly lifecycle PENDING → VERIFYING → VERIFIED →
ESCALATION → RETURN → DOCKED via real bus + coordinator, no internal
mocks). Raised backend coverage gate to 80% with `backend/` in scope
(load + chaos samples deselected because instrumentation breaks
their latency SLO); coverage on the included scope **88.37%**.
Frontend Vitest + Testing Library at 70% critical-path coverage on
`lib/auth.tsx`, `lib/api.ts`, `lib/ws.ts`,
`components/EmergencyStop.tsx`, `components/AuthGate.tsx` (36 tests,
statements 76.5% / branches 82.7%). Monthly chaos drill workflow +
OWASP ZAP baseline workflow (HIGH-only fail gate via
`scripts/ci/zap_fail_on_high.py`). Process docs landed for the
drone-day field items: `docs/security/pentest-scope.md`,
`docs/operator/acceptance.md`, `docs/ops/drone-day-checklist.md §2.J`.
Tests: 2 new e2e + 15 new doc-parity + 36 new frontend vitest; full
backend suite **625 passed / 16 skipped / 3 deselected** (vs 611 /
16 baseline). `make lint` + `make audit` green; voice / brand audit
clean on every new file. Drone-day items (real external pen-test
execution, live operator acceptance, prod-domain ZAP, prod-cluster
chaos drill) catalogued in §2.J.

2026-05-18: Phase 6.I compliance + data protection completed on
branch `claude/phase-6-planning-X3ICw`. Expanded
`docs/compliance/gdpr.md` (data flow, PII inventory, data-subject
rights matrix), added the canonical
`docs/compliance/retention.md`, the Art. 28
`docs/compliance/dpa-template.md`, and the expanded
`docs/compliance/drone-regulations.md`. New Alembic migration
`0002_phase6i_retention` adds a 365-day Timescale retention policy
on `events`. New `backend/app/api/compliance.py` router exposes
admin-mediated `POST /admin/export` (Art. 15) and
`POST /admin/forget` (Art. 17 with pseudonymisation). 31 new
backend tests + 9 cross-cutting doc-parity tests; full suite
**611 passed / 16 skipped** (vs 580 / 16 baseline). `make lint` +
`make audit` green; voice / brand audit clean on every new file.
Drone-day items (DPA signing, DPO appointment, controller-side
DSAR procedure, quarterly retention audit, camera-payload site
policy, NOTAM integration, pen-test, aircraft + pilot
registration, insurance, annual DPIA review) catalogued in
`docs/ops/drone-day-checklist.md` §2.I.

2026-05-18: Phase 6.H documentation completed on branch `codex/phase-6h-documentation`. Documentation set added (architecture/API/WS/operator/ops/security/compliance/dev), README docs map refreshed, and `tests/test_phase6h_docs.py` added to validate required files, key links, OpenAPI route presence, WS kinds, and forbidden-word absence in new docs.

2026-05-18: Phase 6.G resilience + disaster recovery landed on
`claude/plan-phase-6g-N1Ail`. New `EMERGENCY_RTL_ALL` operator intent
(commander+MFA, typed double-confirmation phrase, dedicated 1/min/op
rate limiter, SYSTEM audit event with the safety-bypass note), DR
runbook at `docs/ops/disaster-recovery.md`, Sentinel + Patroni
example configs under `infra/redis/` + `infra/postgres/`,
`scripts/backup_restore_drill.sh` (`make backup-drill`),
Console `EmergencyStop` button in HeadBar (Launch Amber, no red,
inline two-stage confirmation). 32 new tests; full suite
580 passed / 16 skipped (vs 558 / 16 baseline). `make lint` +
`make audit` green; voice/brand audits clean. Drone-day items
(Sentinel cluster, Patroni / managed RDS replica, WAL archive,
off-site backup sync, quarterly DR rehearsal, GPG rotation,
emergency stop pen-test) catalogued in
`docs/ops/drone-day-checklist.md` §2.G.

2026-05-18: Phase 6.F performance + scale targets landed on
`claude/plan-phase-6f-COete`. Three in-process p95 assertions in
`tests/load/test_load_inproc.py` (WS p95 < 200 ms, REST p95 < 100 ms,
200-unit burst rate-limiter drops > 0); standalone soak driver in
`tests/load/driver.py` (`make load-soak`); chaos drills in
`scripts/chaos/redis_pause.sh` and `scripts/chaos/backend_kill.sh`
with a re-usable `tests.chaos.ws_probe` module. New `load-smoke` job
on every push (`.github/workflows/test.yml`) plus a weekly
`.github/workflows/load-test.yml` soak (`schedule: 17 4 * * 1`,
SHA-pinned, runs Timescale + Redis as service containers). Smoke
locally green (3/3 passed in 13.09 s) and full suite 558 passed /
16 skipped (vs 555 / 16 baseline). No new dependencies; `httpx` +
`websockets` + `redis` were already core. Plan +
docs/ops/performance.md cover the SLO table and the diagnostic
walk-down for a breach.

2026-05-17: Phase 6.E deployment + infra-as-code landed on
`claude/memoized-starlight-plan-njyE3`. Backend / frontend / backup
Dockerfiles (multi-stage, digest-pinned, non-root, ro-rootfs);
`docker-compose.prod.yml` (single-node with nginx + Let's Encrypt
certbot + backup sidecar); raw k8s manifests + Helm chart with
ingress-nginx + cert-manager + HPA + NetworkPolicy + PSS-restricted
namespace + pg_dump CronJob; cert-manager ClusterIssuers;
`image-build.yml` (Trivy blocking) + `image-sign.yml` (cosign
keyless); GPG-encrypted pg_dump backup + restore-with-guard scripts;
`docs/ops/deploy.md` + `docs/ops/migrations.md`. 14 new tests; full
suite 555 passed / 16 skipped (vs 541 / 16 baseline). `make lint`
+ `make audit` green; voice/brand audits clean. Drone-day items
(DNS, real Let's Encrypt prod, GHCR creds, Sigstore identity,
NetworkPolicy CNI, GPG recipient, off-site sync, Grafana datasource
URL, Redis mTLS) catalogued in `docs/ops/drone-day-checklist.md` §2.E.

2026-05-17: Phase 6.D observability stack landed on
`claude/observability-stack-setup-Gxzh7`. Prometheus `/metrics`
(commander-gated or IP-allowlisted), structlog JSON logs with
secret-redaction processor, `X-Request-ID` middleware, active
`/ready` probe (DB + Redis + auth), optional OpenTelemetry via
`[otel]` extra, Grafana dashboard + alert rule files committed.
27 new tests; full suite 541 passed / 16 skipped (vs 514 / 16
baseline). `prometheus-client` pinned explicitly. Design note +
runbook in `docs/observability/overview.md`; drone-day items
(scrape config, Grafana datasource, Loki endpoint, Alertmanager
routes) catalogued in `docs/ops/drone-day-checklist.md` §2.D.

2026-05-17: Phase 6.C operator auth + RBAC + MFA-for-commander landed
on `claude/jwt-rbac-mfa-gRsfE`. Pure JWT HS256; 97 new auth tests on
top of the 6.B baseline; `pyjwt` pinned explicitly; full suite green
(514 passed, 16 skipped). The transitional `X-Operator-Id` and
`X-Admin-Token` gates were retired in the same pass. Hardware-day
items (secret provisioning, MFA enrolment, optional OIDC bridge,
HttpOnly cookie for refresh, Redis-backed revocation, pen-test) are
catalogued in `docs/ops/drone-day-checklist.md` §2.C and the design
note lives in `docs/security/auth.md`.
2026-05-17: Phase 6.B multi-site bootstrap + admin hot-reload landed on
the same branch (29 more tests, 414 total). Phase 6.A safety policy
engine landed on branch `claude/phase-6-production-os` with full kernel
wiring (scheduler / command bus / coordinator) and 53 new tests. The hardware-day actions
(real weather provider, Sigstore signing, MFA TOTP, customer
acceptance, etc.) are listed in
[`docs/ops/drone-day-checklist.md`](ops/drone-day-checklist.md).
2026-05-16: Phase 6 started on branch `claude/phase-6-production-os`.
Phase 5 readiness gates updated on branch
`codex/phase5-bench-security-gates`. Status is CI-ready by `make lint`,
`make test`, and `make audit`; `pymavlink` package integrity is enforced
offline; secure Redis mTLS entry criteria fail closed for prod/required
secure bus mode. PX4 SITL was attempted but not validated, and hardware
bench validation remains pending and must not be implied as done. Phase 4
post-readiness fixes on branch
`claude/verify-phase4-completion-qiLsH`.
Phase 4 originally completed on branch
`claude/phase-4-persistence-OGUJm`. Phase 2 was completed on branch
`claude/phase-2-start-CMUg1`. Phase 1 was completed at GitHub main
commit `2390f872908a4a52588287a3865b3da96c785750`.
