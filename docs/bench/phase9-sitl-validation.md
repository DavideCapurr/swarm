# Phase 9 SITL validation evidence — MAVLink/PX4 adapter

Date: 2026-06-24
Branch: `feat/px4-sitl-evidence`
Base commit: `72499ba`

This closes the gap left by the 2026-05-16 attempt
(`docs/bench/artifacts/2026-05-16-sitl-probe.json`), which failed because **no
PX4 process was emitting HEARTBEAT** on the MAVLink UDP endpoint. Here a real
PX4 SITL autopilot was launched, connected to, flown through a VERIFY mission,
and commanded home — all captured in a green probe artifact.

## Readiness state

| State | Result | Evidence |
|---|---|---|
| CI-ready | pass | `make lint`, `make test`, `make audit` green; probe logic unit-tested against `FakeMAVLinkEndpoint` (`tests/test_phase9_sitl_probe.py`). |
| PX4 SITL-validated | **pass** | Live PX4 v1.14.0 SITL run. Artifact: [`artifacts/phase9-sitl-probe.json`](artifacts/phase9-sitl-probe.json) — `status: "pass"`, 5/5 gate steps. |
| Hardware-validated | pending | No PX4 flight controller / radio / airframe was available. SITL is **not** flight proof. |

**Typed claim:** the MAVLink/PX4 adapter is **SITL-validated** — it speaks the
real PX4 MAVLink wire protocol end-to-end against the real autopilot stack. It
is **not** bench- or field-validated; nothing here implies a physical aircraft
has flown.

## SITL bring-up (reproducible)

PX4 SITL runs in a pinned, headless, multi-arch Docker image — no native PX4
toolchain, no Gazebo install on the host. The image runs natively on Apple
Silicon (`arm64`) and on `amd64`.

- **Image:** `jonasvautherin/px4-gazebo-headless:1.14.0`
- **Digest (pin):** `sha256:77f11913cbb2c4e9147a0ec0fdc4318e9575515e20e88d1f3cd9a21470ddcd21`
- **Autopilot:** PX4 **v1.14.0** (firmware githash `72dd41c5b8`,
  `flight_sw_version` 1.14.0 reported via MAVLink `AUTOPILOT_VERSION`)
- **Vehicle / world:** gazebo-classic `iris`, `empty` (image defaults)
- **Host:** macOS (Darwin arm64), Docker Desktop 29.4.3

### 1. Launch PX4 SITL

```bash
docker run -d --rm --name px4-sitl \
  --log-opt max-size=10m --log-opt max-file=1 \
  jonasvautherin/px4-gazebo-headless@sha256:77f11913cbb2c4e9147a0ec0fdc4318e9575515e20e88d1f3cd9a21470ddcd21 \
  192.168.65.254 192.168.65.254
```

The two trailing arguments are the **IPv4** the in-container PX4 sends MAVLink
to: `<IP for 14550 (GCS)> <IP for 14540 (offboard/API)>`.

> **macOS networking gotcha (why the explicit IPv4 matters).** This image
> auto-targets `host.docker.internal` when no IP is passed. On this Docker
> Desktop, `host.docker.internal` resolves to an **IPv6** ULA
> (`fdc4:f303:9324::254`), and PX4's `-t` partner-IP flag is IPv4-only — so the
> 14540/14550 links silently fail with `ERROR [mavlink] invalid partner ip`.
> Passing the Docker Desktop host gateway IPv4 `192.168.65.254` explicitly
> fixes it. PX4 then sends MAVLink out to the host; Docker Desktop NATs it to
> the host loopback, so a host socket bound on `0.0.0.0:14540` receives it and
> replies route back to the container.
>
> **Linux:** add `--add-host=host.docker.internal:host-gateway` and pass the
> resulting IPv4, or use `--network host` and pass the host's LAN IP.

### 2. Confirm a HEARTBEAT is reachable before probing

```bash
.venv/bin/python - <<'PY'
from pymavlink import mavutil
m = mavutil.mavlink_connection("udpin:0.0.0.0:14540")
print("HEARTBEAT ok" if m.wait_heartbeat(timeout=30) else "NO HEARTBEAT")
m.close()
PY
```

