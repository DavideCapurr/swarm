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
| 5     | Real Adapter (MAVLink/PX4 via pymavlink)              | **CI-ready; SITL attempted/not validated; hardware pending** |
| 6     | Production OS (policy, geofence, auth, SBOM, ops)     | **in_progress** — 6.A/6.B/6.C done on `claude/jwt-rbac-mfa-gRsfE`; 6.D–6.J pending |

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
- [ ] 6.D Observability stack — pending.
- [ ] 6.E Deployment + infra-as-code — pending.
- [ ] 6.F Performance + scale — pending.
- [ ] 6.G Resilience + DR — pending.
- [ ] 6.H Documentation — pending.
- [ ] 6.I Compliance — pending.
- [ ] 6.J Testing finale — pending.

External-asset gates (weather API key, JWT signing key, TLS domain,
Sigstore identity, NOTAM feed, MFA TOTP provider) are deliberately not
"required to be done in this branch"; they are captured in the drone-day
checklist and gated on hardware acquisition.

## Last updated

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
