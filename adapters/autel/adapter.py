from __future__ import annotations

from swarm_core.messages import SensorKind

from adapters._stub import StubAdapter
from adapters.base import Capabilities, Failsafes


class AutelAdapter(StubAdapter):
    vendor: str = "autel"

    def __init__(self, *, agent_id: str, model: str = "evo-max-4t") -> None:
        super().__init__(agent_id=agent_id, model=model)
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=True,
            has_rtk=True,
            max_flight_time_s=2400.0,
            max_speed_mps=20.0,
            max_altitude_m=500.0,
        )
        self.autopilot_failsafes = Failsafes(low_battery_threshold_pct=20.0)
