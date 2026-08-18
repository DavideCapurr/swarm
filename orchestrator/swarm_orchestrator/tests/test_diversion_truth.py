"""A diverted unit is the executor, never also an exclusion.

Under continuous patrol every unit is airborne, so no unit is eligible and the
allocator falls through to the diversion branch. The frame it publishes is what
the Console renders verbatim, so it must not describe one agent two
contradictory ways — `winner_agent_id` and `excluded_units` are disjoint.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from swarm_core.messages import Anomaly, AnomalyKind, Geo

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.service import Orchestrator
from sim.swarm_sim.world import World


@pytest.mark.asyncio
async def test_diverted_winner_is_not_published_as_excluded() -> None:
    world = World.vineyard(n_drones=3, ignition_after_s=999.0)
    for drone in world.drones:
        drone.speed_mps = 200.0
        drone.climb_mps = 30.0

    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    for drone in world.drones:
        adapter = SimulatedAdapter(agent_id=drone.agent_id, drone=drone, self_tick=False)
        await adapter.connect()
        registry.register(adapter)
        adapters.append(adapter)

    bus = InMemoryBus()
    await bus.connect()

    orch = Orchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        verify_hover_s=0.2,
        continuous_patrol=True,
        patrol_origin=world.dock,
        patrol_radius_m=130.0,
        patrol_period_s=0.2,
    )

    async def tick_world() -> None:
        while True:
            world.step(0.05)
            await asyncio.sleep(0.005)

    decisions: list[Any] = []

    async def watch_allocations() -> None:
        async for _, payload in bus.subscribe("swarm:allocations"):
            decisions.append(json.loads(payload))

    tick = asyncio.create_task(tick_world())
    orch_task = asyncio.create_task(orch.run())
    watcher = asyncio.create_task(watch_allocations())

    # Let the whole fleet leave the dock, so nothing is available to bid.
    await asyncio.sleep(1.5)

    await bus.publish(
        "swarm:anomalies",
        Anomaly(
            kind=AnomalyKind.SMOKE,
            geo=Geo(lat=world.dock.lat + 0.0012, lon=world.dock.lon + 0.0008),
            confidence=0.8,
        ).model_dump_json(),
    )

    deadline = asyncio.get_running_loop().time() + 15.0
    while not any(d["mode"] == "diversion" for d in decisions):
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"no diversion decision published: {decisions}")
        await asyncio.sleep(0.05)

    for task in (orch_task, tick, watcher):
        task.cancel()
    for adapter in adapters:
        await adapter.disconnect()
    await bus.close()

    diversions = [d for d in decisions if d["mode"] == "diversion"]
    for decision in diversions:
        winner = decision["winner_agent_id"]
        assert winner is not None
        excluded = {row["agent_id"] for row in decision["excluded_units"]}
        assert winner not in excluded, (
            f"{winner} published as both the winner and an exclusion: {decision}"
        )
        # A diverted unit never bid, so it carries no auction score.
        assert decision["winner_score"] is None
        # The mission it was pulled off is stated, not dropped.
        assert "diverted_from_mission_id" in decision
