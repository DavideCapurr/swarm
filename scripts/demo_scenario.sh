#!/usr/bin/env bash
# Phase 7.E — boot a SwarmOS scenario end-to-end.
#
# Usage:
#   ./scripts/demo_scenario.sh <scenario-yaml> [--metrics] [--duration SECONDS]
#
# The scenario YAML is loaded by sim/swarm_sim/runner.py via the
# SIM_SCENARIO env var; everything else (infra, sim subprocess, backend,
# Console) is delegated to scripts/dev_up.sh. When --metrics is passed,
# scripts/scenario_metrics.py runs in the background and snapshots the
# audit log into docs/bench/artifacts/ after --duration seconds.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <scenario-yaml> [--metrics] [--duration SECONDS]" >&2
  exit 2
fi

SCENARIO_PATH="$1"
shift

if [ ! -f "$SCENARIO_PATH" ]; then
  echo "[demo_scenario] scenario file not found: $SCENARIO_PATH" >&2
  exit 2
fi

METRICS=0
DURATION="${SWARM_DEMO_METRICS_DURATION:-60}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --metrics) METRICS=1; shift ;;
    --duration) DURATION="$2"; shift 2 ;;
    *) echo "[demo_scenario] unknown arg: $1" >&2; exit 2 ;;
  esac
done

export SIM_SCENARIO="$SCENARIO_PATH"
echo "[demo_scenario] SIM_SCENARIO=$SIM_SCENARIO"

if [ "$METRICS" -eq 1 ]; then
  if [ ! -d .venv ]; then
    echo "[demo_scenario] .venv not found — run \`make setup\` first" >&2
    exit 1
  fi
  SCENARIO_ID="$(basename "$SCENARIO_PATH" .yaml)"
  echo "[demo_scenario] metrics collector will snapshot $SCENARIO_ID after ${DURATION}s"
  ( \
    .venv/bin/python "$ROOT/scripts/scenario_metrics.py" \
      --scenario "$SCENARIO_ID" \
      --duration "$DURATION" \
      --backend "http://localhost:${BACKEND_PORT:-8765}" \
    & \
  )
fi

exec ./scripts/dev_up.sh
