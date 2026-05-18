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

### 2.D Observability (Phase 6.D code-complete; deploy items remain)

The code is in place — metrics registry, `/metrics` endpoint (commander
or IP-allowlist), structlog JSON pipeline with secret redaction,
`X-Request-ID` middleware, active `/ready` probe, dashboards + alert
rules under `infra/grafana/`. The drone-day items below are deployment
choices that need real infrastructure.

- [ ] **Prometheus scrape config** committed in the deploy overlay. Example
      stanza (drop into `prom-stack` values or any Prometheus instance):

      ```yaml
      scrape_configs:
        - job_name: swarmos-backend
          metrics_path: /metrics
          scrape_interval: 15s
          static_configs:
            - targets: ['swarmos-backend.swarmos.svc.cluster.local:8765']
          # Either set bearer_token (commander-scoped JWT) or rely on
          # SWARM_METRICS_IP_ALLOWLIST=<pod CIDR> in the backend env.
      ```

- [ ] **Grafana datasource provisioning** (`infra/grafana/datasource.yaml`)
      pointing at the Prometheus instance above. Import
      `infra/grafana/dashboards/swarmos-overview.json` (it parametrises
      the datasource via `${DS_PROMETHEUS}`).

- [ ] **Alertmanager routes** wired to the rule groups in
      `infra/grafana/alerts.yml`. Severity convention: `warning` → quiet
      Slack channel; `critical` → PagerDuty + on-call SMS. **No red
      band in dashboard styling** (design system §5.2).

- [ ] **Loki / Vector / Fluent Bit endpoint** for stdout JSON logs. Suggested
      labels: `service=swarmos-backend`, `site=$SWARM_SITE_ID`,
      `env=$SWARM_ENV`. Promtail's `json` parser is enough — lines are
      already JSON with `timestamp`, `level`, `event`, `request_id`,
      `path`, `method`.

- [ ] **OpenTelemetry collector** (optional). To enable tracing:
      install the `[otel]` extra (`uv sync --extra otel`) and set
      `SWARM_OTLP_ENDPOINT=http://otelcol:4318/v1/traces`. Default
      installs do not include the OTel stack.

- [ ] **Readiness probe** wired in the Kubernetes Deployment manifest:
      `readinessProbe: { httpGet: { path: /ready, port: 8765 }, periodSeconds: 10 }`.
      `livenessProbe` continues to use `/health`.

- [ ] **Blackbox-exporter** (optional, for the `SwarmReadinessProbeFailing`
      alert): scrape `/ready` from a probe instance so the alert can fire
      on actual probe failure rather than only on missing metrics.

### 2.E Deploy + signing (Phase 6.E — code-complete; deploy items remain)

The 6.E work delivered: backend / frontend / backup Dockerfiles
(multi-stage, non-root, read-only-rootfs-compatible, digest-pinned
bases), `docker-compose.prod.yml` for single-node deploys (nginx + LE
certbot + pg + redis + backend + frontend + backup sidecar), full
`infra/k8s/` raw manifests, the
[`swarmos` Helm chart](../../infra/helm/swarmos/) parameterised per
site, cert-manager ClusterIssuers, image build + cosign sign workflows
in CI, GPG-encrypted pg_dump backup script + restore drill, and the
deploy + migrations guides at [`deploy.md`](deploy.md) +
[`migrations.md`](migrations.md). What still needs you on hardware
day:

- [ ] **Public DNS A/AAAA record** for the chosen `TLS_SERVER_NAME` /
      `ingress.host`. Point it at the ingress LB (k8s) or single-node
      host (compose-prod).
- [ ] **Real TLS certificate**: edit the email in
      [`infra/cert-manager/issuer-letsencrypt-prod.yaml`](../../infra/cert-manager/issuer-letsencrypt-prod.yaml)
      and apply both ClusterIssuers. Verify cert issuance against the
      staging issuer first (it has no rate limit), then flip the
      Ingress annotation to `letsencrypt-prod`. For compose-prod, fill
      `TLS_EMAIL` in `.env`; the certbot sidecar handles the rest.
- [ ] **GHCR push credentials**: the image-build workflow uses
      `GITHUB_TOKEN` by default. For org-owned packages, set
      `actions: write` and `packages: write` on the workflow and bind
      the repo to the package via the GHCR UI.
- [ ] **Sigstore identity** for `cosign sign --yes`: the image-sign
      workflow uses keyless OIDC against
      `https://token.actions.githubusercontent.com`. Verify the
      certificate identity regex matches your repo path (the workflow
      uses `^https://github.com/<owner>/swarm/.+$`). Update it if you
      rename the repo or fork.
- [ ] **Image-pull Secret**: if pulling from a private GHCR org, create
      a `dockerconfigjson` Secret and add it to
      `image.imagePullSecrets` in the Helm values.
