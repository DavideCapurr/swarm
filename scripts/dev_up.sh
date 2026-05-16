#!/usr/bin/env bash
# Boot the SWARM OS dev environment: infra → sim → backend → frontend.
#
# Run: ./scripts/dev_up.sh
# Stop: Ctrl+C

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "[dev_up] created .env from .env.example"
fi

# One-shot migration: port 8000 collides with other local dev servers, so we
# moved the backend to 8765. Rewrite stale .env values in place.
if grep -qE '(BACKEND_PORT=8000|localhost:8000)' .env; then
  sed -i.bak \
    -e 's|^BACKEND_PORT=8000$|BACKEND_PORT=8765|' \
    -e 's|http://localhost:8000|http://localhost:8765|g' \
    -e 's|ws://localhost:8000|ws://localhost:8765|g' \
    .env
  echo "[dev_up] migrated .env: backend port 8000 → 8765 (backup at .env.bak)"
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

# Activate venv if present.
if [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "[dev_up] bringing up infra (postgres + redis)…"
docker compose up -d postgres redis

# Wait for redis to accept connections.
for i in $(seq 1 20); do
  if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Wait for postgres + run Alembic migrations (Phase 4).
for i in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U "${POSTGRES_USER:-swarm}" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if [ -d .venv ]; then
  echo "[dev_up] running Alembic migrations…"
  # Fail-fast: a broken schema means the backend would serve stale data and
  # the audit log would silently drop rows. Surface the failure now.
  .venv/bin/alembic upgrade head
fi

cleanup() {
  echo "[dev_up] stopping background processes…"
  kill $(jobs -p) 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[dev_up] starting sim runner…"
python3 -m sim.swarm_sim.runner &
SIM_PID=$!

echo "[dev_up] starting backend (FastAPI)…"
uvicorn backend.app.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8765}" &
BACKEND_PID=$!

echo "[dev_up] starting frontend (Next.js)…"
(cd frontend && corepack pnpm dev) &
FRONT_PID=$!

echo "[dev_up] all services running."
echo "          dashboard:  http://localhost:3000"
echo "          backend:    http://localhost:${BACKEND_PORT:-8765}/health"
echo "          ws:         ws://localhost:${BACKEND_PORT:-8765}/ws/telemetry"
wait $SIM_PID $BACKEND_PID $FRONT_PID
