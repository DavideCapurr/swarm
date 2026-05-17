# Drone-day checklist — what to do when the hardware arrives

This file collects every gate that was deliberately deferred because no real
drone, no real cloud account, and no real operations team existed at code
time. **Open this file the day you acquire the drones** and walk through it
section by section. Each item links back to the code that already supports
it; nothing here is hypothetical.

The repo is structured so that the codebase up to Phase 6 is **complete and
CI-validated** without a real fleet. What remains for hardware day is
**configuration, secrets, and field acceptance** — not implementation.

## 0. Hardware acquisition

Reference: [`docs/adapters/mavlink-setup.md`](../adapters/mavlink-setup.md).

- [ ] **Air frame**: PX4-compatible quadrotor. Tested wire profile is
      Holybro X500 v2 with Pixhawk 6C; ArduPilot is supported via the same
      adapter but not the primary path.
- [ ] **Radio**: SiK telemetry radio (915 MHz EU / 868 MHz Italy-allowed) or
      RFD900X. Pair the air unit and the ground station before any field
      test.
- [ ] **Dock charging**: for the demo site we assume `dock-langhe-01` with
      3 slots. Hardware can be a manual charging mat in v1; auto-dock
      requires Phase 7.
- [ ] **Regulatory check**: confirm the drone class (CE C0/C1/C2) and
      U-space authorization at the deploy site **before** powering anything
      on. SwarmOS does not validate flight legality — see
      [`docs/compliance/drone-regulations.md`](../compliance/drone-regulations.md)
      when that file is produced in Phase 6.I.

## 1. Phase 5 bench validation (gates currently `pending`)

These two gates are explicitly documented as pending in `docs/STATUS.md`
because no PX4 device existed in CI. They are the first thing to flip on
hardware day.

- [ ] **PX4 SITL acceptance**: follow
      [`docs/adapters/mavlink-setup.md`](../adapters/mavlink-setup.md)
      §SITL. Run `make phase5-sitl-gate` against a real PX4 SITL on
      `udp:localhost:14540`. Commit the artifact at
      `docs/bench/artifacts/<date>-sitl-probe.json` with `status: pass`.
- [ ] **Real hardware acceptance**: same checklist but with the radio
      connected. Commit the artifact at
      `docs/bench/artifacts/<date>-hardware-probe.json`.
- [ ] Update `docs/STATUS.md` Phase 5 row to **done** only after **both**
      artifacts exist for the exact commit under review.

## 2. Phase 6 external assets to provision

These are gates that the code already supports but require an account,
domain, key, or device the dev environment didn't have.

### 2.A Safety policy — weather provider (Phase 6.A)

The local stub provider is a deliberate placeholder. See
`swarm_os/safety.py` (`LocalStubWeatherProvider`).

- [ ] Choose a provider: OpenWeather (paid tier) or Aviationweather
      (FAA, free for the US; for the EU vineyard use OpenWeather or
      Meteomatics).
- [ ] Add API key to the secrets vault, never to git.
- [ ] Set `SWARM_WEATHER_PROVIDER=openweather` (or equivalent) in the
      production env.
- [ ] Update `infra/config/sites/<site_id>.yaml` `weather_provider.kind`
      and `refresh_interval_s`.
- [ ] Verify dock `weather_lock` flips on simulated wind > threshold by
      mocking the provider response in a staging run.

### 2.B Optional NOTAM / NFZ feed (Phase 6.A)

Out of scope for first bench but the policy engine has a plug-in slot.

- [ ] If you need NOTAM enforcement: integrate a provider (NATS, EASA
      NFZ overlay, ENAC for Italy) and reject missions whose waypoints
      fall inside an active NFZ. Hook lives next to the geofence check
      in `swarm_os/policy.py`.

### 2.B-bis Multi-site (Phase 6.B)

The 6.B work delivered: site-aware bootstrap via `SWARM_SITE_ID`,
hot-reload `POST /admin/reload-site-config`, audit event on every
reload, transitional `X-Admin-Token` gate.

What still needs you on hardware day:

- [ ] **Admin token**: generate a strong `SWARM_ADMIN_TOKEN` value
      and mount it as a Docker / k8s secret. Do not check it into
      git, env files, or compose YAML.
- [ ] **Per-site YAML**: drop one `infra/config/sites/<site_id>.yaml`
      per real site you operate. The committed `vineyard-01.yaml`
      is a template. For a new site, copy + edit the geofence
      polygon to match the legal authorization perimeter on a
      survey map (drone-day §3).
- [ ] **Boot env**: set `SWARM_SITE_ID=<your-site>` in the deploy
      environment so the backend boots against the right config.
- [ ] **Hot-reload workflow**: document for the operator how to
      submit a YAML edit (PR + merge + restart, or YAML edit +
      `curl -H X-Admin-Token POST /admin/reload-site-config`). The
      operator manual at `docs/operator/manual.md` will land in
      Phase 6.H with the full procedure.
- [ ] **Simultaneous multi-site multiplexing in one backend**: NOT
      delivered — Phase 7 concern. Today one backend instance
      serves one site at a time. If you need to run two sites from
      a single deploy, run two backend containers behind different
      hostnames, each with its own `SWARM_SITE_ID`.

### 2.C Operator auth (Phase 6.C — code landed)

