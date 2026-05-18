#!/usr/bin/env bash
# Phase 6.F — backend SIGTERM chaos drill.
#
# Asserts the Console reconnect path recovers within 6 s of a backend
# SIGTERM + restart cycle:
#
#   1. Find the running uvicorn process (`pgrep -f backend.app.main`).
#   2. Start a ws_probe in --watch mode so the close event is timed.
#   3. SIGTERM the backend, wait for the probe to confirm close.
#   4. Start uvicorn again in the background.
#   5. Run a reconnect probe; assert RECONNECT_MS <= 6000.
#
# Requires: `make backend` already running, `make bootstrap-auth-dev`
# already run so the dev viewer account exists.
set -euo pipefail

BACKEND_URL=${BACKEND_URL:-http://localhost:8765}
WS_URL=${WS_URL:-ws://localhost:8765/ws/telemetry}
USER_ID=${SWARM_LOAD_USER:-op-viewer01}
PASSWORD=${SWARM_LOAD_PASSWORD:-swarm-dev}
SLO_MS=${SLO_MS:-6000}

cd "$(dirname "$0")/../.."

if ! command -v curl >/dev/null 2>&1; then
  echo "[chaos-backend] curl not on PATH" >&2
  exit 2
fi
if [ ! -x .venv/bin/python ]; then
  echo "[chaos-backend] .venv missing — run 'make setup' first" >&2
  exit 2
fi

login_body=$(printf '{"operator_id":"%s","password":"%s"}' "$USER_ID" "$PASSWORD")
token=$(curl -fsS -X POST "$BACKEND_URL/auth/login" \
          -H 'Content-Type: application/json' \
          -d "$login_body" \
          | .venv/bin/python -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

if [ -z "$token" ]; then
  echo "[chaos-backend] login returned empty token" >&2
  exit 2
fi

pid=$(pgrep -f "backend.app.main" | head -n1 || true)
if [ -z "$pid" ]; then
  echo "[chaos-backend] no backend.app.main process found — start 'make backend'" >&2
  exit 2
fi
echo "[chaos-backend] target backend pid=$pid"

# Start the watcher in background, give it a beat to connect.
watch_log=$(mktemp)
.venv/bin/python -m tests.chaos.ws_probe \
  --url "$WS_URL" --token "$token" --mode watch --deadline 30 \
  >"$watch_log" 2>&1 &
watch_pid=$!
sleep 1.0

echo "[chaos-backend] SIGTERM $pid"
kill -TERM "$pid"

# Wait for the watcher to either record the close or time out.
wait "$watch_pid" || true
if ! grep -q "CLOSE_DETECTED=1" "$watch_log"; then
  cat "$watch_log" >&2
  echo "[chaos-backend] FAIL: watcher did not see the close" >&2
  rm -f "$watch_log"
  exit 1
fi
rm -f "$watch_log"

echo "[chaos-backend] restarting backend (background)"
nohup .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port 8765 \
  >/tmp/chaos-backend.out 2>&1 &
restart_pid=$!
disown "$restart_pid" || true

# Reconnect probe — fails non-zero if SLO breached.
.venv/bin/python -m tests.chaos.ws_probe \
  --url "$WS_URL" --token "$token" --mode reconnect \
  --deadline 15 --slo-ms "$SLO_MS"

echo "[chaos-backend] PASS: reconnect within ${SLO_MS} ms"
