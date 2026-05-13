"""Kinematic drone model used by the simulated adapter.

The drone is a point-mass with capped horizontal speed and capped climb rate.
It exposes commands the adapter calls: takeoff, goto, hover, rtl. Each `step`
advances the internal state by `dt` seconds.

Not aerodynamics. Not Gazebo. Enough to validate orchestration logic end-to-end.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from swarm_core.messages import Geo

_TAKEOFF_TARGET_ALT_M = 30.0
_LANDING_THRESHOLD_M = 1.5
_AT_TARGET_THRESHOLD_M = 5.0
_M_PER_DEG = 111_000.0  # equirectangular approximation


def _planar_distance_m(a: Geo, b: Geo) -> float:
    """Quick planar distance in meters (equirectangular approximation)."""

    dx = (b.lon - a.lon) * math.cos(math.radians((a.lat + b.lat) / 2.0)) * _M_PER_DEG
    dy = (b.lat - a.lat) * _M_PER_DEG
    return math.hypot(dx, dy)


@dataclass
class Drone:
    """A single kinematic drone."""

    agent_id: str
    dock: Geo
    geo: Geo = field(init=False)
    target: Geo | None = None
    speed_mps: float = 10.0
    climb_mps: float = 3.0
    battery_pct: float = 100.0
    battery_drain_pct_per_s: float = 0.05  # ≈100% in ~33 min
    yaw_deg: float = 0.0
    rtl_battery_pct: float = 20.0
    max_alt_m: float = 120.0
    geofence: Sequence[Geo] | None = None

    # Internal state
    _mode: str = "DOCKED"  # "DOCKED" | "TAKEOFF" | "FLYING" | "HOVER" | "LANDING"
    _rtl_pending: bool = False

    def __post_init__(self) -> None:
        self.geo = Geo(lat=self.dock.lat, lon=self.dock.lon, alt_m=0.0)

    # ── derived state ───────────────────────────────────────────────────────

    @property
    def is_docked(self) -> bool:
        return self._mode == "DOCKED"

    @property
    def is_airborne(self) -> bool:
        return self._mode in ("FLYING", "HOVER")

    def at_target(self, target: Geo) -> bool:
        return _planar_distance_m(self.geo, target) < _AT_TARGET_THRESHOLD_M

    # ── commands (called by the adapter) ────────────────────────────────────

    def command_takeoff(self) -> None:
        if self._mode == "DOCKED":
            self._mode = "TAKEOFF"

    def command_goto(self, geo: Geo) -> None:
        # Clamp altitude to max_alt_m for safety.
        alt = min(geo.alt_m or _TAKEOFF_TARGET_ALT_M, self.max_alt_m)
        self.target = Geo(lat=geo.lat, lon=geo.lon, alt_m=alt)
        if self._mode in ("HOVER", "FLYING"):
            self._mode = "FLYING"

    def command_hover(self) -> None:
        if self.is_airborne:
            self._mode = "HOVER"
            self.target = None

    def command_rtl(self) -> None:
        self._rtl_pending = True
        self.target = Geo(lat=self.dock.lat, lon=self.dock.lon, alt_m=_TAKEOFF_TARGET_ALT_M)
        if self.is_airborne:
            self._mode = "FLYING"

    # ── integration step ────────────────────────────────────────────────────

    def step(self, dt: float) -> None:
        """Advance internal state by `dt` seconds."""

        # Battery drains whenever motors are spinning (anything non-DOCKED).
        if self._mode != "DOCKED":
            self.battery_pct = max(0.0, self.battery_pct - self.battery_drain_pct_per_s * dt)

        # Auto-RTL on low battery.
        if (
            self.battery_pct <= self.rtl_battery_pct
            and self._mode in ("FLYING", "HOVER")
            and not self._rtl_pending
        ):
            self.command_rtl()

        if self._mode == "TAKEOFF":
            self.geo = Geo(
                lat=self.geo.lat,
                lon=self.geo.lon,
                alt_m=min(self.geo.alt_m + self.climb_mps * dt, _TAKEOFF_TARGET_ALT_M),
            )
            if self.geo.alt_m >= _TAKEOFF_TARGET_ALT_M - 0.1:
                self._mode = "FLYING" if self.target else "HOVER"
            return

        if self._mode == "FLYING" and self.target is not None:
            d = _planar_distance_m(self.geo, self.target)
            if d < _AT_TARGET_THRESHOLD_M:
                # Arrived horizontally — handle vertical and dock landing if RTL.
                if self._rtl_pending:
                    self._mode = "LANDING"
                else:
                    self._mode = "HOVER"
                return
            step_m = min(self.speed_mps * dt, d)
            ratio = step_m / d
            dlat = (self.target.lat - self.geo.lat) * ratio
            dlon = (self.target.lon - self.geo.lon) * ratio
            new_lat = self.geo.lat + dlat
            new_lon = self.geo.lon + dlon
            # Track altitude separately at climb_mps rate.
            dz = (self.target.alt_m or _TAKEOFF_TARGET_ALT_M) - self.geo.alt_m
            dz_step = max(-self.climb_mps * dt, min(self.climb_mps * dt, dz))
            new_alt = self.geo.alt_m + dz_step
            self.geo = Geo(lat=new_lat, lon=new_lon, alt_m=new_alt)
            self.yaw_deg = math.degrees(math.atan2(dlon, dlat)) % 360.0
            return

        if self._mode == "LANDING":
            new_alt = max(0.0, self.geo.alt_m - self.climb_mps * dt)
            self.geo = Geo(lat=self.geo.lat, lon=self.geo.lon, alt_m=new_alt)
            if new_alt < _LANDING_THRESHOLD_M:
                self._mode = "DOCKED"
                self._rtl_pending = False
                # Snap to dock and start charging.
                self.geo = Geo(lat=self.dock.lat, lon=self.dock.lon, alt_m=0.0)

        if self._mode == "DOCKED" and self.battery_pct < 100.0:
            # Charge at 1% per second while docked (instant relative to flight times).
            self.battery_pct = min(100.0, self.battery_pct + 1.0 * dt)