- [ ] **NetworkPolicy CNI**: confirm the cluster CNI enforces
      `NetworkPolicy` (Calico / Cilium / Antrea / Weave-net 2.6+). EKS
      / GKE clusters created without the right flag will silently
      ignore the policies.
- [ ] **StorageClass for the backup PVC**: `infra/helm/swarmos/values*.yaml`
      defaults to the cluster default; set
      `backup.storageClass` if you want an explicit SC (gp3 on AWS,
      pd-ssd on GCP, csi-driver-nfs on bench clusters).
- [ ] **GPG backup recipient**:
      generate the backup keypair offline (`gpg --full-generate-key`),
      import the public key into the keyring used by the backup
      container (mounted at `/home/swarm/.gnupg` via the
      `swarmos-backup-gnupg` Secret), and set the
      `BACKUP_GPG_RECIPIENT` env to the fingerprint. **Keep the private
      key offline**; never mount it into the cluster.
- [ ] **Off-site backup destination**: the local PVC (k8s) / docker
      volume (compose) holds the last 30 days. Add an rsync, AWS-CLI
      `s3 sync`, or `restic` cron entry that pushes
      `/backups/swarm-*.sql.gpg` to an off-site bucket. The dump is
      already encrypted; the off-site copy can sit on warm storage.
- [ ] **Quarterly restore drill**: schedule a recurring task that
      runs the procedure in [`migrations.md`](migrations.md)
      §"Restore drill" against a throwaway DB and records the RTO/RPO
      in the runbook.
- [ ] **Grafana datasource** (closes the 6.D drone-day item): drop
      [`infra/grafana/datasource.yaml`](../../infra/grafana/datasource.yaml)
      under the Grafana sidecar's provisioning directory and set
      `${DS_PROMETHEUS_URL}` (+ optional `${DS_LOKI_URL}`).
- [ ] **HttpOnly cookie pipe for refresh tokens** (closes the 6.C
      drone-day item, deferred to 6.E): replace the `localStorage`
      refresh-token store in `frontend/lib/auth.tsx` with a
      server-issued cookie. Out of scope on this branch — frontend
      currently still uses `localStorage` and the 15-min access TTL
      bounds the exposure.
- [ ] **Redis mTLS material** for the production secure-bus mode
      (Phase 5 fail-closed): provision `REDIS_TLS_CA_CERTS`,
      `REDIS_TLS_CERTFILE`, `REDIS_TLS_KEYFILE` as Secret mounts +
      switch `REDIS_URL` to `rediss://`. Without this, the backend
      refuses to fall back to the in-memory bus when `SWARM_ENV=prod`.

To verify the deploy after binding the above, run the checklist at the
end of [`deploy.md`](deploy.md) §6.

### 2.G Resilience + Disaster Recovery (Phase 6.G — code-complete; deploy items remain)

The 6.G work delivered: the `EMERGENCY_RTL_ALL` operator intent (JWT
commander + MFA + a typed confirmation phrase, with a dedicated
1/min/operator rate limiter and a SYSTEM event that records the safety
policy bypass), the DR runbook at
[`docs/ops/disaster-recovery.md`](disaster-recovery.md), reference
configs for the failover patterns at
[`infra/redis/sentinel-example.yaml`](../../infra/redis/sentinel-example.yaml)
+ [`infra/postgres/patroni-example.yaml`](../../infra/postgres/patroni-example.yaml),
and the monthly backup drill at `scripts/backup_restore_drill.sh`
(`make backup-drill`).

What still needs you on hardware day:

- [ ] **Redis Sentinel cluster** (or managed Redis HA) provisioned per
      the reference config. Three-node quorum, mTLS terminated at
      Redis, `REDIS_URL` switched to the Sentinel endpoint. Verify
      failover with `redis-cli SENTINEL FAILOVER swarm-master` and
      confirm the SwarmOS backend reconnects within 5 s (Phase 6.F
      chaos drill `make chaos-redis` exercises this path).
- [ ] **Postgres Patroni cluster** (or managed Postgres HA — RDS
      multi-AZ, Cloud SQL HA, Azure Flexible Server HA) provisioned
      per the reference config. ETCD cluster off-host, replication
      lag < 30 s, automated promotion enabled. Pen-test `patronictl
      failover` from a hostile network — the promotion command must
      not be reachable from the cluster's data-plane VLAN.
- [ ] **WAL archive** to off-site storage (S3 / B2 / GCS) with
      retention ≥ 7 days. Without this, RPO degrades from 5 min to
      the daily pg_dump cadence. wal-g + cron job is the supported
      pattern; document the recovery command in
      [`disaster-recovery.md`](disaster-recovery.md) §S3.
