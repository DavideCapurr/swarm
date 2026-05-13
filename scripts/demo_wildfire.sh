#!/usr/bin/env bash
# Scripted wildfire scenario.
#
# Boots infra + sim + backend + frontend with an ignition pre-scheduled at
# t=10 s. Open http://localhost:3000 within 30 s of running this and watch the
# anomaly → auction → verify → RTL cycle.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export SIM_DRONES=3
export SIM_IGNITION_AT_S=10
export SIM_TICK_HZ=10

exec ./scripts/dev_up.sh
