from __future__ import annotations

from swarm_core.messages import SensorKind

from adapters._stub import StubAdapter
from adapters.base import Capabilities, Failsafes


class ParrotAdapter(StubAdapter):
    vendor: str = "parrot"

    def __init__(self, *, agent_id: str, model: str = "anafi-ai") -> None:
        super().__init__(agent_id=agent_id, model=model)
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
            has_obstacle_avoidance=True,
            has_rtk=False,
            max_flight_time_s=1980.0,  # ~33 min for ANAFI Ai
            max_speed_mps=14.0,
            max_altitude_m=120.0,
        )
        self.autopilot_failsafes = Failsafes(low_battery_threshold_pct=20.0)
