# Payload presence-response validation — real backend + two PX4 SITL vehicles

Date: 2026-08-15
PR: #126 (`agent/payload-runtime-integration`)
Validated feature commit: `e07dd267cb0fd131ecb1e5a695415fc75b9be45b`
Targeted runtime run: `31883256167`
Live PX4 run: `31883256128`
Live artifact: `9246593798`
Artifact digest: `sha256:42fb8d8df68ce634ca10ba6bf1140fbbd0b9b1d04c7d3abf52345ef0dc64a967`
Permanent probe evidence: [`artifacts/payload-presence-sitl-backend-probe.json`](artifacts/payload-presence-sitl-backend-probe.json)

## Result

**PASS — the bounded payload response is composed into the same backend-owned multi-PX4 mission lifecycle already used for fleet auction, reach-aware arrival and RTL.**

The live sequence was:

`INTRUSION → fleet auction → mav-002 → EN_ROUTE → final MISSION_ITEM_REACHED → ON_STATION → light output ON confirmed → simulated speaker message → cleanup → light output OFF confirmed → RTL/DONE`

The probe completed in **36.912 s**.

This is stronger than a command-transmission test. The light action is not reported as successful merely because SWARM sends a MAVLink command. The runtime waits until the configured PX4 output is observed in the requested state.

It is still SITL evidence. It is not proof that a physical lamp, driver, cable or aircraft payload exists.

## Setup

The workflow used the same live PX4 v1.14 / Gazebo Classic environment as the existing multi-SITL backend proof:

- two independent PX4 v1.14 `iris` instances;
- real Redis service;
- real FastAPI backend lifecycle;
- `SWARM_VENDORS=mavlink`;
- `mav-001=udpin:0.0.0.0:14541`;
- `mav-002=udpin:0.0.0.0:14542`;
- presence response explicitly enabled;
- speaker explicitly marked as simulated.

Before starting the backend, the workflow verifies that `PWM_MAIN_FUNC5` is unused on each PX4 instance, maps it to function `301` (`Offboard Actuator Set 1`) and re-checks both heartbeats. It refuses to overwrite a non-zero, non-301 output function.

The SWARM payload configuration for the run was:

```text
MAVLINK_LIGHT_ACTUATOR_NUMBER=1
MAVLINK_LIGHT_OUTPUT_CHANNEL=5
SWARM_PRESENCE_SIMULATE_SPEAKER=1
SWARM_PRESENCE_HOLD_S=1
```

## Why the light evidence is output-confirmed, not ACK-confirmed

The first implementation inherited relay control from the older payload proof. Live PX4 rejected `MAV_CMD_DO_SET_RELAY` as unsupported.

The next implementation moved to the generic PX4 actuator path, `MAV_CMD_DO_SET_ACTUATOR` (wire command id 187). That exposed an important evidence issue: PX4 v1.14 routes this generic command through its `vehicle_command` path rather than returning the direct `COMMAND_ACK` that SWARM's generic command helper expects.

Waiting for a nonexistent direct ACK therefore produced a timeout even though the command was valid for the PX4 actuator-set path.

The final runtime does not weaken the check to fire-and-forget. Instead it:

1. requests `SERVO_OUTPUT_RAW` from PX4;
2. sends `MAV_CMD_DO_SET_ACTUATOR` for actuator set 1;
3. waits for MAIN5 to enter the expected high or low PWM range;
4. emits `PX4 OUTPUT CONFIRMED` only after that observation;
5. fails the payload action if the configured output is not observed before the response timeout.

This keeps the evidence boundary explicit:

- **PX4 OUTPUT CONFIRMED** = flight-controller command-to-output path observed;
- **SIMULATED PAYLOAD** = demo-only side effect with no MAVLink hardware proof;
- neither label means physical payload hardware was bench-tested.

## Observed live sequence

Both PX4 units became canonical fleet inputs in `DOCKED` state with live telemetry.

The anomaly had confidence `0.95` and target `47.3980, 8.5460`.

SWARM awarded mission `3b5ed5fa3be543e0862703adc792c401` to `mav-002` with score `2.2583195560361817`.

Observed ordering from the external Redis probe:

1. award → `mav-002`;
2. `EN_ROUTE`;
3. `ON_STATION` at `11:57:46.844859Z`;
4. `mav-002 light on · PX4 OUTPUT CONFIRMED`;
5. `mav-002 restricted-area message active · SIMULATED PAYLOAD`;
6. `mav-002 restricted-area message stopped · SIMULATED PAYLOAD`;
7. `mav-002 light off · PX4 OUTPUT CONFIRMED`;
8. `DONE` at `11:57:48.042179Z`.

Because the reach-aware adapter only emits `ON_STATION` after the final `MISSION_ITEM_REACHED`, and because its async generator is paused while the payload policy executes, the live run proves that cleanup completed before the adapter resumed to its RTL/DONE closure.

## Software regression gate

The same feature commit also passed the targeted software gate in run `31883256167`:

- Ruff: pass;
- strict mypy over `core adapters orchestrator sim backend`: pass;
- **30 targeted payload + fleet + mission-runtime + dynamic-reallocation tests: pass**.

Those tests include a fake PX4 endpoint that deliberately does **not** ACK command 187 and instead confirms state through `SERVO_OUTPUT_RAW`, matching the live v1.14 semantics used by the feature.

## What this proves

- Payload response is part of the real backend-owned fleet runtime, not a second demo runner.
- The normal fleet auction still selects the responding PX4.
- The payload policy cannot start before the reach-aware `ON_STATION` gate.
- A PX4 generic actuator output can be configured and controlled by SWARM in live SITL.
- Light ON and OFF are reported only after the configured PX4 output is observed in the requested state.
- Speaker behavior remains explicitly simulated and cannot be confused with hardware proof.
- Cleanup completes before RTL/DONE.
- Existing mission-runtime and dynamic-reallocation behavior remains regression-tested.

## What this does not prove

- No physical aircraft flew.
- No physical light, driver, GPIO/PWM cable or power stage was tested.
- No real speaker or audio transport was tested.
- No customer workflow or field pilot is validated by this technical proof.
- The current light mapping is a configured PX4 capability, not a claim that every MAVLink vehicle exposes the same output mapping.

## Next technical evidence

Do not build another payload demo path.

The next demo-facing technical work should make the already-validated fleet decisions obvious in the existing Console: structured allocation reasons, busy/excluded units, winner/score and concurrent active missions.

The next major evidence jump after that is physical bench/flight proof using the same runtime and a real mapped output, not more simulator-only payload abstractions.
