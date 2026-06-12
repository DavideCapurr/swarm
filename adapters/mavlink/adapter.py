"""MAVLink DroneAdapter — PX4 / ArduPilot via pymavlink.

Phase 5 rewrite: replaces the Phase 0 MAVSDK stub. `pymavlink` is the pure-
Python wire-protocol library; it has no protobuf transitive dependency, so the
Phase 0 audit blocker that ruled out MAVSDK does not apply here. Real flight
acceptance is on the hardware bench (PX4 SITL + a real Holybro X500 / 3DR Quad
Zero); the conformance suite in `adapters/mavlink/tests/` runs against an
in-process `FakeMAVLinkEndpoint` so CI catches contract drift without SITL.

Mission DSL mapping (see roadmap §Phase 5):
  PATROL / VERIFY → `MISSION_COUNT`, then requested-only
                     `MISSION_ITEM_INT` / `MISSION_ITEM` responses, final
                     `MISSION_ACK`, `MAV_CMD_MISSION_START`; progress
                     observed via `MISSION_CURRENT`.
  RTL_DOCK        → `MAV_CMD_NAV_RETURN_TO_LAUNCH`.
  RELAY           → uses `MAV_CMD_NAV_LOITER_UNLIM` (hold position).
  COVER           → rejected — orchestrator must decompose into PATROL slices.

Safety enforcement:
  * `set_safety()` uploads FENCE_POINTs, enables the fence, and writes
    `BAT_LOW_THR` / `MIS_TAKEOFF_ALT` params.
  * Defense-in-depth: every waypoint is geofence-checked before upload; a
    rejected mission raises `RejectedMission` and never reaches the wire.
  * Heartbeat watchdog: if no HEARTBEAT has been received for > 3s the
    adapter's `link_quality` collapses to 0 and any active mission is
    marked cancelled so its loop fails closed into RTL.

Video frame streaming via MAVLink is out of scope (roadmap §Phase 5 §Scope
out): video comes from a separate RTSP / RTSPS gimbal; the adapter
advertises an external URL via `StreamDescriptor` and `stream_video()`
remains a no-op.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import itertools
import logging
import math
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from pymavlink import mavutil
from swarm_core.geometry import haversine_m
from swarm_core.messages import (
    Attitude,
    CaptureResult,
    Geo,
    MissionProgress,
    MissionTask,
    SensorKind,
    Telemetry,
    Waypoint,
)
from swarm_core.missions import MissionKind, UnsupportedMission, mission_waypoints
from swarm_core.rate_limit import TelemetryRateLimiter
from swarm_core.streams import StreamDescriptor, validate_stream_url

from adapters.base import (
    Capabilities,
    Failsafes,
    HealthReport,
    Polygon,
    VideoFrame,
)

logger = logging.getLogger("mavlink.adapter")


class MAVLinkAdapterError(RuntimeError):
    """Base class for MAVLink adapter failures."""


class MAVLinkConnectionError(MAVLinkAdapterError):
    """Raised when a MAVLink endpoint cannot prove it is alive."""


class MAVLinkTimeoutError(MAVLinkAdapterError):
    """Raised when a required MAVLink response does not arrive in time."""


class MAVLinkProtocolError(MAVLinkAdapterError):
    """Raised when the peer violates the expected MAVLink flow."""


class MAVLinkCommandError(MAVLinkAdapterError):
    """Raised when a COMMAND_LONG is rejected or never acknowledged."""


class MAVLinkMissionError(MAVLinkAdapterError):
    """Raised when mission upload is rejected or times out."""


class MAVLinkCaptureUnavailable(MAVLinkAdapterError):
    """Raised when the adapter has no honest capture/stream URI configured."""


class RejectedMission(MAVLinkAdapterError):
    """Raised by `MAVLinkAdapter` when a mission fails client-side safety checks."""


#: Heartbeat watchdog threshold. PX4/ArduPilot both publish HEARTBEAT at 1 Hz,
#: so 3 s with nothing means the radio is gone (or the autopilot has crashed).
HEARTBEAT_TIMEOUT_S: float = 3.0

#: Floor for the waypoint-mission completion deadline. The actual deadline
#: scales with path length and cruise speed (see `_mission_deadline_s`);
#: missions may also pin an explicit `timeout_s` param.
MIN_MISSION_TIMEOUT_S: float = 30.0

#: Conservative cruise fraction of the declared max speed used when sizing
#: the mission deadline — wind, climbs, and corner slow-downs eat margin.
CRUISE_SPEED_FRACTION: float = 0.5


@dataclass
class _MessageWaiter:
    predicate: Callable[[Any], bool]
    future: asyncio.Future[Any]


def _point_in_polygon(lat: float, lon: float, polygon: tuple[Geo, ...]) -> bool:
    """Ray-cast point-in-polygon. Inclusive of the boundary for our purposes.

    Polygons that wrap the antimeridian are not handled — Phase 5 sites are
    small (one vineyard / one perimeter), so this is fine. Phase 6 swaps in
    a Shapely-backed implementation when site_id-aware policy lands.
    """
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        pi = polygon[i]
        pj = polygon[j]
        # Strict ray cast on lon; lat the test value.
        cond = (pi.lon > lon) != (pj.lon > lon)
        if cond:
            slope = (lat - pi.lat) * (pj.lon - pi.lon) - (pj.lat - pi.lat) * (lon - pi.lon)
            if slope == 0:
                return True  # on the edge
            if (slope < 0) != (pj.lon < pi.lon):
                inside = not inside
        j = i
    return inside


def _custom_mode_auto_mission() -> int:
    """Compose the PX4 custom_mode word that selects AUTO.MISSION."""
    main = int(mavutil.PX4_CUSTOM_MAIN_MODE_AUTO)
    sub = int(mavutil.PX4_CUSTOM_SUB_MODE_AUTO_MISSION)
    # Lower 16 bits unused; main mode at byte 2, sub mode at byte 3 (PX4 docs).
    return (sub << 24) | (main << 16)


def _param_id(msg: Any) -> str:
    raw = getattr(msg, "param_id", "")
    if isinstance(raw, bytes):
        return raw.rstrip(b"\x00").decode("ascii", errors="replace")
    return str(raw).rstrip("\x00")


class MAVLinkAdapter:
    """`DroneAdapter` driven by `pymavlink`."""

    vendor: str = "mavlink"

    def __init__(
        self,
        *,
        agent_id: str,
        connection: str = "udp:localhost:14540",
        model: str = "px4-x500",
        source_system: int = 254,
        source_component: int = 0,
        stream_url: str | None = None,
        rate_limit_hz: float = 50.0,
        heartbeat_timeout_s: float = HEARTBEAT_TIMEOUT_S,
        connect_timeout_s: float = 5.0,
        response_timeout_s: float = 5.0,
    ) -> None:
        self.agent_id = agent_id
        self.model = model
        self._connection_str = connection
        self._source_system = source_system
        self._source_component = source_component
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=False,
            max_flight_time_s=1200.0,
            max_speed_mps=15.0,
            max_altitude_m=120.0,
        )
        self.autopilot_failsafes = Failsafes()
        self._mav: Any | None = None
        self._connected = False
        self._cancelled = False
        self._paused = False
        # Safety envelope; populated by set_safety, enforced before upload.
        self._geofence: tuple[Geo, ...] | None = None
        self._max_alt_m: float = self.capabilities.max_altitude_m
        # Watchdog
        self._heartbeat_timeout_s = heartbeat_timeout_s
        self._connect_timeout_s = connect_timeout_s
        self._response_timeout_s = response_timeout_s
        self._last_heartbeat_at: float = 0.0
        # Telemetry state
        self._last_position: Geo | None = None
        self._last_battery_pct: float = 100.0
        self._link_quality: float = 0.0
        self._heading_deg: float = 0.0
        self._rate_limiter = TelemetryRateLimiter(max_hz=rate_limit_hz)
        # Mission state
        self._mission_total: int = 0
        self._mission_current: int = 0
        # External (RTSP / HLS) stream the gimbal advertises out-of-band.
        if stream_url is not None:
            # Fail-fast on bad URL so misconfiguration shows up at init, not
            # in the middle of a flight.
            validate_stream_url(stream_url)
        self._stream_url = stream_url
        self._rx_task: asyncio.Task[None] | None = None
        self._waiters: list[_MessageWaiter] = []

    # ── identity ──────────────────────────────────────────────────────────────

    def stream_descriptor(self) -> StreamDescriptor:
        """Where the operator's browser can pick up live video for this unit.

        Phase 5 keeps video on a separate RTSPS / HLS channel. If the adapter
        is initialized without a URL the descriptor is `available=False`, so
        the Console renders the honest viewport placard.
        """
        if not self._stream_url:
            return StreamDescriptor.offline(self.agent_id)
        scheme = self._stream_url.split(":", 1)[0].lower()
        proto: Any = scheme if scheme in {"rtsps", "https"} else None
        return StreamDescriptor(
            agent_id=self.agent_id,
            available=True,
            url=self._stream_url,
            protocol=proto,
            codec="h264",
        )

    def _require_mav(self) -> Any:
        if self._mav is None:
            raise RuntimeError("adapter not connected")
        return self._mav

    # ── lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        loop = asyncio.get_running_loop()
        self._last_heartbeat_at = 0.0
        self._link_quality = 0.0
        # `mavlink_connection` is blocking — run in executor so we don't stall
        # the event loop on a slow `udp:` resolve.
        try:
            mav = await loop.run_in_executor(
                None,
                lambda: mavutil.mavlink_connection(
                    self._connection_str,
                    source_system=self._source_system,
                    source_component=self._source_component,
                    dialect="ardupilotmega",
                    input=False,
                ),
            )
        except Exception as exc:
            raise MAVLinkConnectionError(
                f"failed to open MAVLink connection {self._connection_str!r}"
            ) from exc
        self._mav = mav
        heartbeat = self._create_waiter(
            lambda msg: (
                msg.get_type() == "HEARTBEAT"
                and int(getattr(msg, "type", -1)) != mavutil.mavlink.MAV_TYPE_GCS
            )
        )
        # Some MAVLink endpoints (PX4 SITL, our fake) only learn the GCS UDP
        # address when the GCS sends a frame first.
        with contextlib.suppress(Exception):
            mav.mav.heartbeat_send(
                mavutil.mavlink.MAV_TYPE_GCS,
                mavutil.mavlink.MAV_AUTOPILOT_INVALID,
                0,
                0,
                mavutil.mavlink.MAV_STATE_ACTIVE,
            )
        self._connected = True
        self._cancelled = False
        self._rx_task = asyncio.create_task(self._rx_loop())
        # Fail closed: a UDP socket can be "open" while no autopilot is
        # present. Do not report success until a real autopilot HEARTBEAT
        # proves the peer exists.
        try:
            await asyncio.wait_for(heartbeat, timeout=self._connect_timeout_s)
        except TimeoutError as exc:
            await self.disconnect()
            raise MAVLinkConnectionError(
                f"MAVLink connect timed out waiting for HEARTBEAT from {self._connection_str!r}"
            ) from exc

    async def disconnect(self) -> None:
        self._connected = False
        for waiter in self._waiters:
            if not waiter.future.done():
                waiter.future.cancel()
        self._waiters.clear()
        if self._rx_task is not None:
            self._rx_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._rx_task
            self._rx_task = None
        if self._mav is not None:
            with contextlib.suppress(Exception):  # pragma: no cover — defensive
                self._mav.close()
            self._mav = None

    async def health(self) -> HealthReport:
        if not self._connected:
            return HealthReport(
                online=False,
                battery_pct=0.0,
                link_quality=0.0,
                last_telemetry_age_s=None,
            )
        age = (
            max(0.0, time.monotonic() - self._last_heartbeat_at)
            if self._last_heartbeat_at
            else None
        )
        return HealthReport(
            online=age is not None and age < self._heartbeat_timeout_s,
            battery_pct=self._last_battery_pct,
            link_quality=self._link_quality,
            last_telemetry_age_s=age,
        )

    # ── safety envelope ──────────────────────────────────────────────────────

    async def set_safety(self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int) -> None:
        mav = self._require_mav()
        self._geofence = tuple(geofence.points)
        self._max_alt_m = float(max_alt_m)
        loop = asyncio.get_running_loop()
        # FENCE_POINT uploads. PX4 expects (lat, lng) in degrees, all points
        # then a closing zero-area marker. We omit the marker — the count is
        # carried by `FENCE_TOTAL` param.
        total = len(geofence.points)
        for idx, pt in enumerate(geofence.points):
            await loop.run_in_executor(
                None,
                functools.partial(
                    mav.mav.fence_point_send,
                    mav.target_system,
                    mav.target_component,
                    idx,
                    total,
                    pt.lat,
                    pt.lon,
                ),
            )
        await self._send_command_long(
            mavutil.mavlink.MAV_CMD_DO_FENCE_ENABLE,
            param1=1.0,
        )
        await self._set_param("BAT_LOW_THR", float(rtl_battery_pct) / 100.0)
        await self._set_param("MIS_TAKEOFF_ALT", min(20.0, float(max_alt_m)))

    # ── mission ──────────────────────────────────────────────────────────────

    async def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:  # type: ignore[override]
        if not self._connected or self._mav is None:
            raise RuntimeError("adapter not connected")
        self._cancelled = False
        self._paused = False
        kind = mission.kind

        if kind in (MissionKind.PATROL.value, MissionKind.VERIFY.value):
            async for p in self._fly_waypoints(mission):
                yield p
        elif kind == MissionKind.RELAY.value:
            async for p in self._hover_relay(mission):
                yield p
        elif kind == MissionKind.RTL_DOCK.value:
            await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
            yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)
        elif kind == MissionKind.COVER.value:
            raise UnsupportedMission("COVER must be decomposed in the orchestrator before dispatch")
        else:
            raise UnsupportedMission(f"unknown mission kind: {kind}")

    def _validate_waypoints_against_safety(
        self, waypoints: list[Waypoint], default_alt: float
    ) -> None:
        for wp in waypoints:
            alt = wp.geo.alt_m if wp.geo.alt_m else default_alt
            if alt > self._max_alt_m:
                raise RejectedMission(
                    f"waypoint altitude {alt} m exceeds max_alt {self._max_alt_m} m"
                )
            if self._geofence is not None and not _point_in_polygon(
                wp.geo.lat, wp.geo.lon, self._geofence
            ):
                raise RejectedMission(
                    f"waypoint ({wp.geo.lat:.5f}, {wp.geo.lon:.5f}) outside geofence"
                )

    def _mission_deadline_s(
        self, mission: MissionTask, waypoints: list[Waypoint]
    ) -> float:
        """Completion deadline for a waypoint mission.

        A mission may pin an explicit ``timeout_s`` param; otherwise the
        deadline scales with the summed leg distances at a conservative
        cruise speed, floored at MIN_MISSION_TIMEOUT_S. A fixed deadline
        would fail-RTL any patrol longer than the constant allows.
        """
        explicit = mission.params.get("timeout_s")
        if explicit is not None:
            return max(float(explicit), MIN_MISSION_TIMEOUT_S)
        path_m = sum(
            haversine_m(a.geo, b.geo) for a, b in itertools.pairwise(waypoints)
        )
        cruise_mps = max(
            self.capabilities.max_speed_mps * CRUISE_SPEED_FRACTION, 1.0
        )
        return MIN_MISSION_TIMEOUT_S + path_m / cruise_mps

    async def _fly_waypoints(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        assert self._mav is not None
        waypoints = mission_waypoints(mission)
        if not waypoints:
            yield MissionProgress(
                mission_id=mission.id, phase="FAILED", progress_pct=0.0, error="empty mission"
            )
            return
        default_alt = float(mission.params.get("altitude_m", 60.0))
        # Defense in depth: pre-upload geofence + altitude check.
        self._validate_waypoints_against_safety(waypoints, default_alt)
        timeout_s = self._mission_deadline_s(mission, waypoints)

        # Send MISSION_COUNT, then stream MISSION_ITEM_INT in response to
        # MISSION_REQUEST_INT.
        await self._upload_mission(waypoints, default_alt)
        # Arm.
        await self._send_command_long(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, param1=1.0)
        # Switch to AUTO.MISSION via SET_MODE.
        await self._set_mode_auto_mission()
        # Start mission.
        await self._send_command_long(mavutil.mavlink.MAV_CMD_MISSION_START)
        self._mission_total = len(waypoints)
        yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_s
        last_emitted = -1
        while loop.time() < deadline:
            if self._cancelled:
                await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
                yield MissionProgress(
                    mission_id=mission.id, phase="FAILED", progress_pct=0.0, error="cancelled"
                )
                return
            if self._paused:
                # Holding position (autopilot got DO_PAUSE_CONTINUE). Freeze
                # the completion clock so a long operator hold can't trip the
                # deadline and fail-RTL a healthy mission.
                deadline += 0.05
                await asyncio.sleep(0.05)
                continue
            if self._mission_current != last_emitted:
                last_emitted = self._mission_current
                pct = (self._mission_current + 1) / max(self._mission_total, 1) * 90.0
                phase = "ON_STATION" if mission.kind == MissionKind.VERIFY.value else "EN_ROUTE"
                yield MissionProgress(mission_id=mission.id, phase=phase, progress_pct=pct)
            if self._mission_current >= self._mission_total - 1:
                break
            await asyncio.sleep(0.05)

        await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
        yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)

    async def _upload_mission(self, waypoints: list[Waypoint], default_alt: float) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()

        def mission_predicate(candidate: Any) -> bool:
            return candidate.get_type() in {
                "MISSION_REQUEST_INT",
                "MISSION_REQUEST",
                "MISSION_ACK",
            }

        next_response = self._create_waiter(mission_predicate)
        await loop.run_in_executor(
            None,
            lambda: mav.mav.mission_count_send(
                mav.target_system,
                mav.target_component,
                len(waypoints),
            ),
        )
        sent: set[int] = set()
        deadline = loop.time() + max(
            self._response_timeout_s, len(waypoints) * self._response_timeout_s
        )
        accepted = mavutil.mavlink.MAV_MISSION_ACCEPTED

        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise MAVLinkMissionError(
                    "mission upload timed out waiting for MISSION_REQUEST or MISSION_ACK"
                )
            try:
                msg = await asyncio.wait_for(next_response, timeout=remaining)
            except TimeoutError as exc:
                raise MAVLinkTimeoutError(
                    "timed out waiting for MISSION_REQUEST(_INT) or MISSION_ACK"
                ) from exc
            finally:
                self._waiters = [w for w in self._waiters if w.future is not next_response]
            kind = msg.get_type()
            if kind in {"MISSION_REQUEST_INT", "MISSION_REQUEST"}:
                seq = int(getattr(msg, "seq", -1))
                if seq < 0 or seq >= len(waypoints):
                    raise MAVLinkProtocolError(
                        f"autopilot requested invalid mission item seq={seq}"
                    )
                next_response = self._create_waiter(mission_predicate)
                try:
                    await self._send_mission_item(
                        waypoints[seq],
                        seq=seq,
                        default_alt=default_alt,
                        use_int=kind == "MISSION_REQUEST_INT",
                    )
                except Exception:
                    self._waiters = [w for w in self._waiters if w.future is not next_response]
                    raise
                sent.add(seq)
                continue

            result = int(getattr(msg, "type", -1))
            if result != accepted:
                raise MAVLinkMissionError(f"mission upload rejected with MISSION_ACK type={result}")
            if len(sent) != len(waypoints):
                raise MAVLinkProtocolError(
                    "mission upload accepted before every item was requested"
                )
            return

    async def _send_mission_item(
        self,
        waypoint: Waypoint,
        *,
        seq: int,
        default_alt: float,
        use_int: bool,
    ) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()
        alt = waypoint.geo.alt_m if waypoint.geo.alt_m else default_alt
        if use_int:
            await loop.run_in_executor(
                None,
                functools.partial(
                    mav.mav.mission_item_int_send,
                    mav.target_system,
                    mav.target_component,
                    seq,
                    mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                    mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                    0,  # current
                    1,  # autocontinue
                    0.0,  # param1 — hold time
                    2.0,  # param2 — accept radius
                    0.0,  # param3 — pass radius
                    float("nan"),  # param4 — yaw
                    int(waypoint.geo.lat * 1e7),
                    int(waypoint.geo.lon * 1e7),
                    float(alt),
                ),
            )
            return
        await loop.run_in_executor(
            None,
            functools.partial(
                mav.mav.mission_item_send,
                mav.target_system,
                mav.target_component,
                seq,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0,
                1,
                0.0,
                2.0,
                0.0,
                float("nan"),
                float(waypoint.geo.lat),
                float(waypoint.geo.lon),
                float(alt),
            ),
        )

    async def _hover_relay(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        self._require_mav()
        geo = Geo(**mission.params["geo"])
        duration_s = float(mission.params.get("duration_s", 600.0))
        altitude_m = float(mission.params.get("altitude_m", 80.0))
        # Validate against safety envelope before issuing the LOITER.
        self._validate_waypoints_against_safety([Waypoint(geo=geo)], default_alt=altitude_m)
        await self._send_command_long(
            mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
            param5=geo.lat,
            param6=geo.lon,
            param7=altitude_m,
        )
        yield MissionProgress(mission_id=mission.id, phase="ON_STATION", progress_pct=50.0)
        elapsed = 0.0
        step = 0.5
        while elapsed < duration_s and not self._cancelled:
            await asyncio.sleep(min(step, duration_s - elapsed))
            if self._paused:
                continue  # holding — relay time on station does not accrue
            elapsed += step
        await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)
        if self._cancelled:
            yield MissionProgress(
                mission_id=mission.id, phase="FAILED", progress_pct=0.0, error="cancelled"
            )
        else:
            yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)

    async def pause_mission(self) -> None:
        """Hold in place: `MAV_CMD_DO_PAUSE_CONTINUE(param1=0)` + ACK.

        The flag is set only after the autopilot acknowledges, so a lost
        command can't leave the loop convinced the vehicle is holding
        while it keeps flying the mission.
        """
        if self._connected and self._mav is not None:
            await self._send_command_long(
                mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE, param1=0.0
            )
        self._paused = True

    async def resume_mission(self) -> None:
        if self._connected and self._mav is not None:
            await self._send_command_long(
                mavutil.mavlink.MAV_CMD_DO_PAUSE_CONTINUE, param1=1.0
            )
        self._paused = False

    async def cancel_mission(self) -> None:
        self._cancelled = True
        if self._mav is not None:
            with contextlib.suppress(Exception):
                await self._send_command_long(mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH)

    async def divert(self, new_waypoint: Waypoint) -> None:
        # Defense in depth: refuse to divert outside the safety envelope.
        self._validate_waypoints_against_safety([new_waypoint], default_alt=self._max_alt_m / 2)
        await self._send_command_long(
            mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM,
            param5=new_waypoint.geo.lat,
            param6=new_waypoint.geo.lon,
            param7=new_waypoint.geo.alt_m or self._max_alt_m / 2,
        )

    async def request_capture(self, sensor: SensorKind) -> CaptureResult:
        if not self._stream_url:
            raise MAVLinkCaptureUnavailable(
                "MAVLink capture is not configured; set MAVLINK_STREAM_URL "
                "to an allowlisted RTSPS/HLS endpoint before requesting capture"
            )
        geo = self._last_position or Geo(lat=0.0, lon=0.0)
        return CaptureResult(
            sensor=sensor,
            uri=self._stream_url,
            geo=geo,
        )

    # ── streams ──────────────────────────────────────────────────────────────

    async def stream_telemetry(self) -> AsyncIterator[Telemetry]:  # type: ignore[override]
        # Push telemetry at 4 Hz — well under the rate limiter cap. The
        # GLOBAL_POSITION_INT messages arrive at 10 Hz from the autopilot;
        # we sample them here so MissionProgress can observe between yields.
        while self._connected:
            await asyncio.sleep(0.25)
            if not self._last_heartbeat_at:
                continue
            geo = self._last_position
            if geo is None:
                continue
            if not self._rate_limiter.should_accept(self.agent_id):
                continue
            yield Telemetry(
                agent_id=self.agent_id,
                geo=geo,
                attitude=Attitude(yaw_deg=self._heading_deg),
                battery_pct=self._last_battery_pct,
                link_quality=self._link_quality,
            )

    async def stream_video(self) -> AsyncIterator[VideoFrame]:  # type: ignore[override]
        # Phase 5 keeps video on a separate RTSPS / HLS pipe (see
        # `stream_descriptor`). This adapter method stays a no-op.
        if False:  # pragma: no cover
            yield VideoFrame(self.agent_id, 0, 0, 0, "h264", b"")

    # ── internals ────────────────────────────────────────────────────────────

    def _create_waiter(self, predicate: Callable[[Any], bool]) -> asyncio.Future[Any]:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._waiters.append(_MessageWaiter(predicate=predicate, future=future))
        return future

    async def _wait_for_message(
        self,
        predicate: Callable[[Any], bool],
        *,
        timeout_s: float | None = None,
        description: str,
    ) -> Any:
        future = self._create_waiter(predicate)
        try:
            return await asyncio.wait_for(
                future,
                timeout=self._response_timeout_s if timeout_s is None else timeout_s,
            )
        except TimeoutError as exc:
            raise MAVLinkTimeoutError(f"timed out waiting for {description}") from exc
        finally:
            self._waiters = [w for w in self._waiters if w.future is not future]

    async def _rx_loop(self) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()
        try:
            while self._connected:
                msg = await loop.run_in_executor(
                    None, lambda: mav.recv_match(blocking=True, timeout=0.5)
                )
                if msg is None:
                    self._check_watchdog()
                    continue
                self._dispatch(msg)
                self._check_watchdog()
        except asyncio.CancelledError:
            raise
        except Exception:  # pragma: no cover — defensive
            logger.exception("mavlink rx loop crashed")

    def _check_watchdog(self) -> None:
        if not self._last_heartbeat_at:
            return
        age = time.monotonic() - self._last_heartbeat_at
        if age > self._heartbeat_timeout_s:
            if self._link_quality > 0.0:
                logger.warning(
                    "heartbeat watchdog: %s link lost (age %.1fs) — cancel + RTL",
                    self.agent_id,
                    age,
                )
            self._link_quality = 0.0
            self._cancelled = True
        else:
            self._link_quality = max(0.0, 1.0 - age / self._heartbeat_timeout_s)

    def _dispatch(self, msg: Any) -> None:
        kind = msg.get_type()
        if kind == "HEARTBEAT":
            self._last_heartbeat_at = time.monotonic()
            self._link_quality = 1.0
        elif kind == "GLOBAL_POSITION_INT":
            self._last_position = Geo(
                lat=float(msg.lat) / 1e7,
                lon=float(msg.lon) / 1e7,
                alt_m=float(msg.relative_alt) / 1000.0,
            )
            hdg = float(getattr(msg, "hdg", 0))
            # `hdg` is 0-35999 (centi-degrees) or 65535 if unknown.
            if hdg != 65535:
                self._heading_deg = hdg / 100.0
        elif kind == "SYS_STATUS":
            remaining = int(getattr(msg, "battery_remaining", -1))
            if 0 <= remaining <= 100:
                self._last_battery_pct = float(remaining)
        elif kind == "MISSION_CURRENT":
            self._mission_current = int(getattr(msg, "seq", 0))
        for waiter in list(self._waiters):
            if waiter.future.done():
                self._waiters.remove(waiter)
                continue
            try:
                matched = waiter.predicate(msg)
            except Exception:  # pragma: no cover — defensive
                logger.exception("mavlink waiter predicate crashed")
                matched = False
            if matched and not waiter.future.done():
                waiter.future.set_result(msg)
                with contextlib.suppress(ValueError):
                    self._waiters.remove(waiter)

    async def _send_command_long(
        self,
        command: int,
        *,
        param1: float = 0.0,
        param2: float = 0.0,
        param3: float = 0.0,
        param4: float = 0.0,
        param5: float = 0.0,
        param6: float = 0.0,
        param7: float = 0.0,
    ) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()
        ack = self._create_waiter(
            lambda msg: (
                msg.get_type() == "COMMAND_ACK" and int(getattr(msg, "command", -1)) == int(command)
            )
        )
        await loop.run_in_executor(
            None,
            lambda: mav.mav.command_long_send(
                mav.target_system,
                mav.target_component,
                command,
                0,
                param1,
                param2,
                param3,
                param4,
                param5,
                param6,
                param7,
            ),
        )
        try:
            msg = await asyncio.wait_for(ack, timeout=self._response_timeout_s)
        except TimeoutError as exc:
            raise MAVLinkCommandError(
                f"COMMAND_LONG {command} timed out waiting for COMMAND_ACK"
            ) from exc
        finally:
            self._waiters = [w for w in self._waiters if w.future is not ack]
        result = int(getattr(msg, "result", -1))
        if result != mavutil.mavlink.MAV_RESULT_ACCEPTED:
            raise MAVLinkCommandError(f"COMMAND_LONG {command} rejected with MAV_RESULT {result}")

    async def _set_param(self, name: str, value: float) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()
        padded_name = name.encode("ascii").ljust(16, b"\x00")[:16]
        expected = name.rstrip("\x00")
        param_echo = self._create_waiter(
            lambda msg: msg.get_type() == "PARAM_VALUE" and _param_id(msg) == expected
        )
        # PX4 accepts PARAM_SET; ArduPilot accepts both PARAM_SET and PARAM_VALUE.
        await loop.run_in_executor(
            None,
            lambda: mav.mav.param_set_send(
                mav.target_system,
                mav.target_component,
                padded_name,
                float(value),
                mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
            ),
        )
        try:
            msg = await asyncio.wait_for(param_echo, timeout=self._response_timeout_s)
        except TimeoutError as exc:
            raise MAVLinkTimeoutError(
                f"PARAM_SET {name!r} timed out waiting for PARAM_VALUE"
            ) from exc
        finally:
            self._waiters = [w for w in self._waiters if w.future is not param_echo]
        echoed = float(getattr(msg, "param_value", math.nan))
        if not math.isfinite(echoed) or abs(echoed - float(value)) > 1e-3:
            raise MAVLinkProtocolError(
                f"PARAM_SET {name!r} echo mismatch: expected {value}, got {echoed}"
            )

    async def _set_mode_auto_mission(self) -> None:
        mav = self._require_mav()
        loop = asyncio.get_running_loop()
        base = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom = _custom_mode_auto_mission()
        mode_echo = self._create_waiter(
            lambda msg: (
                msg.get_type() == "HEARTBEAT" and int(getattr(msg, "custom_mode", -1)) == custom
            )
        )
        await loop.run_in_executor(
            None,
            lambda: mav.mav.set_mode_send(
                mav.target_system,
                base,
                custom,
            ),
        )
        try:
            await asyncio.wait_for(mode_echo, timeout=self._response_timeout_s)
        except TimeoutError as exc:
            raise MAVLinkTimeoutError(
                "SET_MODE AUTO.MISSION timed out waiting for matching HEARTBEAT"
            ) from exc
        finally:
            self._waiters = [w for w in self._waiters if w.future is not mode_echo]


# ── small helpers exposed for tests ────────────────────────────────────────────


def point_in_polygon(lat: float, lon: float, polygon: tuple[Geo, ...]) -> bool:
    """Public alias for the private ray-cast used by `set_safety` enforcement."""
    return _point_in_polygon(lat, lon, polygon)


# `math` is used for NaN comparisons; re-export to avoid a Ruff F401.
_ = math

__all__ = (
    "HEARTBEAT_TIMEOUT_S",
    "MAVLinkAdapter",
    "MAVLinkAdapterError",
    "MAVLinkCaptureUnavailable",
    "MAVLinkCommandError",
    "MAVLinkConnectionError",
    "MAVLinkMissionError",
    "MAVLinkProtocolError",
    "MAVLinkTimeoutError",
    "RejectedMission",
    "point_in_polygon",
)
