"""DJI Payload SDK adapter — STUB.

Real wiring requires a DJI PSDK 3.x C++ build cross-compiled for the onboard SoC
plus a Python ↔ PSDK IPC bridge. The contract here is identical to every other
adapter; the body is empty until SWARM ships its own onboard compute.
"""

from __future__ import annotations

from swarm_core.messages import SensorKind

from adapters._stub import StubAdapter
from adapters.base import Capabilities, Failsafes


class DJIPSDKAdapter(StubAdapter):
    vendor: str = "dji_psdk"

    def __init__(self, *, agent_id: str, model: str = "matrice-3d-psdk") -> None:
        super().__init__(agent_id=agent_id, model=model)
        self.capabilities = Capabilities(
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL, SensorKind.MULTISPECTRAL}),
            has_obstacle_avoidance=True,
            has_rtk=True,
            has_payload_drop=False,
            max_flight_time_s=2700.0,
            max_speed_mps=15.0,
            max_altitude_m=500.0,
        )
        self.autopilot_failsafes = Failsafes(low_battery_threshold_pct=25.0)
