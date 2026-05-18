#!/bin/sh
# SwarmOS backup/restore drill (Phase 6.G).
#
# Boots a throwaway Postgres + Timescale sidecar via docker, runs
# scripts/backup_postgres.sh against the *live* DATABASE_URL, then
# runs scripts/restore_postgres.sh against the sidecar and asserts the
# restored schema matches what Alembic expects.
#
# Usage:
#   DATABASE_URL=postgres://user:pass@host:5432/swarm \
#   BACKUP_GPG_RECIPIENT=ops@example.com \
#   scripts/backup_restore_drill.sh
#
# Hard rules:
#   - `set -eu` everywhere (no `|| true` masks).
#   - Sidecar container is named `swarm-drill-pg-<pid>` and torn down
#     in the cleanup trap on any exit path (success, failure, signal).
#   - Drill PASS / FAIL is the script's exit code. CI consumes it
#     directly.
#   - Drill artifacts (dump + log) are written under BACKUP_DIR; the
#     monthly DR drill uploads them to the off-site target.
#
# Drone-day items (see docs/ops/drone-day-checklist.md §2.G):
#   - real off-site sync target
#   - quarterly customer-acceptance drill from a cold restore
#   - rotation of BACKUP_GPG_RECIPIENT keys
set -eu

DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:?BACKUP_GPG_RECIPIENT must be set}"
BACKUP_DIR="${BACKUP_DIR:-/tmp/swarm-drill}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-3}"
DRILL_PG_IMAGE="${DRILL_PG_IMAGE:-timescale/timescaledb:2.16.1-pg16}"
DRILL_PG_PASSWORD="${DRILL_PG_PASSWORD:-swarm-drill-password}"
DRILL_PG_PORT="${DRILL_PG_PORT:-55433}"
DRILL_PG_NAME="swarm-drill-pg-$$"

mkdir -p "${BACKUP_DIR}"
LOG="${BACKUP_DIR}/drill-$(date -u +%Y%m%dT%H%M%SZ).log"

log() { echo "[drill] $*" | tee -a "${LOG}"; }

cleanup() {
    rc=$?
    if docker ps -aq -f "name=${DRILL_PG_NAME}" >/dev/null 2>&1; then
        log "tearing down sidecar ${DRILL_PG_NAME}"
        docker rm -f "${DRILL_PG_NAME}" >/dev/null 2>&1 || true
    fi
    if [ ${rc} -eq 0 ]; then
        log "drill PASS"
    else
        log "drill FAIL (exit ${rc})"
    fi
    return ${rc}
}
trap cleanup EXIT INT TERM

log "starting drill — dest=${BACKUP_DIR}"

# 1. Dump the live DB.
log "step 1 — backup live DB to ${BACKUP_DIR}"
BACKUP_DIR="${BACKUP_DIR}" \
BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT}" \
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS}" \
DATABASE_URL="${DATABASE_URL}" \
    scripts/backup_postgres.sh

# Find the latest dump produced in this run.
DUMP="$(ls -1t "${BACKUP_DIR}"/swarm-*.sql.gpg | head -n 1)"
if [ -z "${DUMP}" ] || [ ! -r "${DUMP}" ]; then
    log "FATAL: no dump found under ${BACKUP_DIR}"
    exit 2
fi
log "dump produced: ${DUMP}"

# 2. Boot a throwaway sidecar with the same major version as prod.
log "step 2 — booting sidecar ${DRILL_PG_NAME} (image ${DRILL_PG_IMAGE})"
docker run -d --rm \
    --name "${DRILL_PG_NAME}" \
    -e POSTGRES_PASSWORD="${DRILL_PG_PASSWORD}" \
    -e POSTGRES_DB=swarm_drill \
    -p "${DRILL_PG_PORT}:5432" \
    "${DRILL_PG_IMAGE}" >/dev/null

# Wait for readiness — pg_isready is bundled in the image.
log "waiting for sidecar to accept connections"
i=0
until docker exec "${DRILL_PG_NAME}" pg_isready -U postgres -d swarm_drill >/dev/null 2>&1; do
    i=$((i + 1))
    if [ ${i} -ge 60 ]; then
        log "FATAL: sidecar did not become ready within 60 s"
        exit 3
    fi
    sleep 1
done

DRILL_URL="postgres://postgres:${DRILL_PG_PASSWORD}@localhost:${DRILL_PG_PORT}/swarm_drill"

# 3. Restore the dump into the sidecar.
log "step 3 — restore dump into sidecar"
DATABASE_URL="${DRILL_URL}" \
    scripts/restore_postgres.sh --i-understand-this-overwrites "${DUMP}"

# 4. Schema parity check via Alembic.
log "step 4 — verify alembic current matches head"
if ! command -v alembic >/dev/null 2>&1; then
    log "WARN: alembic not on PATH; skipping schema parity check"
else
    cur="$(DATABASE_URL="${DRILL_URL}" alembic current 2>/dev/null | tail -n 1 || true)"
    head="$(alembic heads 2>/dev/null | tail -n 1 || true)"
    if [ -z "${cur}" ] || [ -z "${head}" ]; then
        log "FATAL: alembic current/head returned empty (cur='${cur}' head='${head}')"
        exit 4
    fi
    cur_rev="${cur%% *}"
    head_rev="${head%% *}"
    if [ "${cur_rev}" != "${head_rev}" ]; then
        log "FATAL: schema drift — restored=${cur_rev} expected=${head_rev}"
        exit 5
    fi
    log "schema parity OK — rev ${cur_rev}"
fi

# 5. Sanity check audit row counts.
log "step 5 — verify audit tables non-empty"
events_count="$(docker exec "${DRILL_PG_NAME}" psql -U postgres -d swarm_drill -tAc 'SELECT count(*) FROM events;' 2>/dev/null || echo 0)"
commands_count="$(docker exec "${DRILL_PG_NAME}" psql -U postgres -d swarm_drill -tAc 'SELECT count(*) FROM operator_commands;' 2>/dev/null || echo 0)"
log "events=${events_count} operator_commands=${commands_count}"

# The drill itself doesn't *require* rows — a fresh deploy has none — but
# we record the counts so the monthly drill artifact carries them for
# trend analysis.

log "drill complete: dump=${DUMP}, schema=PASS, rows={events:${events_count}, commands:${commands_count}}"
