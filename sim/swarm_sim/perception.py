"""Mock perception layer — injects anomalies on a schedule.

In commit 1 this is intentionally simple: at configured times the perception
emits a `SMOKE` anomaly at a random or pre-set geo. The interface
(`emit_anomaly`) is the same the future CV model will satisfy — when the
PyTorch detector in `ml/anomaly/` is ready, it replaces this implementation
without touching the orchestrator.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from swarm_core.geometry import haversine_m
from swarm_core.messages import Anomaly, AnomalyKind, Geo

if TYPE_CHECKING:  # pragma: no cover
    from sim.swarm_sim.drone import Drone

# A drone counts as "on station over the anomaly" when it is airborne and
# within this radius of the anomaly geo. Deliberately a little more generous
# than the drone's own 5 m at-target threshold (drone.py:_AT_TARGET_THRESHOLD_M)
# to tolerate hover drift and the haversine/equirectangular difference, while
# still far below the dock-to-hotspot separation (~47 m in the wildfire
# scenario) so an idle docked drone can never falsely confirm.
_CONFIRM_RADIUS_M = 15.0


@dataclass
class IgnitionEvent:
    """A scripted "fire ignites here at t_s seconds" event for demos."""

    after_s: float
    geo: Geo
    kind: AnomalyKind = AnomalyKind.SMOKE
    confidence: float = 0.78


@dataclass
class MockPerception:
    """Emits anomalies according to a schedule (or randomly)."""

    territory_center: Geo
    territory_radius_m: float = 600.0
    ignitions: list[IgnitionEvent] = field(default_factory=list)
    on_anomaly: Callable[[Anomaly], None] | None = None
    rng: random.Random = field(default_factory=random.Random)
    # Phase 7.B — confirm-by-observation. A dispatched drone that dwells over
    # the anomaly for this long makes the sim re-emit it with verified=True.
    confirm_dwell_s: float = 2.5
    # Unverified anomalies we have emitted, keyed by id, awaiting a drone to
    # physically reach them. Accumulated on-station dwell + the ids we have
    # already confirmed so we re-emit verified=True exactly once per anomaly.
    _emitted: dict[str, Anomaly] = field(default_factory=dict)
    _dwell_s: dict[str, float] = field(default_factory=dict)
    _confirmed: set[str] = field(default_factory=set)

    async def run(self) -> None:
        """Schedule the ignitions and emit anomalies as they fire."""
        if not self.ignitions:
            return
        # Sort by after_s and emit each on time.
        for ev in sorted(self.ignitions, key=lambda e: e.after_s):
            await asyncio.sleep(ev.after_s)
            self.emit_anomaly(ev.kind, ev.geo, ev.confidence)

    def emit_anomaly(self, kind: AnomalyKind, geo: Geo, confidence: float) -> Anomaly:
        a = Anomaly(kind=kind, geo=geo, confidence=confidence)
        self._emitted[a.id] = a
        if self.on_anomaly:
            self.on_anomaly(a)
        return a

    def observe(self, drones: Sequence[Drone], dt: float) -> None:
        """Confirm anomalies a drone is physically on-station over.

        Phase 7.B — verification truth stays in the honest simulator. When a
        dispatched drone reaches an anomaly's geo and dwells for
        `confirm_dwell_s`, re-emit that *same* anomaly (same id / kind / geo /
        confidence) with `verified=True` through the existing `on_anomaly`
        hook. The coordinator's `apply_anomaly` then flips it to VERIFIED and
        the R2 floor (0.80) decides whether it escalates — SwarmOS still only
        *decides*, never invents the confirmation.
        """

        for aid, anomaly in self._emitted.items():
            if aid in self._confirmed:
                continue
            on_station = any(
                d.is_airborne and haversine_m(d.geo, anomaly.geo) < _CONFIRM_RADIUS_M
                for d in drones
            )
            if not on_station:
                # Require *continuous* dwell — a brief fly-through doesn't count.
                self._dwell_s[aid] = 0.0
                continue
            self._dwell_s[aid] = self._dwell_s.get(aid, 0.0) + dt
            if self._dwell_s[aid] >= self.confirm_dwell_s:
                self._confirmed.add(aid)
                confirmed = anomaly.model_copy(update={"verified": True})
                if self.on_anomaly:
                    self.on_anomaly(confirmed)

    def random_point_in_territory(self) -> Geo:
        """Pick a roughly uniform point in a disk around the territory center."""
        import math

        r = self.territory_radius_m * (self.rng.random() ** 0.5)
        theta = self.rng.uniform(0, 2 * math.pi)
        m_per_deg = 111_000.0
        dlat = (r * math.sin(theta)) / m_per_deg
        dlon = (r * math.cos(theta)) / m_per_deg
        return Geo(
            lat=self.territory_center.lat + dlat,
            lon=self.territory_center.lon + dlon,
        )
