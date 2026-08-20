from __future__ import annotations

import pytest
from swarm_core.capabilities import Capability
from swarm_core.messages import AgentState, FleetState, Geo, Telemetry

from swarm_os.coordinator import SwarmCoordinator
from swarm_os.state import SwarmState, VINEYARD_CENTER


@pytest.mark.asyncio
async def test_capabilities_survive_fleet_state_and_telemetry_projection() -> None:
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)
    capabilities = [
        Capability.THERMAL_OBSERVATION.value,
        Capability.VISUAL_OBSERVATION.value,
    ]

    await coordinator.apply_fleet_state(
        FleetState(
            agent_id="sim-capable",
            vendor="simulated",
            model="x500",
            fsm_state=AgentState.DOCKED,
            battery_pct=92.0,
            geo=VINEYARD_CENTER,
            capabilities=capabilities,
        )
    )

    assert state.units["sim-capable"].capabilities == capabilities

    # Telemetry updates position/battery but must not erase physical-capacity
    # facts learned from the canonical fleet-state frame.
    await coordinator.apply_telemetry(
        Telemetry(
            agent_id="sim-capable",
            geo=Geo(
                lat=VINEYARD_CENTER.lat + 0.0001,
                lon=VINEYARD_CENTER.lon,
                alt_m=12.0,
            ),
            battery_pct=90.0,
        )
    )

    assert state.units["sim-capable"].capabilities == capabilities
