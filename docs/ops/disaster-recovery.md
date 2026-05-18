# SwarmOS — Disaster Recovery runbook

Phase 6.G owns this document. It defines the recovery objectives, the
failure scenarios SwarmOS is engineered to survive, and the operational
procedures for each. The patterns described here (Redis Sentinel,
Postgres Patroni / managed-RDS replica, off-site backup sync) are
documented as the target topology; the **deployed** topology depends on
the customer's deploy choice — see
[`docs/ops/deploy.md`](deploy.md) for the single-node compose-prod path
shipped today.

## Recovery objectives

| Objective | Target | Source of truth                                |
|-----------|--------|------------------------------------------------|
| RTO       | 1 h    | "Console operational again, fleet reachable"   |
| RPO       | 5 min  | "audit + telemetry loss capped at last 5 min"  |

These objectives apply to the operator-facing surface (Console + REST +
WS) and to the audit trail (Postgres `events` + `operator_commands`).
Telemetry is best-effort by design: a multi-minute outage of the
telemetry stream is recoverable from the autopilot's local logs and does
not block recovery.

RPO 5 min is met by:

1. **Postgres WAL + replica** (or managed RDS with point-in-time
   recovery on, retention ≥ 7 days) for the audit log.
2. **Encrypted `pg_dump` daily** off-box (`scripts/backup_postgres.sh`,
   Phase 6.E) for the bulk-restore floor.
3. **State reconstruction from the bus** (Phase 4): on restart the
   backend backfills the in-memory event deque from the DB so the
   Console regains 200 events of history immediately, then live frames
   resume on the next bus tick.

RTO 1 h is met by:

1. Helm rolling restart of the backend pod (≈ 60 s),
2. or `docker compose -f docker-compose.prod.yml up -d` on the
   single-node target (≈ 90 s),
3. plus the `restore_postgres.sh` floor (≈ 5 min on a 1 GB dump,
   verified by the drill — see §Backup drill).

## Failure scenarios

For each scenario: detection → action → verification.

### S1. Backend pod crash-loop

* **Detection**: `/ready` returns 503, Grafana alert `backend_ready` fires,
  Console banner flips to `link · offline`.
* **Action**: Inspect logs via `kubectl logs -l app=swarm-backend
  --tail=200` (or `docker compose -f docker-compose.prod.yml logs
  backend`). If the cause is a bad config (env / operators.yaml), roll
  back to the previous Helm revision: `helm rollback swarmos -n swarm`.
  If the cause is a code bug, deploy the previous tag.
* **Verification**: `/ready` returns 200, the auth audit shows the
  backend logging in, `swarm_ws_clients` climbs back above zero.

### S2. Redis loss

* **Detection**: `/ready` reports `redis: down`, the alert `redis_up`
  fires. Backend stays alive in degraded mode but the bus is
  unreachable.
* **Action — non-secure mode (single-node dev)**: backend logs
  "InMemoryBus fallback engaged"; bring Redis back via `docker compose
  restart redis`. Lost messages are bounded by the bus consumer's
  in-memory deque (200 events).
* **Action — secure mode (Phase 5 prod gate)**: Sentinel does the
  failover. If a quorum cannot be reached, manual `redis-cli SENTINEL
  FAILOVER swarm-master` on the surviving node and verify the
  configured connection string still resolves via the Sentinel
  endpoint. See the example config at
  [`infra/redis/sentinel-example.yaml`](../../infra/redis/sentinel-example.yaml).
* **Verification**: `/ready` returns 200, `swarm_ws_clients` stable,
  telemetry frames flow within 5 s of recovery.

### S3. Postgres primary loss

* **Detection**: `/ready` reports `db: down`, the audit log stops
  growing, the alert `db_up` fires.
* **Action — managed RDS**: trigger the documented failover for the
  provider (RDS multi-AZ promotes in seconds, Cloud SQL HA likewise).
  Update the `DATABASE_URL` secret only if the connection string
  changed.
* **Action — Patroni (self-hosted)**: `patronictl failover swarmos`
  promotes the replica, the VIP / DNS alias re-points to the new
  primary. See the example config at
  [`infra/postgres/patroni-example.yaml`](../../infra/postgres/patroni-example.yaml).
* **Action — single-node**: restore from the latest backup (see
  §Backup drill). Accept the data loss between the failure and the
  last backup (≤ 24 h with the daily cadence, ≤ 5 min if WAL archive
  is configured).
