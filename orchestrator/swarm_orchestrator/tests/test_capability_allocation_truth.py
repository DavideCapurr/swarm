from __future__ import annotations

import asyncio
import json

import pytest
from swarm_core.messages import Anomaly, AnomalyKind, SensorKind

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.service import Orchestrator
from sim.swarm_sim.world import World


@pytest.mark.asyncio
async def test_intrusion_publishes_capability_requirement_and_mismatch() -> None:
    world = World.vineyard(n_drones=2, ignition_after_s=999.0)
    registry = AdapterRegistry()
    adapters = [
        SimulatedAdapter(
            agent_id=world.drones[0].agent_id,
            drone=world.drones[0],
            sensors=frozenset({SensorKind.THERMAL}),
        ),
        SimulatedAdapter(
            agent_id=world.drones[1].agent_id,
            drone=world.drones[1],
            sensors=frozenset({SensorKind.RGB, SensorKind.THERMAL}),
        ),
    ]
    for adapter in adapters:
        await adapter.connect()
        registry.register(adapter)

    bus = InMemoryBus()
    await bus.connect()
    orchestrator = Orchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        verify_hover_s=0.0,
    )
    task = asyncio.create_task(orchestrator.run())

    async def next_allocation() -> dict[str, object]:
        async for _, payload in bus.subscribe("swarm:allocations"):
            return json.loads(payload)
        raise AssertionError("allocation stream ended")

    allocation_task = asyncio.create_task(next_allocation())
    await asyncio.sleep(0.05)

    anomaly = Anomaly(
        kind=AnomalyKind.INTRUSION,
        geo=world.dock,
        confidence=0.71,
    )
    await bus.publish("swarm:anomalies", anomaly.model_dump_json())

    decision = await asyncio.wait_for(allocation_task, timeout=3.0)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    for adapter in adapters:
        await adapter.disconnect()
    await bus.close()

    assert decision["required_capabilities"] == ["visual_observation"]
    assert decision["winner_agent_id"] == "sim-2"

    excluded = decision["excluded_units"]
    assert isinstance(excluded, list)
    mismatch = next(row for row in excluded if row["agent_id"] == "sim-1")
    assert mismatch["reason"] == "CAPABILITY_MISMATCH"
    assert mismatch["capabilities"] == ["thermal_observation"]
