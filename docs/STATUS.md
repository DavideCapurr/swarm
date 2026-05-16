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

2026-05-15: Phase 2 completed on branch `claude/phase-2-start-CMUg1`.
Phase 1 was completed at GitHub main commit
`2390f872908a4a52588287a3865b3da96c785750`.
