# MAVLink adapter — setup guide (Phase 5)

This page covers everything you need to bring up the `mavlink` vendor
runner: against PX4 SITL on your laptop, and against real PX4 hardware on
the test bench. The wire protocol the adapter speaks is the same in both
cases — only the connection string changes.

> **Scope.** Phase 5 ships a MAVLink (PX4 / ArduPilot) adapter built on
> `pymavlink`. DJI consumer / Mobile / Cloud integrations are out of
> scope; their stubs in `adapters/dji_*` are left in place for a future
> enterprise integration. See
> [`docs/STATUS.md`](../STATUS.md) for the open vendor decisions.

## Architecture refresher

```
PX4 SITL ─┐
          │ MAVLink (UDP / serial)
real PX4 ─┴──► adapters/mavlink/adapter.py (pymavlink) ──► swarm:* bus ──► backend ──► Console
```

`adapters/mavlink/runner.py` boots the adapter, opens the MAVLink
connection, and publishes:

- `swarm:telemetry:<agent_id>`   — `Telemetry` (≤ 50 Hz, rate-limited)
- `swarm:fleet:state`            — `FleetState` (2 Hz)
- `swarm:streams:<agent_id>`     — `StreamDescriptor`

`backend/app/fleet.py` reads `SWARM_VENDORS` and boots requested MAVLink
runners in-process with the backend. The simulator runs out-of-process via
`python -m sim.swarm_sim.runner` (already launched by
`scripts/dev_up.sh`). If `mavlink` is requested and the adapter does not
receive a HEARTBEAT during boot, backend startup fails; mixed
`SWARM_VENDORS=simulator,mavlink` is also fail-fast unless Phase 6 adds an
explicit best-effort policy.

## Env vars

| Var | Default | Meaning |
|---|---|---|
| `SWARM_VENDORS` | `simulator` | Comma-separated vendor list. Allowed: `simulator`, `mavlink`. Unknown tokens fail-fast on backend boot. |
| `MAVLINK_CONNECTION` | `udp:localhost:14540` | `pymavlink` connection string. PX4 SITL emits on `udp:14540` (offboard) and `udp:14550` (GCS); ArduPilot uses `udp:14550`. Serial: `/dev/ttyUSB0,57600`. |
| `MAVLINK_AGENT_ID` | `mav-001` | The SwarmOS agent id reported on `swarm:fleet:state`. |
| `MAVLINK_MODEL` | `px4-x500` | Display string the Console renders. |
| `MAVLINK_STREAM_URL` | _unset_ | Optional gimbal stream URL. Must be `rtsps://` or `https://`; `http://`, `rtsp://`, `rtmp://`, `file://`, etc. are rejected at boot. |
| `MAVLINK_RATE_LIMIT_HZ` | `50` | Sanity cap on telemetry frames per agent. The roadmap pins 50 Hz. |

## Adapter readiness boundaries

Phase 5 has two readiness levels:

- **CI-ready:** `make test` exercises the adapter against
  `FakeMAVLinkEndpoint`, which enforces HEARTBEAT-before-connect,
  request/response mission upload, duplicate `MISSION_REQUEST_INT`
  handling, final `MISSION_ACK`, `COMMAND_ACK`, `PARAM_VALUE`, stream URL
  allowlisting, backend-side telemetry rate limiting, and fail-fast vendor
  boot.
- **Bench-ready:** PX4 SITL or real hardware has been run with the manual
  checklist below. Do not mark bench validation complete until the runbook
  evidence exists for the exact commit under review.

## Local PX4 SITL bring-up

PX4 SITL is the recommended way to exercise the adapter end-to-end
without hardware. The adapter does **not** ship with SITL — it would
pull Gazebo / a multi-gigabyte runtime — so install it once on your
workstation.

```bash
# 1. Build PX4 SITL once. ~30 min.
git clone --recurse-submodules https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot
make px4_sitl_default jmavsim   # or `gazebo` for the heavier sim

# 2. Launch SITL. It listens on UDP 14540 by default.
make px4_sitl_default jmavsim

# 3. In a separate terminal, boot SwarmOS with the mavlink vendor.
cd /path/to/swarm
SWARM_VENDORS=simulator,mavlink \
  MAVLINK_CONNECTION="udp:localhost:14540" \
  MAVLINK_AGENT_ID="mav-px4-sitl" \
  ./scripts/dev_up.sh
```

