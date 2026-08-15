#!/usr/bin/env bash
# Investor/demo cut: restricted-area presence -> VERIFY -> light + message.
#
# Run through bash so this file does not depend on executable-bit handling from
# the GitHub contents API:
#   bash scripts/demo_presence.sh
#
# Additional demo_scenario args are forwarded, e.g.:
#   bash scripts/demo_presence.sh --metrics --duration 45

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export SWARM_SIM_RUNNER_MODULE="sim.swarm_sim.presence_runner"
export SWARM_PRESENCE_HOLD_S="${SWARM_PRESENCE_HOLD_S:-5}"
export SWARM_PRESENCE_MIN_CONFIDENCE="${SWARM_PRESENCE_MIN_CONFIDENCE:-0.75}"

exec bash ./scripts/demo_scenario.sh sim/scenarios/intrusion_owner_land.yaml "$@"
