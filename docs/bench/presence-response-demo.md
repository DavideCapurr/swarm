# Presence-response demo

This document defines the evidence boundary for SWARM's first payload-action
vertical slice.

The goal is not to claim a security product or physical intervention system.
The goal is to prove that SWARM can move beyond observation and issue a bounded,
auditable action to the selected autonomous unit.

## Domain loop

```text
restricted-area presence cue
        ↓
VERIFY mission
        ↓
fleet allocation / mission execution
        ↓
capture-ready ON_STATION state
        ↓
presence-response policy
        ↓
LIGHT_ON
PLAY_MESSAGE(restricted_area)
hold
STOP_MESSAGE
LIGHT_OFF
        ↓
mission continues to RTL
```

The response is deliberately non-force. It provides visibility and a
pre-approved informational message. It does not pursue, coerce, target, or use
force against a person.

## Proof levels

The implementation keeps flight proof, light-command proof, and speaker proof
separate.

| Capability | Visual simulator | PX4 SITL probe | Physical claim |
|---|---|---|---|
| VERIFY mission | simulated aircraft | MAVLink/PX4 mission path | none |
| Light command | `SIMULATED PAYLOAD` | `MAV_CMD_DO_SET_RELAY` must receive `COMMAND_ACK` | no lamp attached/proven |
| Speaker message | `SIMULATED PAYLOAD` | `SIMULATED PAYLOAD` | no speaker attached/proven |
| Cleanup | stop message + light off | relay-off must ACK | no hardware proof |
| Console visibility | typed EventFeed frames | code path separately tested | no field proof |

`MAV_CMD_DO_SET_RELAY` is part of the MAVLink common command set and PX4's
VehicleCommand interface. The repository still treats an ACK as protocol/SITL
evidence only, not evidence that a physical payload exists.

References:

- MAVLink common command set: https://mavlink.io/en/messages/common.html
- PX4 VehicleCommand: https://docs.px4.io/main/en/msg_docs/VehicleCommand
- PX4 v1.14 VehicleCommand used by the existing SITL evidence baseline:
  https://docs.px4.io/v1.14/en/msg_docs/VehicleCommand

## 1. Visual Console demo

Run:

```bash
bash scripts/demo_presence.sh
```

This reuses the existing restricted-area-person scenario as a technical fixture,
but boots `sim.swarm_sim.presence_runner` instead of changing the canonical sim
runner.

Expected sequence after the high-confidence presence reaches the verification
point:

1. SWARM dispatches a VERIFY mission through the existing allocator/orchestrator.
2. The first arrival-only `ON_STATION` state does **not** trigger the payload.
3. The capture-ready `ON_STATION` state crosses the configured progress gate.
4. The selected unit emits:
   - `light on · SIMULATED PAYLOAD`
   - `restricted-area message active · SIMULATED PAYLOAD`
5. The mission remains suspended on station for the configured hold period.
6. Cleanup emits:
   - `restricted-area message stopped · SIMULATED PAYLOAD`
   - `light off · SIMULATED PAYLOAD`
7. Only then may the mission generator continue to return-to-base.

The backend validates these payload events as strict `Event` models and forwards
them through the existing WebSocket/EventFeed path. The Console does not invent
payload state locally.

Environment knobs:

```text
SWARM_PRESENCE_MIN_CONFIDENCE   default 0.75
SWARM_PRESENCE_HOLD_S           default 5
```

## 2. PX4 SITL protocol gate

First start the same PX4 v1.14 SITL environment used by the existing Phase 9
validation. Then run:

```bash
.venv/bin/python scripts/presence_sitl_probe.py \
  --connection "${MAVLINK_CONNECTION:-udp:localhost:14540}" \
  --verify-lat 44.7 \
  --verify-lon 8.03 \
  --light-relay-index 0 \
  --json-out docs/bench/artifacts/presence-sitl-probe.json
```

The probe is green only if all required steps succeed:

1. PX4 heartbeat/health is live.
2. VERIFY reaches a terminal `DONE` phase.
3. `LIGHT_ON` produces an accepted MAVLink relay command.
4. The speaker state is explicitly reported as simulated and is both started
   and stopped.
5. `LIGHT_OFF` produces an accepted MAVLink relay command.
6. The complete presence sequence is observed in order before mission return.

If PX4 rejects or fails to ACK the relay command, the payload event records the
failure and the probe returns a non-zero exit code. Do not convert that failure
into a simulated success.

## Safety and truth invariants

- Presence response is opt-in. Existing wildfire/intrusion/search regression
  demos keep their current behavior.
- Only `AnomalyKind.INTRUSION` at or above the configured confidence threshold
  is eligible in this demo policy.
- Arrival alone is insufficient. The mission must cross the capture-ready
  progress gate.
- Payload capabilities are optional per agent. Missing capabilities are skipped,
  never fabricated.
- The message is selected from a closed catalogue. No generated/free-form audio
  enters the actuation path.
- Cancellation or exception during the hold runs cleanup in `finally`:
  `STOP_MESSAGE` then `LIGHT_OFF`.
- `MAVLink ACK` means the autopilot accepted the command. It does **not** mean a
  physical lamp or speaker has been field-validated.

## What this PR does not solve

This slice does not yet provide the final YC multi-vehicle PX4 demo. The current
backend MAVLink runner publishes one vehicle's telemetry/fleet state but is not
yet the same mission-execution runtime as the simulator orchestrator.

That distinction is intentional. This PR establishes the reusable payload action
contract and proves its two sides independently:

- allocation/policy/Console behavior in the visual multi-agent simulator;
- real MAVLink/PX4 command + ACK behavior in the SITL probe.

The next integration step is to make the multi-vehicle PX4 runtime use the same
orchestrator path, then the payload controller can be registered on those real
SITL adapters without changing the payload domain model.
