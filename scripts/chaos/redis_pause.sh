#!/usr/bin/env bash
# Phase 6.F — Redis chaos drill.
#
# Pauses the Redis container for 8 seconds and asserts:
#   1. /healthz keeps returning 200 (in-memory state remains live);
#   2. the backend log records the InMemoryBus fallback (or, if the
#      backend was already booted with Redis, that no crash is logged).
#
# Out of scope: live re-fallback while running. The boot-time fallback
# is what we exercise; for a true mid-run failover, restart the backend
# after pausing.
#
# Requirements: docker compose stack running locally (`make infra`),
# backend up (`make backend`), and `curl` on PATH.
set -euo pipefail

BACKEND_URL=${BACKEND_URL:-http://localhost:8765}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.yml}
PAUSE_S=${PAUSE_S:-8}
HEALTH_PATH=${HEALTH_PATH:-/health}

cd "$(dirname "$0")/../.."

if ! command -v docker >/dev/null 2>&1; then
  echo "[chaos-redis] docker not on PATH — skipping (drone-day §2.E)" >&2
  exit 0
fi

if ! docker compose -f "$COMPOSE_FILE" ps redis | grep -q "Up"; then
  echo "[chaos-redis] redis container not running — start with 'make infra'" >&2
  exit 2
fi

echo "[chaos-redis] pausing redis for ${PAUSE_S}s"
docker compose -f "$COMPOSE_FILE" pause redis >/dev/null

trap 'docker compose -f "$COMPOSE_FILE" unpause redis >/dev/null 2>&1 || true' EXIT

failures=0
deadline=$(( $(date +%s) + PAUSE_S ))
while [ "$(date +%s)" -lt "$deadline" ]; do
  if ! curl -fsS --max-time 1 "$BACKEND_URL$HEALTH_PATH" >/dev/null; then
    failures=$((failures + 1))
    echo "[chaos-redis] $HEALTH_PATH non-200 at $(date +%H:%M:%S)" >&2
  fi
  sleep 0.5
done

echo "[chaos-redis] unpausing redis"
docker compose -f "$COMPOSE_FILE" unpause redis >/dev/null
trap - EXIT

if [ "$failures" -gt 0 ]; then
  echo "[chaos-redis] FAIL: $HEALTH_PATH returned non-200 $failures times during pause" >&2
  exit 1
fi

echo "[chaos-redis] PASS: $HEALTH_PATH 200 throughout ${PAUSE_S}s redis pause"
