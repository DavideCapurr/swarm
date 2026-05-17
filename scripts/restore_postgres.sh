#!/bin/sh
# SwarmOS Postgres restore script (Phase 6.E).
#
# Usage:
#   DATABASE_URL=postgres://user:pass@host:5432/db \
#   scripts/restore_postgres.sh --i-understand-this-overwrites <dump.sql.gpg>
#
# The `--i-understand-this-overwrites` flag is mandatory. Restoring a
# dump on top of a non-empty database is a foot-gun; we make it loud.
#
# Pipeline (reverse of backup_postgres.sh):
#   gpg --decrypt | pg_restore --clean --if-exists
#
# Drone-day §2.E expects a restore drill quarterly on a throwaway DB
# (not the production one). This script is the supported drill path.
set -eu

usage() {
    cat <<EOF
Usage: $0 --i-understand-this-overwrites <path-to-dump.sql.gpg>

Required env:
  DATABASE_URL  postgres connection string for the target DB

This will:
  - decrypt the dump with the gpg key in the current keyring
  - run pg_restore --clean --if-exists against DATABASE_URL
  - DROP and recreate every table/index present in the dump

It is **not safe** to point this at a production DB without prior
isolation. The flag is mandatory to prove you've read this.
EOF
    exit 64
}

if [ $# -lt 2 ]; then
    usage
fi

if [ "$1" != "--i-understand-this-overwrites" ]; then
    echo "[restore] FATAL: missing --i-understand-this-overwrites guard flag" >&2
    usage
fi

DUMP="$2"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

if [ ! -r "${DUMP}" ]; then
    echo "[restore] FATAL: cannot read ${DUMP}" >&2
    exit 1
fi

echo "[restore] decrypting ${DUMP}"
echo "[restore] target DATABASE_URL = ${DATABASE_URL%@*}@***"

# pg_restore reads from stdin when -d is given and the input format is
# custom (-Fc). Stream through gpg so no plaintext dump lands on disk.
gpg --batch --yes --decrypt "${DUMP}" \
  | pg_restore \
        --clean --if-exists \
        --no-owner --no-acl \
        --dbname "${DATABASE_URL}"

echo "[restore] done"