- [ ] **Off-site backup sync** for the encrypted pg_dump: nightly
      `aws s3 sync` (or `rclone` / `restic`) from the Phase 6.E
      backup PVC to a second-region bucket. Versioning enabled, MFA
      delete on, lifecycle rule to glacier after 30 days.
- [ ] **Monthly drill scheduled**: `make backup-drill` from a CI job
      or a cron entry; the script's exit code is the drill PASS/FAIL.
      Artifacts (drill log + dump hash) uploaded to the off-site
      target. Failures page the on-call.
- [ ] **Quarterly DR-site failover rehearsal** with the customer:
      promote the replica region, point DNS at the new origin, run
      the operator manual golden path inside the RTO budget, fail
      back. Document the RTO/RPO measurement in the runbook.
- [ ] **GPG backup recipient rotation**: yearly, with overlap so old
      dumps stay decryptable for the retention window. Procedure
      lives in [`disaster-recovery.md`](disaster-recovery.md) §Backup
      drill.
- [ ] **Emergency stop pen-test**: external red team exercises
      `POST /actions/emergency-rtl-all` (commander-only, MFA, double
      confirmation phrase, dedicated rate limiter, safety bypass +
      audit event). Confirm a stolen non-MFA commander token cannot
      trigger the intent and that a leaked replay of an accepted
      request body is throttled within 1 min.
- [ ] **Runbook handover** to the customer's SRE: walk through every
      scenario in [`disaster-recovery.md`](disaster-recovery.md), with
      live keyboard time on at least S2 (Redis loss) and S3 (Postgres
      primary loss) on a staging stack.

### 2.I Compliance (Phase 6.I — code-complete; deploy items remain)

Code landed: GDPR data flow + PII inventory ([`docs/compliance/gdpr.md`](../compliance/gdpr.md)),
canonical retention table ([`docs/compliance/retention.md`](../compliance/retention.md)),
Art. 28 processor agreement template
([`docs/compliance/dpa-template.md`](../compliance/dpa-template.md)),
drone regulatory reference
([`docs/compliance/drone-regulations.md`](../compliance/drone-regulations.md)),
admin-mediated DSAR endpoints (`POST /admin/export` for Art. 15,
`POST /admin/forget` for Art. 17 with pseudonymisation), Timescale
365-day retention policy on `events` (migration
`0002_phase6i_retention`), repository helper to prune non-hypertable
tables (`Repository.prune_old_rows`).

External-asset / operator-side items still to do:

- [ ] **DPA signed** — populate the parties, sub-processors annex, and
      governing-law clause in `docs/compliance/dpa-template.md` and
      execute. Controller + Processor legal teams own this.
- [ ] **DPO contact** — appoint or designate per Art. 37 if required by
      the controller's profile; document the contact channel that
      handles incoming DSARs.
- [ ] **Retention windows confirmed with legal** — telemetry 30 d,
      events 365 d, audit 7 y are the SwarmOS defaults; adjust to the
      controller's jurisdiction and update `retention.md` *and* the
      migration in the same change (the doc-parity test in
      `tests/test_phase6i_compliance_docs.py` will fail otherwise).
- [ ] **DSAR procedure** — controller-side workflow that authenticates
      the data subject and dispatches the commander to invoke
      `/admin/export` / `/admin/forget`. Out of band, not in SwarmOS.
- [ ] **Quarterly retention audit** — verify the Timescale retention
      policies are still running (`SELECT * FROM
      timescaledb_information.jobs WHERE proc_name='policy_retention';`),
      verify `BACKUP_RETENTION_DAYS` is honoured by the cron, verify no
      orphan plaintext dumps.
- [ ] **Camera-payload site policy** — when the camera lands (drone-day
      §3 field calibration), publish a per-site policy covering lawful
      basis, purpose, frame-rate minimisation, on-device face/plate
      blurring, retention, and signage. Store the policy in
      `infra/config/sites/<site_id>.yaml` (a future schema extension
      will codify it).
- [ ] **NOTAM / U-space integration credentials** — provision the
      national feed account; wire the runtime hook in `swarm_os/safety.py`
      (the polygon-rejection path is already in place, only the feed is
      missing).
- [ ] **Pen-test of the DSAR endpoints** — verify `/admin/export` and
      `/admin/forget` cannot be reached by viewer / operator / non-MFA
      commander, verify the rate limiter holds at 1/min/commander,
      verify the pseudonymisation is not reversible from log lines.
- [ ] **Aircraft registration + remote-pilot certification** — operator
      side, per the relevant jurisdiction (EASA / CAA / FAA / FOCA / …).
- [ ] **Insurance** — operator side, hull + third-party liability per
      flight category.
- [ ] **Annual DPIA review** — controller-side, against the updated
      data inventory and threat model.

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
