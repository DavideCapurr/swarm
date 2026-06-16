"""End-to-end test: anomaly → auction → award → mission execution → done.

Uses the simulated adapter and the in-memory bus. No external infrastructure.
This is the smallest acceptance test that proves SWARM OS works end-to-end.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from swarm_core.messages import Anomaly, AnomalyKind, Geo

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.service import Orchestrator
from sim.swarm_sim.world import World


@pytest.mark.asyncio
async def test_anomaly_to_done_end_to_end() -> None:
    # Faster world: smaller anomaly distance, faster drones.
    world = World.vineyard(n_drones=3, ignition_after_s=999.0)  # we'll inject manually
    for d in world.drones:
        d.speed_mps = 200.0
        d.climb_mps = 30.0

    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    for d in world.drones:
        # World owns time in this test — disable adapter self-tick.
        a = SimulatedAdapter(agent_id=d.agent_id, drone=d, self_tick=False)
        await a.connect()
        registry.register(a)
        adapters.append(a)

    bus = InMemoryBus()
    await bus.connect()

    # Short hover so the whole verify cycle completes inside the test timeout.
    orch = Orchestrator(bus=bus, registry=registry, world_drones=world.drones, verify_hover_s=0.5)

    # Tick the world while the test runs.
    async def tick_world() -> None:
        while True:
            world.step(0.05)
            await asyncio.sleep(0.005)

    tick = asyncio.create_task(tick_world())
    orch_task = asyncio.create_task(orch.run())

    # Track mission progress on the bus.
    awards: list[dict[str, object]] = []
    progress_phases: list[str] = []

    async def watch_awards() -> None:
        async for _, payload in bus.subscribe("swarm:missions:award"):
            awards.append(json.loads(payload))
            return

    async def watch_progress() -> None:
        async for _, payload in bus.subscribe("swarm:missions:progress:*"):
            p = json.loads(payload)
            progress_phases.append(p["phase"])
            if p["phase"] in ("DONE", "FAILED"):
                return

    awards_task = asyncio.create_task(watch_awards())
    progress_task = asyncio.create_task(watch_progress())

    # Let the orchestrator's subscribe loop start.
    await asyncio.sleep(0.05)

    # Inject a smoke anomaly 300 m NE of the dock.
    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=Geo(lat=world.dock.lat + 0.0027, lon=world.dock.lon + 0.0027),
        confidence=0.8,
    )
    await bus.publish("swarm:anomalies", anomaly.model_dump_json())

    # Wait for auction + mission completion.
    await asyncio.wait_for(awards_task, timeout=5.0)
    await asyncio.wait_for(progress_task, timeout=15.0)

    # Tear down.
    orch_task.cancel()
    tick.cancel()
    for a in adapters:
        await a.disconnect()
    await bus.close()
    with pytest.raises(asyncio.CancelledError):
        await orch_task
    with pytest.raises(asyncio.CancelledError):
        await tick

    assert len(awards) == 1
    winner = awards[0]["winner_agent_id"]
    assert isinstance(winner, str) and winner.startswith("sim-")
    assert "DONE" in progress_phases


@pytest.mark.asyncio
async def test_continuous_patrol_moves_whole_fleet_and_still_verifies() -> None:
    """Continuous patrol must launch every unit (incl. Unit 003), keep the
    map dynamic, and still complete a VERIFY by diverting an airborne unit
    when none is docked."""

    from swarm_core.geometry import haversine_m

    world = World.vineyard(n_drones=3, ignition_after_s=999.0)
    for d in world.drones:
        d.speed_mps = 200.0
        d.climb_mps = 30.0

    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    for d in world.drones:
        a = SimulatedAdapter(agent_id=d.agent_id, drone=d, self_tick=False)
        await a.connect()
        registry.register(a)
        adapters.append(a)

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

    # Track the farthest each unit gets from its dock — proves it actually flew.
    max_dist = {d.agent_id: 0.0 for d in world.drones}

    async def tick_world() -> None:
        while True:
            world.step(0.05)
            for d in world.drones:
                max_dist[d.agent_id] = max(
                    max_dist[d.agent_id], haversine_m(d.geo, d.dock)
                )
            await asyncio.sleep(0.005)

    tick = asyncio.create_task(tick_world())
    orch_task = asyncio.create_task(orch.run())

    # Let the whole fleet get airborne and sweep their wedges.
    await asyncio.sleep(1.5)

    # Every unit — sim-1, sim-2, sim-3 — must have left the dock.
    for agent_id, dist in max_dist.items():
        assert dist > 20.0, f"{agent_id} never left the dock (max {dist:.1f} m)"

    # With the fleet airborne, an anomaly must still be verified by diverting
    # the nearest unit.
    progress_phases: list[str] = []

    async def watch_progress() -> None:
        async for _, payload in bus.subscribe("swarm:missions:progress:*"):
            p = json.loads(payload)
            progress_phases.append(p["phase"])
            if p["phase"] in ("DONE", "FAILED"):
                return

    progress_task = asyncio.create_task(watch_progress())
    await asyncio.sleep(0.05)

    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=Geo(lat=world.dock.lat + 0.0012, lon=world.dock.lon + 0.0008),
        confidence=0.8,
    )
    await bus.publish("swarm:anomalies", anomaly.model_dump_json())

    await asyncio.wait_for(progress_task, timeout=15.0)

    orch_task.cancel()
    tick.cancel()
    for a in adapters:
        await a.disconnect()
    await bus.close()
    with pytest.raises(asyncio.CancelledError):
        await orch_task
    with pytest.raises(asyncio.CancelledError):
        await tick

    assert "DONE" in progress_phases