* **Verification**: `/ready` returns 200, audit log row count matches
  pre-failure +/- inflight, Grafana `swarm_anomalies_pending` resumes
  updating.

### S4. Off-site backup loss

* **Detection**: weekly off-site sync job alert fires (drone-day item).
* **Action**: regenerate keys, replace the off-site target, re-run the
  drill manually (`make backup-drill`) and ship the resulting dump.

### S5. Total site loss (compose-prod target)

* **Detection**: monitoring sees the whole site down.
* **Action**:
  1. Provision a fresh host (or new k8s cluster with
     `infra/helm/swarmos`).
  2. Restore secrets from the secrets vault.
  3. `scripts/restore_postgres.sh --i-understand-this-overwrites
     <encrypted-dump.gpg>` to seed the audit log.
  4. Boot the stack (`docker compose -f docker-compose.prod.yml up -d`
     or `helm upgrade --install swarmos`).
  5. Point DNS at the new origin; certbot re-issues the TLS cert.
* **Verification**: end-to-end smoke (`docs/operator/manual.md` golden
  path) passes inside the RTO budget.

## Backup drill

Cadence: **monthly**. Owner: SRE (drone-day §2.G).

```
make backup-drill
```

The drill in `scripts/backup_restore_drill.sh`:

1. Boots a sidecar Postgres container with the same major version as
   prod.
2. Runs `scripts/backup_postgres.sh` against the *live* DB into a
   scratch dir (the dump is encrypted via the same GPG recipient as
   prod).
3. Runs `scripts/restore_postgres.sh --i-understand-this-overwrites`
   against the sidecar.
4. Asserts the restored schema matches `alembic current` and that
   `events` and `operator_commands` row counts are non-zero.
5. Tears the sidecar down. Drill PASS / FAIL is the exit code.

Drill artifacts (timestamped log + dump hash) are uploaded to the
off-site target documented in `docs/ops/drone-day-checklist.md` §2.G.

## Failover topology — code-complete, not deployed

Phase 6.G ships the **patterns** as reference configs and as Helm
values hooks; the **deployment** decision lives with the customer.

* Redis Sentinel: [`infra/redis/sentinel-example.yaml`](../../infra/redis/sentinel-example.yaml).
  Three sentinels, quorum 2, `down-after-milliseconds 5000`. Wire the
  endpoint via `REDIS_URL=rediss://sentinel-host:26379/0` plus
  `REDIS_TLS_*` from Phase 5.
* Postgres failover: [`infra/postgres/patroni-example.yaml`](../../infra/postgres/patroni-example.yaml).
  Three nodes, ETCD-backed leader election, async streaming
  replication. Managed alternatives (RDS multi-AZ, Cloud SQL HA, Azure
  Flexible Server HA) are interchangeable from SwarmOS's point of
  view — the only contract is a single `DATABASE_URL` that points at
  the writable endpoint.
* Helm values exposed: `redis.sentinel.enabled` (default `false`),
  `postgres.replication.mode` (default `off`). Both default off so the
  shipped chart still produces the single-node topology Phase 6.E
  validated.

## Emergency stop (the runtime DR control)

The `EMERGENCY_RTL_ALL` intent (Phase 6.G) is the in-flight emergency
control: every airborne unit returns to its dock at once. It's
commander-only with MFA + a double-confirmation phrase, the safety
policy gate is intentionally bypassed (a low battery is *why* we're
stopping), and the bypass is recorded in the audit log as a `system`
event.

Operationally:
* Triggered from the Console HeadBar button (commander role).
* Triggered via API by a runbook script: `POST /actions/emergency-rtl-all`
  with `{"confirm": true, "confirmation_phrase": "RETURN ALL UNITS"}`
  and a commander+MFA bearer token.
* After the fleet is recovered, clear `state.emergency_active_at` by
  reloading the site config (`POST /admin/reload-site-config`) — the
  hold-patrol flag clears with it.

## Out of scope (drone-day items)

These belong to `docs/ops/drone-day-checklist.md` §2.G, not this
runbook:

* Provision real Redis Sentinel cluster or managed Redis HA.
* Provision real Postgres Patroni cluster or managed Postgres HA.
* Configure WAL archive to S3 / B2 for the 5-min RPO floor.
* Real off-site backup sync target + key rotation.
* Quarterly DR-site failover rehearsal with the customer.
* Pen-test of the emergency stop endpoint by an external red team.
