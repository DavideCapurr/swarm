# Phase 10 — live PX4 payload-response validation

Date: 2026-08-15

Status: **PASS**

This evidence closes the software/SITL part of the bounded presence-response path on the same backend runtime already used for multi-PX4 fleet coordination.

## What was run

GitHub Actions run: `31883512123`

Validated feature commit: `1e0b3feadcb6228277f51422709a8d7af648e1f0`

Artifact:

- ID: `9246647845`
- digest: `sha256:1a08a0a0553b9cc506ce175f5ee319859b08e0935f18990a6f1355b5f3e454df`

Permanent probe result: [`artifacts/phase10-payload-sitl-backend-probe.json`](artifacts/phase10-payload-sitl-backend-probe.json)

The gate ran:

- real Redis;
- real `uvicorn backend.app.main:app`;
- two PX4 v1.14 Gazebo Classic `iris` instances;
- one `MAVLinkFleetRunner`;
- one shared `AdapterRegistry`;
- one `PresenceResponseBusFleetOrchestrator`;
- an external Redis-only acceptance probe.

PX4 links:

- `mav-001`: PX4 instance 1 / MAV_SYS_ID 2, UDP remote 14541;
- `mav-002`: PX4 instance 2 / MAV_SYS_ID 3, UDP remote 14542.

Both fleet states reached the backend as `DOCKED` before the event was injected.

## Output configuration used by the SITL gate

The stock `iris` SITL configuration does not expose a ready-made light or relay payload. The gate therefore configured an unused flight-controller output before starting SWARM:

- `PWM_MAIN_FUNC5` was first verified to be disabled (`0`) on both PX4 instances;
- MAIN1–4 were never touched because they are motor outputs;
- MAIN5 was mapped to PX4 function `301`, **Offboard Actuator Set 1**;
- the parameter was written using PX4/MAVLink INT32 byte-wise parameter encoding;
- the gate read the value back as `301` on both instances before starting the backend.

Production code does not mutate flight-controller output mappings. That remains deployment/hardware configuration.

## Validated sequence

The external probe published:

- event kind: `INTRUSION`;
- confidence: `0.95`;
- target: `47.3980, 8.5460`.

SWARM then produced:

1. fleet auction;
2. winner `mav-002`;
3. `EN_ROUTE`;
4. final PX4 `MISSION_ITEM_REACHED` → SWARM `ON_STATION`;
5. light ON through `MAV_CMD_DO_SET_ACTUATOR` (`187`);
6. configured PX4 output observed in the ON state;
7. pre-approved restricted-area speaker message activated as **SIMULATED PAYLOAD**;
8. one-second bounded hold;
9. simulated speaker stopped;
10. light OFF through command `187`;
11. configured PX4 output observed in the OFF state;
12. mission resumed and closed `DONE` / RTL.

Total probe duration: **36.591 s**.

Observed mission phases:

`EN_ROUTE → ON_STATION → DONE`

Observed payload events, in order:

- `mav-002 light on · PX4 OUTPUT CONFIRMED`
- `mav-002 restricted-area message active · SIMULATED PAYLOAD`
- `mav-002 restricted-area message stopped · SIMULATED PAYLOAD`
- `mav-002 light off · PX4 OUTPUT CONFIRMED`

The probe additionally requires the final light-OFF confirmation to occur before the mission's `DONE` frame.

## Why output confirmation is used instead of COMMAND_ACK

An earlier implementation waited for `COMMAND_ACK` after `MAV_CMD_DO_SET_ACTUATOR`.
Live testing showed that this is the wrong proof condition for PX4 v1.14.

PX4's actuator-set mixer consumes `VEHICLE_CMD_DO_SET_ACTUATOR` directly from `vehicle_command`; this path does not produce the normal command ACK used by commands such as RTL or message-interval configuration.

The final implementation therefore verifies the configured flight-controller output through MAVLink telemetry instead of inventing or assuming an ACK.

This is stronger than merely recording that command `187` was sent.

## Evidence boundary

This run proves:

- the real multi-PX4 backend can apply the intrusion policy to the auction winner;
- payload action begins only after the reach-aware `ON_STATION` gate;
- SWARM can command a configured PX4 offboard actuator output ON and OFF;
- the configured flight-controller output state was observed after both commands;
- cleanup completes before the mission closes and RTL proceeds;
- payload events are server-owned and distinguish real PX4 output confirmation from simulated speaker state.

This run does **not** prove:

- a physical lamp, relay, speaker or amplifier was connected;
- electrical output voltage/current under physical load;
- a real aircraft payload installation;
- real audio playback from a drone;
- a field intrusion response;
- customer or regulatory validation.

The correct hardware claim remains: **PX4 SITL output-confirmed, physical payload hardware pending.**
