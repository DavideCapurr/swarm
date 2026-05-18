# SwarmOS migrations playbook (Phase 6.E)

This document describes the Alembic-based schema migration workflow for
SwarmOS. The persistence layer landed in Phase 4 — see
[`../STATUS.md`](../STATUS.md) §"Phase 4". This guide is the operational
runbook for shipping schema changes to a live production database.

> Goal: a migration is a routine, low-risk operation. If a deploy is
> stuck rolling back because of a migration, something has gone
> deeply wrong — read this guide before any migration touches prod.

---

## 0. Tooling

- Migration tool: [Alembic](https://alembic.sqlalchemy.org/), pinned in
  [`pyproject.toml`](../../pyproject.toml) to `>=1.13,<2`.
- Config: [`alembic.ini`](../../alembic.ini) — the URL is intentionally
  blank; `env.py` reads `DATABASE_URL` from the runtime environment.
- Versions:
  [`backend/app/db/migrations/versions/`](../../backend/app/db/migrations/versions/).
  The only migration today is
  `20260516_0001_phase4_initial.py` (Phase 4 initial schema +
  Timescale hypertable setup for `telemetry` and `events`).

---

## 1. Creating a migration

Migrations are model-diff-generated; we never hand-edit DDL without
reading the diff.

```bash
# Edit backend/app/db/models.py (add a column, change a constraint, etc.)
make db-revision message="add unit serial column"
# inspect the generated file under backend/app/db/migrations/versions/
git add backend/app/db/migrations/versions/<file>
git commit -m "phase-N: db migration for <feature>"
```

After every revision: **read the autogen file**. Alembic sometimes
misses Timescale-specific concerns or partial-index conditions; this is
the failure mode that bit Phase 4 (see [`../STATUS.md`](../STATUS.md)
§"Phase 4 — post-readiness fixes").

### Timescale gotchas

- Every unique index on a Timescale hypertable **must include the
  partitioning column**. The Phase 4 `events` PK is `(id, ts)` for
  exactly this reason.
- `ALTER TABLE … ADD CONSTRAINT … UNIQUE` rewrites the index globally;
  on a multi-chunk hypertable this is expensive. Prefer adding the
  constraint at the chunk level via a Timescale-aware migration helper.
- Retention policies are owned by Alembic. Update the policy in the
  migration, not via psql; otherwise the next environment that runs
  `alembic upgrade head` will recreate the old policy.

---

## 2. No-downtime rules

For every column / constraint / index change, follow the
**additive-first, drop-later** pattern:

| Change                | Step 1 (additive)                          | Step 2 (drop, in a later migration) |
|-----------------------|--------------------------------------------|--------------------------------------|
| New required column   | Add as nullable + default                  | Backfill, then `ALTER … NOT NULL`    |
| Rename column         | Add new column + dual-write                | Drop old, after one release          |
| Drop column           | Stop reading in code, ship                 | Drop the column after one release    |
| Rename table          | Add view + dual-write                      | Drop old, after one release          |
| New index             | Use `CREATE INDEX CONCURRENTLY`            | n/a                                  |
| New FK on big table   | Add `NOT VALID` + `VALIDATE CONSTRAINT`    | n/a                                  |
| New unique constraint | Create `UNIQUE` index `CONCURRENTLY` first | `ADD CONSTRAINT … USING INDEX`       |

The rule: **never let an active code version + an active migration
produce mutually-incompatible state**. If the rollback path requires
re-adding a column, the migration was not additive-first.

---

## 3. Running a migration in production

The supported path is a **Job that runs migrations before the new
backend image rolls out**.

### Kubernetes

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: swarmos-migrate-v0.X.Y
  namespace: swarmos
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 1800
  template:
    spec:
      restartPolicy: Never
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
      containers:
        - name: migrate
          image: ghcr.io/<owner>/swarmos-backend@sha256:<digest>
          command: ["/opt/venv/bin/alembic", "upgrade", "head"]
          envFrom:
            - secretRef:
                name: swarmos
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities: { drop: [ALL] }
```

Apply the Job, wait for it to succeed, THEN `helm upgrade` the
Deployment. Helm hooks (`pre-upgrade`) automate this — the Phase 6.F
work will fold the hook into the chart; for now run it as a manual
two-step.

### compose-prod

`make db-migrate` against the deployed DATABASE_URL, ideally from inside
the backend container via:

```bash
docker compose -f docker-compose.prod.yml exec backend \
  /opt/venv/bin/alembic upgrade head
```

The `Makefile` `backend` target already depends on `db-migrate`, so a
plain `docker compose restart backend` will pick up new migrations on
container boot. **Do NOT rely on this for production** — boot-time
migrations on a busy DB can serialize behind connections; the explicit
exec above is safer.

### Worked example: Phase 4 initial migration

```bash
$ alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260516_0001, phase4 initial
INFO  [...] CREATE TABLE sessions
INFO  [...] CREATE TABLE events  (PRIMARY KEY (id, ts))
INFO  [...] CREATE TABLE telemetry
INFO  [...] CREATE TABLE missions
INFO  [...] CREATE TABLE anomalies
INFO  [...] CREATE TABLE operator_commands
INFO  [...] CREATE TABLE sector_visits
INFO  [...] SELECT create_hypertable('telemetry', 'ts', if_not_exists => TRUE)
INFO  [...] SELECT create_hypertable('events',    'ts', if_not_exists => TRUE)
INFO  [...] SELECT add_retention_policy('telemetry', INTERVAL '30 days')
```

Time: ~3 s on an empty DB. On a populated DB the hypertable conversion
runs in-place; budget 60 s per million existing rows in `telemetry`.

---

## 4. Rolling back

### Code rollback only

Most rollbacks DON'T need a downgrade — if the migrations were
additive-first (§2), the previous image works against the new schema.

```bash
helm rollback swarmos <previous-revision> -n swarmos
# DB untouched; previous image is happy because every column it reads
# still exists.
```

### Code + schema rollback

If the previous image really can't run against the new schema (you
violated §2), downgrade is one step at a time:

```bash
alembic downgrade -1
```

This reverses the most recent migration. Never `--sql` skip multiple
revisions on production — every step needs to apply atomically.

If the rollback target needs schema state that no longer exists, you
have to manually `pg_restore` from the most recent backup. That is the
"emergency procedure" path; in practice if you reach it, file a postmortem
on why the change wasn't additive-first.

---

## 5. Restore drill (quarterly)

Drone-day §2.E mandates a quarterly restore drill against a throwaway
DB. Procedure:

```bash
# 1. Pick a recent backup
ls -1tr /backups/swarm-*.sql.gpg | tail -1
dump=$(ls -1tr /backups/swarm-*.sql.gpg | tail -1)

# 2. Spin up a throwaway pg container
docker run --rm -d \
  -e POSTGRES_PASSWORD=throwaway \
  --name pg-drill \
  postgres:16-alpine

# 3. Restore
DATABASE_URL=postgres://postgres:throwaway@127.0.0.1:5432/postgres \
  scripts/restore_postgres.sh --i-understand-this-overwrites "$dump"

# 4. Sanity check
docker exec pg-drill psql -U postgres -c "\dt"
docker exec pg-drill psql -U postgres -c "SELECT count(*) FROM events;"

# 5. Tear down
docker stop pg-drill
```

Record the drill outcome (RTO, RPO, dump size, restore time) in
[`runbook.md`](runbook.md) when that file is produced in Phase 6.G.

---

## 6. Common pitfalls

- **Autogen missed a constraint**: re-run `alembic revision --autogenerate`
  with a clean DB state. Mixed-revision DBs produce misleading diffs.
- **`PostgresqlImpl` says "transactional DDL"**: Postgres runs each
  migration in a transaction by default. Migrations that mix DDL +
  long-running DML may need `op.execute("COMMIT")` to release locks.
- **Timescale hypertable creation deadlocks**: ensure no other
  transactions hold a lock on the source table when running
  `create_hypertable` — apply the migration in a maintenance window if
  the system is hot.
- **SQLite test path passes, production fails**: every test that
  exercises a constraint must run on both dialects via
  `backend/tests/test_alembic_migration.py`. The Phase 4 hypertable PK
  bug bit us here.
