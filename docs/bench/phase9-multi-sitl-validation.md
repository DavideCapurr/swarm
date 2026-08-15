# Phase 9 multi-SITL validation — backend-owned SWARM orchestration

Date: 2026-08-15
PR: #123 (`agent/mavlink-multi-agent-orchestrator`)
Validated feature commit: `24f788a14655c35cd2591e63798116887dd10356`
GitHub Actions run: `31856642970`
Artifact: `9239256725`
Artifact digest: `sha256:59df20f42c0b6951e7fd301fdb0e1c3f869c0d94ea67a8ab74e534135be59bed`
Permanent probe evidence: [`artifacts/phase9-multi-sitl-backend-probe.json`](artifacts/phase9-multi-sitl-backend-probe.json)

## Result

**PASS — two live PX4 v1.14 SITL vehicles were visible to one real backend process, auctioned by SWARM, and the winning vehicle reached the verification waypoint before SWARM commanded RTL.**

This is stronger than the June single-aircraft SITL gate. It validates the actual backend lifecycle introduced in PR #123:

`PX4 #1 + PX4 #2 → MAVLinkFleetRunner → AdapterRegistry → FleetState → BusFleetOrchestrator → auction → winner.execute_mission() → MISSION_ITEM_REACHED → RTL`

It is still SITL evidence, not hardware or field-flight evidence.

## Setup

The workflow ran on Linux with the same pinned PX4/Gazebo image already used by the project:

- PX4 image: `jonasvautherin/px4-gazebo-headless@sha256:77f11913cbb2c4e9147a0ec0fdc4318e9575515e20e88d1f3cd9a21470ddcd21`
- PX4: v1.14.0
- vehicle: Gazebo Classic `iris`
- world: `empty`
- instances: 2
- Redis: real Redis service
- backend: real `uvicorn backend.app.main:app`
- backend vendors: `SWARM_VENDORS=mavlink`
- fleet configuration:

```bash
MAVLINK_FLEET='mav-001=udpin:0.0.0.0:14541,mav-002=udpin:0.0.0.0:14542'
```

PX4 instance 1 reported MAV_SYS_ID 2 and its Onboard MAVLink link as local UDP 14581 → remote 14541.
PX4 instance 2 reported MAV_SYS_ID 3 and its Onboard MAVLink link as local UDP 14582 → remote 14542.
Both independent heartbeat gates passed before the SWARM backend was started.

## Acceptance sequence

The external probe does not import backend internals. It only uses Redis bus topics, as an external perception source would.

1. Wait for `FleetState` for both `mav-001` and `mav-002`.
2. Publish one `INTRUSION` anomaly at 47.3980, 8.5460 with confidence 0.95.
3. Observe the SWARM mission award.
4. Observe mission progress for the awarded mission.
5. Pass only if the mission reaches `EN_ROUTE → ON_STATION → DONE`.

Observed result:

- both units: `DOCKED`, battery 100%, live MAVLink telemetry;
- winner: `mav-002`;
- auction score: `2.2583257083428623`;
- mission ID: `e09a8b34e055423f85d11751a4313309`;
- mission phases: `EN_ROUTE → ON_STATION → DONE`;
- probe duration: **35.682 s**.

## Why `ON_STATION` is meaningful now

The first live multi-SITL attempt exposed a false-completion bug in the original Phase 5 adapter: for a one-waypoint mission, PX4 can report `MISSION_CURRENT=0` immediately after mission start. The adapter treated that cursor as if waypoint 0 had already been reached and returned `ON_STATION → RTL → DONE` in about 1.3 seconds.

PR #123 adds `ReachAwareMAVLinkAdapter` for the backend fleet runtime:

- `MISSION_CURRENT` means progress only;
- `MISSION_ITEM_REACHED` is the only waypoint-completion proof;
- final `ON_STATION` is emitted only after the final `MISSION_ITEM_REACHED`;
- deadline expiry causes `RTL + FAILED`, never a false `DONE`.

The corrected live run took 35.682 seconds. PX4's winning-instance log shows:

- `Armed by external command`;
- `Takeoff to 40.0 meters above home`;
- `Takeoff detected`;
- `Mission finished, loitering`;
- `Returning to launch`;
- `RTL HOME activated`;
- `RTL: landing at home position`.

The sequence is consistent with the adapter's stricter state machine: SWARM did not issue RTL until the final waypoint-reached event had been observed.

## Deadline bug also discovered and fixed

The stricter completion semantics exposed a second issue. The base deadline calculation only summed distances *between* mission waypoints. A single-waypoint VERIFY therefore received the fixed 30-second floor while ignoring:

- current aircraft position → first waypoint distance;
- climb from current altitude to target relative altitude.

In the first reach-aware live run, PX4 was still executing the mission at 30 seconds, so SWARM correctly failed closed and commanded RTL with:

`mission deadline exceeded before final waypoint reached`

The backend reach-aware adapter now adds a conservative allowance for the initial horizontal leg and climb to implicit deadlines. Explicit `timeout_s` values remain operator-controlled and are not inflated.

The same unchanged 40 m mission then passed live.

## Validation layers

Before the final live run, the workflow also passed:

- Ruff;
- strict mypy over `core adapters orchestrator sim backend` plus the probe;
- reach-aware MAVLink regression tests;
- multi-unit fleet-runner tests;
- bus-backed orchestrator tests;
- two-fake-autopilot backend integration tests.

The regression suite explicitly proves that `MISSION_CURRENT=0` without `MISSION_ITEM_REACHED` cannot complete a one-waypoint VERIFY and that deadline expiry returns `FAILED` + RTL.

## What this proves

- Two separate PX4 autopilot instances can coexist behind one SWARM backend.
- Both become canonical `FleetState` inputs to the same orchestrator.
- SWARM performs one fleet-level auction and chooses one winner.
- The winning real PX4 SITL instance receives and executes the MAVLink mission path.
- SWARM does not claim `ON_STATION` until PX4 reports the final mission item reached.
- SWARM then commands RTL and closes the mission only after the RTL command is accepted.

## What this does not prove

- No physical aircraft flew.
- No motors, ESCs, GPS hardware, RC/radio link, dock or payload hardware were validated.
- No mixed simulator + real-MAVLink fleet is orchestrated in one runtime yet. That mode is intentionally disabled to avoid duplicate anomaly consumers.
- No payload action from PR #122 is composed into this real multi-PX4 path yet.
- No customer workflow or field pilot is validated by this technical evidence.

## Next technical composition

The next high-leverage engineering step is not another generic adapter. It is to rebase/compose PR #122 onto this runtime so the same real sequence becomes:

`event → fleet auction → winning PX4 reaches target → verified ON_STATION → bounded payload action → RTL`

After that, the next evidence jump is hardware, not more simulator infrastructure.