The Console at `http://localhost:3000` should now show an extra unit
("mav-px4-sitl") in the FleetGrid, projected from `FleetState` frames
the runner publishes.

### Manual SITL acceptance gate

CI intentionally does not download or run PX4/Gazebo. Before Phase 6 starts,
run this checklist manually and attach the command output/screenshots to the
release/PR notes:

1. `make px4_sitl_default jmavsim` (inside `PX4-Autopilot`) reaches a
   ready SITL prompt and emits HEARTBEAT on UDP 14540.
2. `SWARM_VENDORS=mavlink MAVLINK_CONNECTION="udp:localhost:14540"
   MAVLINK_AGENT_ID="mav-px4-sitl" ./scripts/dev_up.sh` starts the
   backend successfully. A missing HEARTBEAT must fail backend boot.
3. `redis-cli SUBSCRIBE swarm:fleet:state swarm:telemetry:mav-px4-sitl`
   shows the MAVLink unit online with `link_quality > 0`.
4. Submit a VERIFY mission and confirm in PX4/QGroundControl logs that the
   upload uses `MISSION_COUNT`, requested `MISSION_ITEM_INT` frames only,
   and final `MISSION_ACK(MAV_MISSION_ACCEPTED)`.
5. Confirm `COMMAND_ACK` for arm, mission start, and RTL. Rejecting or
   dropping an ACK must surface as an adapter error in backend logs.
6. With `MAVLINK_STREAM_URL` unset, the Console keeps the honest offline
   viewport. With an `https://` or `rtsps://` URL set, it renders the
   configured stream descriptor. Plaintext URLs must fail at boot.

### Verifying the MAVLink path is live

In a third terminal, watch the bus:

```bash
redis-cli SUBSCRIBE swarm:telemetry:mav-px4-sitl
# expect frames at ~4 Hz
```

If you see no frames:

1. Confirm SITL is listening: `nc -uz 127.0.0.1 14540` should succeed.
2. Confirm the runner attached: `docker compose logs backend | grep mavlink`.
3. Confirm the heartbeat watchdog isn't tripping. The adapter cancels
   itself after 3 s of HEARTBEAT silence — symptom: `link_quality`
   collapses to 0 in `swarm:fleet:state`.

## Real PX4 hardware on the test bench

Recommended airframes for the demo bench:

- **Holybro X500 V2** with a Pixhawk 6X — props-safe testing, ~2 kg AUW.
- **3DR Quad Zero** (sub-250 g, EASA C0 class) — outdoor flight without
  a remote-pilot license in EU under §EASA-2019/947 once registered.

### Radio link

A 433 MHz / 915 MHz SiK telemetry radio pair is the standard MAVLink
transport for outdoor flight (range up to 1 km in open terrain). USB
mode is also fine for indoor bench tests.

Configure the radio pair via the QGroundControl Setup → Radio page:

- Baud rate: **57600**
- Air rate:  **64 kbps**
- TX power:  **20 dBm** (regulatory cap inside EU)

### Firmware parameters

Set these on the airframe before flight. They are baseline; site-specific
overrides come in Phase 6 via `infra/config/sites/<site_id>.yaml`.

| Param | Value | Why |
|---|---|---|
| `SYS_AUTOSTART` | `4001` | Generic quad X (X500 default) |
| `MAV_0_CONFIG` | `TELEM 1` | First MAVLink instance on TELEM1 (the SiK radio) |
| `MAV_0_MODE` | `Normal` | GCS-style MAVLink |
| `MAV_0_RATE` | `9600` | Conservative; the adapter rate-limits to 50 Hz anyway |
| `BAT_LOW_THR` | `0.20` | RTL at 20% — `set_safety` re-asserts on connect |
| `BAT_CRIT_THR` | `0.10` | Land at 10% |
| `MIS_TAKEOFF_ALT` | `10.0` | Conservative AGL takeoff target |
| `RTL_DESCEND_ALT` | `30.0` | Approach altitude |
| `RTL_LAND_DELAY` | `0` | Land immediately on home arrival |
| `GF_ACTION` | `2` | RTL on geofence breach (the adapter uploads the polygon) |
| `GF_MAX_HOR_DIST` | `500.0` | Radial soft cap (the polygon takes precedence) |
| `GF_MAX_VER_DIST` | `120.0` | Matches `set_safety(max_alt_m=120)` |
| `COM_OBL_RC_ACT` | `0` | RTL when both GCS and RC are lost |

