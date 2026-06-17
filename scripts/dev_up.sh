#!/usr/bin/env bash
# Boot the SWARM OS dev environment: infra → sim → backend → frontend.
#
# Run: ./scripts/dev_up.sh
# Stop: Ctrl+C

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/bootstrap_dev_env.sh

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
  if docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD}" ping > /dev/null 2>&1; then
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

# Phase 5: pick which vendor producers to launch. The simulator runs as a
# subprocess here; the mavlink runner runs in-process inside the backend
# (see backend/app/fleet.py). We never double-boot — the simulator is
# excluded from `IN_PROCESS_VENDORS` server-side, and the backend skips
# any vendor not in that set.
SWARM_VENDORS="${SWARM_VENDORS:-simulator}"
export SWARM_VENDORS
echo "[dev_up] SWARM_VENDORS=$SWARM_VENDORS"

# CV-live video sub-step: advertise the synthetic SIM-labelled drone-POV clip
# in the Console viewport, but only when the bundled clip is actually present
# (served same-origin by Next from frontend/public/sim-feed/). Without it the
# Console keeps the honest VIEWPORT PENDING placard. Set SWARM_SIM_FEED_PATH
# explicitly to override.
if [ -f frontend/public/sim-feed/drone-pov.mp4 ]; then
  export SWARM_SIM_FEED_PATH="${SWARM_SIM_FEED_PATH:-/sim-feed/drone-pov.mp4}"
  echo "[dev_up] SWARM_SIM_FEED_PATH=$SWARM_SIM_FEED_PATH (simulated viewport feed)"
fi

cleanup() {
  echo "[dev_up] stopping background processes…"
  kill $(jobs -p) 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Launch the simulator subprocess only if it appears in SWARM_VENDORS.
# Case-insensitive match against a comma-separated list.
SIM_PID=""
if [[ ",$(echo "$SWARM_VENDORS" | tr '[:upper:]' '[:lower:]')," == *,simulator,* ]]; then
  echo "[dev_up] starting sim runner…"
  python3 -m sim.swarm_sim.runner &
  SIM_PID=$!
fi

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
echo "          vendors:    $SWARM_VENDORS"
wait $SIM_PID $BACKEND_PID $FRONT_PID
