#!/usr/bin/env bash
# Scripted wildfire scenario.
#
# Boots infra + sim + backend + frontend with an ignition pre-scheduled at
# t=10 s. Open http://localhost:3000 within 30 s of running this and watch the
# anomaly → auction → verify → RTL cycle.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Phase 7.A: scenario YAML is the primary path. When SIM_SCENARIO is set,
# SIM_DRONES / SIM_IGNITION_AT_S / SIM_TICK_HZ are ignored by the runner
# (kept here for back-compat with anyone unsetting SIM_SCENARIO manually).
export SIM_SCENARIO="${SIM_SCENARIO:-sim/scenarios/wildfire_owner_land.yaml}"
export SIM_DRONES=3
export SIM_IGNITION_AT_S=10
export SIM_TICK_HZ=10

exec ./scripts/dev_up.sh
