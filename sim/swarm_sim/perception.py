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
from collections.abc import Callable
from dataclasses import dataclass, field

from swarm_core.messages import Anomaly, AnomalyKind, Geo


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
        if self.on_anomaly:
            self.on_anomaly(a)
        return a

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