The 6.C work delivered: pure JWT HS256 (15 min access, 8 h refresh,
rotation on use), RBAC across viewer/operator/commander, mandatory MFA
for commander at login and `mfa=true` re-check on commander endpoints,
in-process revocation list, audit events on every login / refresh /
logout / revocation, login + WS-upgrade auth, transitional
`X-Admin-Token` retired. See [`docs/security/auth.md`](../security/auth.md).

What still needs you on hardware day:

- [ ] **JWT secret**: generate ≥ 32 random bytes
      (`openssl rand -hex 32`) and mount as the `SWARM_JWT_SECRET`
      env var via a deploy secret. Never commit. Rotate annually +
      after any suspected compromise (drives all outstanding tokens
      to invalid; the revocation list is in-process, so a rotation
      is the supported "log out everyone" lever today).
- [ ] **Operators YAML**: copy `infra/config/operators.example.yaml`
      to `infra/config/operators.yaml` (or wherever
      `SWARM_OPERATORS_CONFIG` points), generate each
      `password_hash` with
      `python -m backend.app.auth.cli hash-password`, and provision
      each commander with
      `python -m backend.app.auth.cli new-mfa op-<id>`. Mount as a
      deploy secret. The repo `.gitignore` blocks the real file from
      being committed.
- [ ] **MFA enrolment**: scan each commander's `otpauth://…` URI
      into a TOTP authenticator app (Aegis / 1Password / FreeOTP /
      Google Authenticator). Print the recovery secret in a sealed
      envelope and store offline per company key-management policy.
- [ ] **OIDC bridge (optional)**: not delivered in 6.C. If a
      customer needs SSO, plug an OIDC provider in front of
      `/auth/login` in Phase 6.E.
- [ ] **HttpOnly cookie for refresh (optional)**: today the Console
      stores both tokens in `localStorage`. CSP forbids third-party
      scripts; the XSS exposure window is the 15-min access TTL. The
      cookie-based pipe (CSRF + SameSite + server-side cookie issuer)
      is queued for 6.E.
- [ ] **Redis-backed revocation list (multi-replica)**: in-process
      today, sufficient for single-instance. Multi-replica deploys
      must wait for the Redis swap together with the rest of the
      secure-bus rollout in 6.E.
- [ ] **Pen-test pass**: include the auth surface in the Phase 6
      external pen-test (login brute force, JTI replay, MFA bypass,
      WS upgrade auth).

### 2.D Observability (Phase 6.D — pending until that session)

- [ ] Prometheus scrape target configured against backend `/metrics`.
- [ ] Grafana instance with the JSON dashboards from
      `infra/grafana/dashboards/`.
- [ ] Alertmanager routes (PagerDuty / Slack / email) wired to the rules
      in `infra/grafana/alerts.yml`.
- [ ] Loki or ELK endpoint for structured logs.

### 2.E Deploy + signing (Phase 6.E — pending until that session)

- [ ] Public DNS record + TLS certificate (Let's Encrypt or commercial
      CA).
- [ ] Sigstore identity for `cosign sign` of container images. Add
      `COSIGN_EXPERIMENTAL=1` and OIDC identity to CI.
- [ ] Backup destination: S3 bucket / off-site location + restore drill
      scheduled.

### 2.F Compliance (Phase 6.I — pending until that session)

- [ ] GDPR DPO contact populated in `docs/compliance/dpa-template.md`.
- [ ] Retention windows confirmed with legal (telemetry 30 d, events
      1 y, audit 7 y — adjust to your jurisdiction).
- [ ] Data subject request workflow (export + delete) tested against
      production data.

## 3. Field calibration

- [ ] Compass + accel calibration done in QGroundControl, parameters
      saved on the air frame.
- [ ] Geofence polygon entered in the YAML site config matches the
      legal authorization perimeter; cross-check on a survey map.
- [ ] `MAX_ALT_M` in the site config matches your CE class limit
      (120 m for C2 in EU; less for some authorizations).
- [ ] Battery threshold `rtl_force_below_pct` calibrated to the actual
      cell chemistry — 20 % of a worn LiPo is less safe than 20 % of a
      fresh one. Err high on the first flights.
- [ ] Link RSSI floor measured in the field; set `rtl_below_quality`
      accordingly.

## 4. Customer / operator acceptance

- [ ] Operator manual ([`docs/operator/manual.md`](../operator/manual.md),
      Phase 6.H output) walked through with the actual operator.
- [ ] End-to-end demo: operator submits `verify` from Console, drone
      flies, anomaly verified, RTL, dock charge — captured on video.
- [ ] Emergency `EMERGENCY_RTL_ALL` (Phase 6.G) drilled with the
      operator at least once, on a SITL session if hardware drills are
      risky.
- [ ] Pen-test report (external) shows zero critical, zero unmitigated
      high.

## 5. Hand-off to production

- [ ] `make lint && make test && make audit` green on the release tag.
- [ ] SBOM (CycloneDX) attached to the release.
- [ ] Container image signed via `cosign verify` succeeds.
- [ ] Backup restore drill: dump → wipe staging DB → restore → boot;
      RTO measured and documented in
      [`docs/ops/disaster-recovery.md`](disaster-recovery.md).
- [ ] On-call rotation set up; runbook
      [`docs/ops/runbook.md`](runbook.md) reviewed by every on-call.

When every box above is ticked, Phase 5 and Phase 6 are *bench-validated*
and the system is genuinely production-ready, not just code-complete.
