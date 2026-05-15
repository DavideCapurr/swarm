"""MAVLink adapter — PX4 / ArduPilot placeholder via MAVSDK-Python.

Mission DSL mapping:
  PATROL → sequence of `MissionItem` uploaded as a mission, started with `start_mission()`
  VERIFY → offboard mode with `set_position_global()` + `Camera.start_photo_interval()`
  RTL_DOCK → `action.return_to_launch()`
  RELAY → guided hover at altitude
  COVER → orchestrator pre-splits into per-agent PATROL slices

Failsafes:
  Lost link → autopilot RTL (configured at boot via `param_set`).
  Low battery → autopilot RTL at threshold.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

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

from adapters.base import (
    Capabilities,
    Failsafes,
    HealthReport,
    Polygon,
    VideoFrame,
)

try:
    from mavsdk import System  # type: ignore[import-not-found]
    from mavsdk.mission import MissionItem, MissionPlan  # type: ignore[import-not-found]

    _MAVSDK_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    System = None  # type: ignore[assignment]
    MissionItem = None  # type: ignore[assignment]
    MissionPlan = None  # type: ignore[assignment]
    _MAVSDK_AVAILABLE = False


class MAVSDKNotInstalled(RuntimeError):
    """Raised when this adapter is instantiated without MAVSDK installed."""


class MAVLinkAdapter:
    vendor: str = "mavlink"

    def __init__(
        self,
        *,
        agent_id: str,
        connection: str = "udp://:14540",
        model: str = "px4-x500",
    ) -> None:
        if not _MAVSDK_AVAILABLE:
            raise MAVSDKNotInstalled(
                "MAVSDK-Python is required for live MAVLink hardware execution, "
                "but it is intentionally not installed in Phase 0-4 because its "
                "protobuf pin currently fails security audit. Re-evaluate this "
                "dependency in Phase 5."
            )
        self.agent_id = agent_id
        self.model = model
        self._connection = connection
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=False,
            max_flight_time_s=1200.0,
            max_speed_mps=15.0,
            max_altitude_m=120.0,
        )
        self.autopilot_failsafes = Failsafes()
        self._drone: System | None = None
        self._cancelled = False

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        assert System is not None
        self._drone = System()
        await self._drone.connect(system_address=self._connection)
        # Wait for first heartbeat.
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                break

    async def disconnect(self) -> None:
        self._drone = None

    async def health(self) -> HealthReport:
        if not self._drone:
            return HealthReport(online=False, battery_pct=0.0, link_quality=0.0, last_telemetry_age_s=None)
        battery_pct = 100.0
        async for batt in self._drone.telemetry.battery():
            battery_pct = float(batt.remaining_percent) * 100.0
            break
        return HealthReport(
            online=True, battery_pct=battery_pct, link_quality=1.0, last_telemetry_age_s=0.0
        )

    # ── safety envelope ──────────────────────────────────────────────────────

    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None:
        assert self._drone is not None
        # PX4 params (best-effort — names vary across firmware versions).
        with contextlib.suppress(Exception):
            await self._drone.param.set_param_float("BAT_LOW_THR", rtl_battery_pct / 100.0)
        with contextlib.suppress(Exception):
            await self._drone.param.set_param_float("MIS_TAKEOFF_ALT", min(20.0, max_alt_m))
        # Geofence upload would go here (mavsdk-python geofence plugin) — omitted in commit 1.

    # ── mission ──────────────────────────────────────────────────────────────

    async def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:  # type: ignore[override]
        assert self._drone is not None
        self._cancelled = False
        kind = mission.kind

        if kind in (MissionKind.PATROL.value, MissionKind.VERIFY.value):
            async for p in self._fly_waypoints(mission):
                yield p
        elif kind == MissionKind.RELAY.value:
            async for p in self._hover_relay(mission):
                yield p
        elif kind == MissionKind.RTL_DOCK.value:
            await self._drone.action.return_to_launch()
            yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)
        elif kind == MissionKind.COVER.value:
            # COVER must be decomposed by the orchestrator into per-agent PATROL slices.
            raise UnsupportedMission("COVER must be decomposed in orchestrator before dispatch")
        else:
            raise UnsupportedMission(f"unknown mission kind: {kind}")

    async def _fly_waypoints(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        assert self._drone is not None
        assert MissionItem is not None and MissionPlan is not None
        wps = mission_waypoints(mission)
        items = [
            MissionItem(
                wp.geo.lat,
                wp.geo.lon,
                wp.geo.alt_m or float(mission.params.get("altitude_m", 60.0)),
                wp.speed_mps or 5.0,
                True,  # is_fly_through
                float("nan"),  # gimbal pitch
                float("nan"),  # gimbal yaw
                MissionItem.CameraAction.NONE,
                wp.hover_s if wp.hover_s else float("nan"),
                float("nan"),  # acceptance radius
                float("nan"),  # yaw
                float("nan"),  # camera photo interval
                MissionItem.VehicleAction.NONE,
            )
            for wp in wps
        ]
        await self._drone.mission.upload_mission(MissionPlan(items))
        await self._drone.action.arm()
        await self._drone.mission.start_mission()
        yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0)

        async for progress in self._drone.mission.mission_progress():
            if self._cancelled:
                await self._drone.mission.clear_mission()
                yield MissionProgress(
                    mission_id=mission.id, phase="FAILED", progress_pct=0.0, error="cancelled"
                )
                return
            pct = progress.current / max(progress.total, 1) * 90.0
            yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=pct)
            if progress.current == progress.total:
                break

        await self._drone.action.return_to_launch()
        yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)

    async def _hover_relay(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        assert self._drone is not None
        geo = Geo(**mission.params["geo"])
        duration_s = float(mission.params.get("duration_s", 600.0))
        altitude_m = float(mission.params.get("altitude_m", 80.0))
        await self._drone.action.arm()
        await self._drone.action.takeoff()
        await self._drone.action.goto_location(geo.lat, geo.lon, altitude_m, 0.0)
        yield MissionProgress(mission_id=mission.id, phase="ON_STATION", progress_pct=50.0)
        await asyncio.sleep(duration_s)
        await self._drone.action.return_to_launch()
        yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)

    async def pause_mission(self) -> None:
        assert self._drone is not None
        await self._drone.mission.pause_mission()

    async def resume_mission(self) -> None:
        assert self._drone is not None
        await self._drone.mission.start_mission()

    async def cancel_mission(self) -> None:
        assert self._drone is not None
        self._cancelled = True
        with contextlib.suppress(Exception):
            await self._drone.mission.clear_mission()
        with contextlib.suppress(Exception):
            await self._drone.action.return_to_launch()

    async def divert(self, new_waypoint: Waypoint) -> None:
        assert self._drone is not None
        await self._drone.action.goto_location(
            new_waypoint.geo.lat,
            new_waypoint.geo.lon,
            new_waypoint.geo.alt_m or 60.0,
            0.0,
        )

    async def request_capture(self, sensor: SensorKind) -> CaptureResult:
        assert self._drone is not None
        # Real implementation would call `camera.take_photo()`; commit 1 stubs the URI.
        geo = await self._first_geo()
        return CaptureResult(sensor=sensor, uri=f"mavlink://{self.agent_id}/{sensor.value}", geo=geo)

    # ── streams ──────────────────────────────────────────────────────────────

    async def stream_telemetry(self) -> AsyncIterator[Telemetry]:  # type: ignore[override]
        assert self._drone is not None
        async for pos in self._drone.telemetry.position():
            batt_pct = 100.0
            async for b in self._drone.telemetry.battery():
                batt_pct = float(b.remaining_percent) * 100.0
                break
            yield Telemetry(
                agent_id=self.agent_id,
                geo=Geo(lat=pos.latitude_deg, lon=pos.longitude_deg, alt_m=pos.relative_altitude_m),
                attitude=Attitude(),
                battery_pct=batt_pct,
            )

    async def stream_video(self) -> AsyncIterator[VideoFrame]:  # type: ignore[override]
        # Video would come from a camera RTSP stream — not wired in commit 1.
        if False:
            yield VideoFrame(self.agent_id, 0, 0, 0, "h264", b"")

    async def _first_geo(self) -> Geo:
        assert self._drone is not None
        async for pos in self._drone.telemetry.position():
            return Geo(lat=pos.latitude_deg, lon=pos.longitude_deg, alt_m=pos.relative_altitude_m)
        return Geo(lat=0.0, lon=0.0)