Expected: `HEARTBEAT ok` (PX4 SITL takes ~20–30 s to build/boot and converge
its EKF on first launch).

### 3. Run the acceptance probe with the mission exercise

The connection string is `udpin:` (server / bind mode) because PX4 **sends** to
the host — not the bare-`udp:` default, which is client mode. The verify
waypoint is placed near the SITL home (Zürich, ~47.3977, 8.5456) so the mission
is feasibility-valid and actually progresses.

```bash
make setup   # installs the [mavlink] extra (pymavlink)

MAVLINK_CONNECTION="udpin:0.0.0.0:14540" MAVLINK_AGENT_ID="mav-px4-sitl" \
  .venv/bin/python scripts/phase5_sitl_probe.py --exercise-verify \
  --verify-lat 47.3980 --verify-lon 8.5460 \
  --connect-timeout-s 8 --mission-timeout-s 60 \
  --json-out docs/bench/artifacts/phase9-sitl-probe.json
```

Exit code `0`; the artifact records `status: "pass"`.

## What passed (the Phase 9 gate set)

Every step in [`artifacts/phase9-sitl-probe.json`](artifacts/phase9-sitl-probe.json)
is tagged with the gate it proves:

| Gate | Step | Proof against live PX4 |
|---|---|---|
| `connect` | `heartbeat` | Autopilot HEARTBEAT received (fail-closed connect). |
| `status_visibility` | `health` | `online=true`, `battery_pct=100`, `link_quality≈1.0`. |
| `telemetry_ingest` | `telemetry` | Real `GLOBAL_POSITION_INT` → `Telemetry` at the SITL home (47.3977509, 8.5456076). |
| `mission_dispatch` | `verify_mission` | VERIFY upload `MISSION_COUNT→MISSION_ITEM_INT→MISSION_ACK`, then `ARM→AUTO.MISSION→MAV_CMD_MISSION_START`; phases `EN_ROUTE→ON_STATION→DONE`. |
| `safety_return_abort` | `safety_return` | `RTL_DOCK → MAV_CMD_NAV_RETURN_TO_LAUNCH` accepted (`COMMAND_ACK`); phase `DONE`. |

The probe rolls up to `pass` **only if every step passes** (a failed `health`
or a missing RTL `COMMAND_ACK` now fails the whole run — no false green).

## CI coverage of the probe logic

The live SITL run cannot execute in CI (it needs Docker + Gazebo), but the
probe's logic — including the new `safety_return` step and the honest
all-steps-pass roll-up — is exercised against the in-process
`FakeMAVLinkEndpoint` in `tests/test_phase9_sitl_probe.py`:

- `test_probe_passes_full_gate_set_against_fake` — full green roll-up, 5 gates,
  RTL reaches the autopilot.
- `test_probe_fails_visibly_without_heartbeat` — the exact 2026-05-16 failure
  (no HEARTBEAT) surfaces as `status: "fail"`, not a coast-to-pass.

The adapter mission/command/safety paths the probe drives are additionally
covered by `adapters/mavlink/tests/test_mavlink_mission_mapping.py` (VERIFY
upload, RTL_DOCK → RETURN_TO_LAUNCH, ACK-missing/ACK-rejected failures,
heartbeat-watchdog cancel→RTL).

## What is still NOT proven

- **No physical flight.** SITL exercises the autopilot software stack and the
  MAVLink contract; it does not prove motors, ESCs, RC link, GPS hardware, or
  airframe behaviour. Hardware/field validation remains pending — see the
  bench checklist in [`../adapters/mavlink-setup.md`](../adapters/mavlink-setup.md).
- **No video.** MAVLink carries no video; the gimbal RTSPS/HLS path is
  unexercised here (out of Phase 5 scope, unchanged).
- **Default world/vehicle only.** Iris in an empty world; no wind, no failure
  injection, no multi-vehicle.

## Teardown

```bash
docker rm -f px4-sitl
```
