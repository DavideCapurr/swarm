#!/usr/bin/env bash
# Phase 7.E — thin wrapper kept for backward compatibility with `make demo`
# and any operator muscle memory. The real boot path is
# scripts/demo_scenario.sh; this script just delegates the wildfire YAML.

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/demo_scenario.sh" \
  "$ROOT/sim/scenarios/wildfire_owner_land.yaml" "$@"
