# Retention Policy (Phase 6.I)

This is the canonical data retention table for SwarmOS. The numbers
below are the source of truth — every other reference (migration code,
GDPR document, runbook) is checked against this table in CI by
`tests/test_phase6i_compliance.py::test_retention_numbers_match`.

For the legal basis of each retention period, see
[`docs/compliance/gdpr.md`](gdpr.md). For the backup policy that
inherits these retentions, see [`docs/ops/deploy.md`](../ops/deploy.md).

## Retention table

| Table / Stream      | Retention   | Enforcement                                  | Rationale |
|---------------------|-------------|----------------------------------------------|-----------|
| `telemetry`         | **30 days** | Timescale `add_retention_policy('telemetry', INTERVAL '30 days')` (Phase 4 migration `0001_phase4_initial`) | Operational data only — high cardinality, low long-term value. 30 days covers the time window an operator might investigate post-incident. |
| `events`            | **365 days** | Timescale `add_retention_policy('events', INTERVAL '365 days')` (Phase 6.I migration `0002_phase6i_retention`) | Console timeline + audit lines. One year covers customer-side audit cycles. Long-term operator-action audit lives in `operator_commands`. |
| `sector_visits`     | **365 days** | Application-level prune in `Repository.prune_old_data` (no Timescale hypertable for this table) | Coverage history is useful within an operating year; older data is summarised by reports, not by raw rows. |
| `operator_commands` | **7 years** | Permanent retention; erasure rewrites `operator_id` to `op-erased-<sha256_short>` via `POST /admin/forget` | Audit log of every operator intent. The retention floor matches typical commercial audit obligations. |
| `anomalies`         | Projection-only | One row per anomaly id, upserted on state change; old rows pruned when the anomaly id is no longer referenced | Operational projection, not a historical log. The full history is reconstructable from `events`. |
| `missions`          | Projection-only | One row per mission id, upserted on phase change | Same as `anomalies`. |
| `sessions`          | **365 days** | Application-level prune (one row per backend boot or per operator handover) | Boot history is useful for incident investigation within a year. |
| Camera frames       | **Not stored today** | Drone-day; governed by site-level policy when the camera payload is wired | Per `gdpr.md` §2 — the placeholder is in `drone-day-checklist.md` §2.I. |
| Backups (`pg_dump | gpg`) | **30 days** | `BACKUP_RETENTION_DAYS=30` in `scripts/backup_postgres.sh`; pruned by fingerprint check after every dump | Matches the upstream retention table — older operational data has already been pruned at source. |
| Structured request log | **Operator-defined** | Logged to stdout; collection / retention is the operator's choice (e.g. Loki retention policy) | SwarmOS does not store logs; the operator's log aggregation pipeline applies its own retention. The recommended floor is 30 days. |

## Implementation notes

* **Timescale hypertables**: `telemetry` (chunk 1 day) and `events`
  (chunk 7 days). `add_retention_policy` runs the background job that
  drops chunks older than the configured interval. The policy is
  idempotent (`if_not_exists => TRUE`) and is removed cleanly on
  downgrade.
* **SQLite test path**: the Timescale statements are guarded by a
  `bind.dialect.name == 'postgresql'` check; tests run on
  `sqlite+aiosqlite` without retention enforcement (retention is a
  production concern, not a correctness one).
* **`sessions`, `sector_visits`** are not hypertables — they are
  pruned by an application-level helper invoked from a cron / k8s
  CronJob. The helper is `Repository.prune_old_rows` and is exercised
  by the test suite for both retention windows.
* **`operator_commands`** is intentionally permanent. The compliance
  requirement is to surface the records for the legal retention floor;
  the operator's own data-management policy may delete rows beyond it
  using the `/admin/forget` anonymisation path or an explicit
  controller-side SQL job.

## Drone-day items

* Camera-frame retention per site (when the camera payload arrives).
* External log aggregation retention (Loki, Datadog, etc.).
* Off-site backup retention beyond the 30-day local window.
* Quarterly retention audit (verify `add_retention_policy` is still
  running on the live Timescale instance, verify `BACKUP_RETENTION_DAYS`
  is honoured by the cron, verify no orphan plaintext dumps).

These are catalogued in
[`docs/ops/drone-day-checklist.md`](../ops/drone-day-checklist.md) §2.I.
