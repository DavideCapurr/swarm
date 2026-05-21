"""The simulated world — vineyard with a dock, drones, and anomaly injector.

The `World` owns the simulation state and advances all drones each tick. It does
not know about the bus, the orchestrator, or the backend; it just exposes
`drones`, `perception`, and a `step(dt)` method.

The runner (`sim.swarm_sim.runner`) wires this up to the bus and adapter layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from swarm_core.messages import AnomalyKind, Geo

from sim.swarm_sim.drone import Drone
from sim.swarm_sim.perception import IgnitionEvent, MockPerception

if TYPE_CHECKING:
    # Phase 7.D — opt-in. `CVPerception` is the same shape as
    # `MockPerception` (structural typing) so a union here keeps the
    # diff minimal and avoids promoting Perception to a Protocol until
    # a third implementor lands (Phase 19).
    from sim.swarm_sim.cv.perception_cv import CVPerception

# A representative northern-Italian vineyard — Langhe, near Alba.
DEFAULT_DOCK = Geo(lat=44.7000, lon=8.0300, alt_m=0.0)


@dataclass
class World:
    """Container for sim state."""

    dock: Geo = field(default_factory=lambda: DEFAULT_DOCK)
    drones: list[Drone] = field(default_factory=list)
    perception: MockPerception | CVPerception | None = None
    t_s: float = 0.0

    @classmethod
    def vineyard(cls, *, n_drones: int = 3, ignition_after_s: float = 10.0) -> World:
        dock = DEFAULT_DOCK
        drones = [Drone(agent_id=f"sim-{i + 1}", dock=dock) for i in range(n_drones)]
        # Scripted ignition somewhere ~300 m NE of the dock.
        ignition_geo = Geo(lat=dock.lat + 0.0027, lon=dock.lon + 0.0027)
        perception = MockPerception(
            territory_center=dock,
            territory_radius_m=600.0,
            ignitions=[
                IgnitionEvent(
                    after_s=ignition_after_s,
                    geo=ignition_geo,
                    kind=AnomalyKind.SMOKE,
                    confidence=0.78,
                )
            ],
        )
        return cls(dock=dock, drones=drones, perception=perception)

    def step(self, dt: float) -> None:
        """Advance every drone by dt seconds."""
        self.t_s += dt
        for d in self.drones:
            d.step(dt)
