# Phase 5 bench validation evidence

Date: 2026-05-16
Branch: `codex/phase5-bench-security-gates`
Base commit: `35c36cc`

## Readiness state

| State | Result | Evidence |
|---|---|---|
| CI-ready | pass | `make lint`, `make test`, `make audit` pass in this worktree. |
| PX4 SITL-validated | pending | Probe could not connect to a PX4 HEARTBEAT on `udp:localhost:14540`. |
| Hardware-validated | pending | No USB telemetry device or real PX4 bench was available in this environment. |

## Commands and evidence

Environment prerequisite checks:

```bash
$ command -v px4 || true
# no output

$ test -d "$HOME/PX4-Autopilot" && echo "$HOME/PX4-Autopilot" || true
# no output

$ find /dev -maxdepth 1 \( -name 'ttyUSB*' -o -name 'tty.usb*' \) -print
# no output
```

SITL probe attempted:

```bash
$ .venv/bin/python scripts/phase5_sitl_probe.py \
    --json-out docs/bench/artifacts/2026-05-16-sitl-probe.json
```

Result: fail, exit code 2. The adapter timed out waiting for autopilot
`HEARTBEAT` on `udp:localhost:14540` after 5 seconds. Full artifact:
`docs/bench/artifacts/2026-05-16-sitl-probe.json`.

Because no PX4 SITL process was available, the mission-upload portion of the
acceptance gate was not run. Because no hardware/radio device was available,
hardware validation was not run.

## Human bench gate

Run these before marking Phase 5 SITL-validated:

```bash
cd /path/to/PX4-Autopilot
make px4_sitl_default jmavsim
```

In this repo, with the Python/frontend setup already installed:

```bash
MAVLINK_CONNECTION="udp:localhost:14540" \
MAVLINK_AGENT_ID="mav-px4-sitl" \
make phase5-sitl-gate

.venv/bin/python scripts/phase5_sitl_probe.py \
  --connection "udp:localhost:14540" \
  --agent-id "mav-px4-sitl" \
  --exercise-verify \
  --json-out docs/bench/artifacts/phase5-sitl-probe.json
```

Then boot the full stack and capture Redis/backend evidence:

```bash
SWARM_VENDORS=mavlink \
MAVLINK_CONNECTION="udp:localhost:14540" \
MAVLINK_AGENT_ID="mav-px4-sitl" \
./scripts/dev_up.sh

redis-cli SUBSCRIBE swarm:fleet:state swarm:telemetry:mav-px4-sitl
```

Do not mark hardware-validated until the real PX4 radio/USB bench checklist in
`docs/adapters/mavlink-setup.md` has command output or clear artifacts for the
exact commit under review.