### Bring-up checklist (props-on, on the bench, **not yet in flight**)

1. Connect the radio pair; verify a green link LED on the GCS side.
2. `python -m adapters.mavlink.runner` with
   `MAVLINK_CONNECTION="/dev/ttyUSB0,57600"`. Expect a log line:
   `mavlink runner: mav-001 online` within 5 s.
3. The runner sends `set_safety` only when called by the orchestrator;
   to test the upload path manually, drop into a Python REPL:
   ```python
   from adapters.mavlink import MAVLinkAdapter
   from adapters.base import Polygon
   from swarm_core.messages import Geo
   a = MAVLinkAdapter(agent_id="mav-001", connection="/dev/ttyUSB0,57600")
   await a.connect()
   await a.set_safety(
       Polygon(points=(
           Geo(lat=44.7000, lon=8.0300),
           Geo(lat=44.7050, lon=8.0300),
           Geo(lat=44.7050, lon=8.0350),
           Geo(lat=44.7000, lon=8.0350),
       )),
       max_alt_m=120.0, rtl_battery_pct=25,
   )
   ```
   Confirm in QGroundControl that `BAT_LOW_THR=0.25` and the fence is
   green.
4. **Unarmed** mission upload check: submit a VERIFY mission via the
   Console (or `curl -X POST .../actions/verify`) and watch the
   `MISSION_COUNT` / `MISSION_ITEM_INT` arrive in QGroundControl. The
   items should match the SwarmOS waypoints lat/lon to 5 decimals.
5. Outdoor flight with props on: a `VERIFY` mission should arm, take
   off, fly to the sector, hover for the configured `hover_s`, capture,
   and RTL automatically.

### Video stream

MAVLink does **not** carry video. The gimbal (e.g. Siyi A8 mini)
publishes RTSP on its own LAN address; mirror it through `mediamtx` or
`go2rtc` to an RTSPS or HLS endpoint and feed the URL via
`MAVLINK_STREAM_URL`. The adapter publishes a `StreamDescriptor` to the
bus; the Console renders the `<video>` element only when the URL passes
the allowlist (`rtsps://` or `https://`) — plaintext `rtsp://` and
`http://` are rejected at both the server and the client.

`request_capture(sensor)` does not fabricate a MAVLink capture artifact.
When `MAVLINK_STREAM_URL` is configured it returns that real stream URI as
the capture reference; when no stream is configured it raises
`MAVLinkCaptureUnavailable` so the caller can render "unavailable" instead
of treating a synthetic URI as evidence.

## CI

The conformance suite under `adapters/mavlink/tests/` runs against an
**in-process** `FakeMAVLinkEndpoint` — a UDP MAVLink server we ship in
the repo. PX4 SITL is the bench acceptance gate; CI does not boot it
(it would require Gazebo). The fake covers the wire protocol the
adapter actually speaks (HEARTBEAT, MISSION_COUNT / MISSION_ITEM_INT /
MISSION_REQUEST_INT / MISSION_ACK, duplicate requests, COMMAND_LONG /
COMMAND_ACK, SET_MODE heartbeat confirmation, PARAM_SET / PARAM_VALUE,
FENCE_POINT), so contract drift surfaces in CI. The fake rejects shortcut
uploads, missing final ACKs, rejected ACKs, and connection without
HEARTBEAT.

## Troubleshooting

- **`heartbeat watchdog: ... link lost` repeatedly:** Endpoint not
  emitting HEARTBEAT. Check the SITL / radio is alive. The adapter
  defaults to a 3 s timeout; raise via `MAVLinkAdapter(...,
  heartbeat_timeout_s=10.0)` for noisy benches.
- **`RejectedMission: waypoint (...) outside geofence`:** Pre-upload
  client-side check tripped. Either fix the waypoint or call
  `set_safety` with a wider polygon. Failing closed is intentional —
  defense in depth.
- **`InvalidStreamURL: stream url scheme not allowed: 'http'`:** The
  allowlist is `rtsps://` and `https://` only. Re-host the stream
  behind a TLS-terminating proxy.
- **`UnknownVendor: ... in SWARM_VENDORS`:** Typo in the env var. The
  closed allowlist is in `backend.app.fleet.SUPPORTED_VENDORS`.
