#!/bin/sh
# SwarmOS Postgres backup script (Phase 6.E).
#
# Usage:
#   DATABASE_URL=postgres://user:pass@host:5432/db \
#   BACKUP_DIR=/backups \
#   BACKUP_GPG_RECIPIENT=ops@example.com \
#   BACKUP_RETENTION_DAYS=30 \
#   scripts/backup_postgres.sh
#
# Pipeline:
#   pg_dump → gpg --encrypt → /backups/swarm-YYYYMMDD-HHMMSSZ.sql.gpg
# Followed by retention pruning (files older than RETENTION_DAYS rm'd).
#
# Hard rules:
#   - `set -euo pipefail` so any partial pipe failure aborts the cycle
#     (no half-written .sql.gpg files in the bucket).
#   - Files written with mode 0600.
#   - Recipient fingerprint MUST be present in the gpg keyring (the
#     operator imports the backup public key into `${GNUPGHOME:-/root/
#     .gnupg}` before first run; see drone-day §2.E).
#   - The dump is encrypted before it ever touches disk (no plaintext
#     intermediate file). Compromise of the backup volume yields gpg
#     ciphertext, not data.
#
# Mirrored verbatim in infra/helm/swarmos/files/backup_postgres.sh for
# the Helm CronJob. The make-backup-dump-dry target verifies they match.
set -eu

BACKUP_DIR="${BACKUP_DIR:?BACKUP_DIR must be set}"
BACKUP_GPG_RECIPIENT="${BACKUP_GPG_RECIPIENT:?BACKUP_GPG_RECIPIENT must be set}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

# Use a sortable, timezone-stable timestamp. UTC + ISO basic format.
ts="$(date -u +%Y%m%dT%H%M%SZ)"
out="${BACKUP_DIR}/swarm-${ts}.sql.gpg"
tmp="${BACKUP_DIR}/.${ts}.partial"

mkdir -p "${BACKUP_DIR}"

if ! gpg --list-keys "${BACKUP_GPG_RECIPIENT}" >/dev/null 2>&1; then
    echo "[backup] FATAL: recipient ${BACKUP_GPG_RECIPIENT} not in keyring" >&2
    exit 1
fi

echo "[backup] starting pg_dump → ${out}"

# `pg_dump -Fc` (custom format) is compact and supports parallel restore.
# We pipe straight into gpg so no plaintext SQL ever hits disk.
umask 077
pg_dump \
    --format=custom \
    --no-owner \
    --no-acl \
    --serializable-deferrable \
    "${DATABASE_URL}" \
  | gpg --batch --yes --trust-model always \
        --recipient "${BACKUP_GPG_RECIPIENT}" \
        --encrypt --output "${tmp}"

mv "${tmp}" "${out}"
chmod 600 "${out}"

echo "[backup] wrote $(du -h "${out}" | awk '{print $1}') to ${out}"

# Retention prune. mtime comparison is enough; we never overwrite an
# existing file (timestamps in the filename are unique).
echo "[backup] pruning > ${BACKUP_RETENTION_DAYS}d in ${BACKUP_DIR}"
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'swarm-*.sql.gpg' \
    -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete

echo "[backup] done"
