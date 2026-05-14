"""Simulated DroneAdapter implementation.

The adapter speaks the canonical SWARM `DroneAdapter` Protocol but flies a
deterministic kinematic drone defined in `sim.swarm_sim.drone.Drone`. It is the
reference implementation against which the conformance suite is validated.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

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
from swarm_core.missions import MissionKind, mission_waypoints

from adapters.base import (
    Capabilities,
    DroneAdapter,
    Failsafes,
    HealthReport,
    Polygon,
    VideoFrame,
)


class SimulatedAdapter:
    """Reference adapter — drives a `sim.swarm_sim.drone.Drone` instance."""

    vendor: str = "simulated"

    def __init__(
        self,
        *,
        agent_id: str,
        drone: Any,
        model: str = "sim-x500",
        self_tick: bool = True,
        tick_hz: float = 50.0,
    ) -> None:
        # `drone` is `sim.swarm_sim.drone.Drone` but typed as Any here to keep
        # `adapters/` free of `sim/` imports. The dependency is one-way: sim
        # never imports adapters.
        #
        # `self_tick=True` (default) spawns a background task that steps the
        # drone — useful for tests and standalone adapter usage. Set False when
        # an external world ticker owns time (e.g. in `sim.swarm_sim.runner`,
        # which steps the World atomically so all drones advance in lockstep).
        self.agent_id = agent_id
        self.model = model
        self._drone = drone
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=False,
            max_flight_time_s=600.0,
            max_speed_mps=12.0,
            max_altitude_m=120.0,
        )
        self.autopilot_failsafes = Failsafes()
        self._connected = False
        self._cancelled = False
        self._paused = False
        self._self_tick = self_tick
        self._tick_hz = tick_hz
        self._tick_task: asyncio.Task[None] | None = None

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._connected = True
        if self._self_tick and self._tick_task is None:
            self._tick_task = asyncio.create_task(self._tick_loop())

    async def disconnect(self) -> None:
        import contextlib

        self._connected = False
        if self._tick_task is not None:
            self._tick_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tick_task
            self._tick_task = None

    async def _tick_loop(self) -> None:
        dt = 1.0 / self._tick_hz
        while self._connected:
            self._drone.step(dt)
            await asyncio.sleep(dt)

    async def health(self) -> HealthReport:
        return HealthReport(
            online=self._connected,
            battery_pct=self._drone.battery_pct,
            link_quality=1.0,
            last_telemetry_age_s=0.0,
        )

    # ── safety envelope ──────────────────────────────────────────────────────

    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None:
        self._drone.geofence = geofence.points
        self._drone.max_alt_m = max_alt_m
        self._drone.rtl_battery_pct = float(rtl_battery_pct)

    # ── mission ──────────────────────────────────────────────────────────────

    async def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:  # type: ignore[override]
        if not self._connected:
            raise RuntimeError("adapter not connected")
        self._cancelled = False
        self._paused = False
        async for p in self._execute(mission):
            yield p

    async def _execute(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        kind = mission.kind

        # Take off if currently docked.
        if self._drone.is_docked:
            self._drone.command_takeoff()
            while not self._drone.is_airborne and not self._cancelled:
                await asyncio.sleep(0.05)
            yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0)

        waypoints = mission_waypoints(mission)
        total = len(waypoints) or 1

        for i, wp in enumerate(waypoints):
            if self._cancelled:
                break
            while self._paused and not self._cancelled:
                await asyncio.sleep(0.1)

            self._drone.command_goto(wp.geo)
            while not self._drone.at_target(wp.geo) and not self._cancelled:
                await asyncio.sleep(0.05)
                if self._paused:
                    self._drone.command_hover()

            yield MissionProgress(
                mission_id=mission.id,
                phase="ON_STATION" if kind == MissionKind.VERIFY.value else "EN_ROUTE",
                progress_pct=(i + 1) / total * 80.0,
            )

            # Hover & capture for VERIFY.
            if kind == MissionKind.VERIFY.value:
                hover_s = float(mission.params.get("hover_s", 0.0))
                self._drone.command_hover()
                t0 = time.monotonic()
                while time.monotonic() - t0 < hover_s and not self._cancelled:
                    await asyncio.sleep(0.1)
                for sensor_str in mission.params.get("sensors", []):
                    await self.request_capture(SensorKind(sensor_str))
                yield MissionProgress(
                    mission_id=mission.id, phase="ON_STATION", progress_pct=85.0
                )

            if kind == MissionKind.RELAY.value:
                duration_s = float(mission.params.get("duration_s", 0.0))
                self._drone.command_hover()
                t0 = time.monotonic()
                while time.monotonic() - t0 < duration_s and not self._cancelled:
                    await asyncio.sleep(0.1)

        # Return to dock.
        if not self._cancelled:
            self._drone.command_rtl()
            while not self._drone.is_docked and not self._cancelled:
                await asyncio.sleep(0.05)
                if self._paused:
                    self._drone.command_hover()
            yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)
        else:
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=0.0,
                error="cancelled",
            )

    async def pause_mission(self) -> None:
        self._paused = True

    async def resume_mission(self) -> None:
        self._paused = False

    async def cancel_mission(self) -> None:
        self._cancelled = True
        self._drone.command_rtl()

    async def divert(self, new_waypoint: Waypoint) -> None:
        self._drone.command_goto(new_waypoint.geo)

    async def request_capture(self, sensor: SensorKind) -> CaptureResult:
        return CaptureResult(
            sensor=sensor,
            uri=f"sim://{self.agent_id}/{sensor.value}/{int(time.time() * 1000)}",
            geo=Geo(lat=self._drone.geo.lat, lon=self._drone.geo.lon, alt_m=self._drone.geo.alt_m),
        )

    # ── streams ──────────────────────────────────────────────────────────────

    async def stream_telemetry(self) -> AsyncIterator[Telemetry]:  # type: ignore[override]
        while self._connected:
            yield Telemetry(
                agent_id=self.agent_id,
                geo=Geo(
                    lat=self._drone.geo.lat,
                    lon=self._drone.geo.lon,
                    alt_m=self._drone.geo.alt_m,
                ),
                attitude=Attitude(yaw_deg=self._drone.yaw_deg),
                velocity_mps=self._drone.speed_mps,
                battery_pct=self._drone.battery_pct,
                link_quality=1.0,
            )
            await asyncio.sleep(0.1)  # 10 Hz

    async def stream_video(self) -> AsyncIterator[VideoFrame]:  # type: ignore[override]
        # Simulated adapter does not emit real video frames.
        if False:
            yield VideoFrame(self.agent_id, 0, 0, 0, "raw_rgb", b"")

    # Ensure we satisfy the Protocol — quick runtime check.
    def __post_init__(self) -> None:  # pragma: no cover
        assert isinstance(self, DroneAdapter)
