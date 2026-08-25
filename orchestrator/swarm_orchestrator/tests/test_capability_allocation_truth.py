from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, cast

import pytest
from swarm_core.allocations import AllocationDecision, AllocationExclusionReason
from swarm_core.capabilities import Capability
from swarm_core.geometry import haversine_m
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    FleetState,
    Geo,
    MissionTask,
    SensorKind,
)
from swarm_core.missions import VERIFY

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.service import Orchestrator
from sim.swarm_sim.world import World


@dataclass
class StaticAllocationOrchestrator(Orchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)
    awarded_agent_ids: list[str] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)

    async def _award_and_run(self, mission: MissionTask, agent_id: str, score: float) -> None:
        self.awarded_agent_ids.append(agent_id)


def _fleet_member(
    agent_id: str,
    *,
    geo: Geo,
    capabilities: list[str],
) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="executor",
        fsm_state=AgentState.DOCKED,
        battery_pct=90.0,
        geo=geo,
        capabilities=capabilities,
    )


@pytest.mark.asyncio
async def test_capability_eligibility_precedes_proximity_ranking() -> None:
    objective_geo = Geo(lat=45.0, lon=9.0)
    visual = Capability.VISUAL_OBSERVATION.value
    thermal = Capability.THERMAL_OBSERVATION.value
    near_incapable = _fleet_member(
        "agent-near",
        geo=Geo(lat=45.0018, lon=9.0),
        capabilities=[visual],
    )
    far_capable = _fleet_member(
        "agent-far",
        geo=Geo(lat=45.018, lon=9.0),
        capabilities=[thermal],
    )
    objective = VERIFY(
        geo=objective_geo,
        required_capabilities=[thermal],
    )

    bus = InMemoryBus()
    await bus.connect()
    orchestrator = StaticAllocationOrchestrator(
        bus=bus,
        registry=AdapterRegistry(),
        fleet_fixture=[near_incapable, far_capable],
    )

    async def next_allocation() -> AllocationDecision:
        async for _, payload in bus.subscribe("swarm:allocations"):
            return AllocationDecision.model_validate_json(payload)
        raise AssertionError("allocation stream ended")

    allocation_task = asyncio.create_task(next_allocation())
    await asyncio.sleep(0)
    await orchestrator._auction_and_dispatch(objective)
    decision = await asyncio.wait_for(allocation_task, timeout=1.0)
    await bus.close()

    near_distance = haversine_m(near_incapable.geo, objective_geo)
    far_distance = haversine_m(far_capable.geo, objective_geo)
    assert 150.0 < near_distance < 250.0
    assert 1_800.0 < far_distance < 2_200.0

    assert decision.required_capabilities == [thermal]
    assert [unit.agent_id for unit in decision.eligible_units] == ["agent-far"]
    mismatch = next(unit for unit in decision.excluded_units if unit.agent_id == "agent-near")
    assert mismatch.reason is AllocationExclusionReason.CAPABILITY_MISMATCH
    assert "score" not in mismatch.model_dump()
    assert "score_breakdown" not in mismatch.model_dump()
    assert decision.eligible_units[0].score_breakdown.distance_m == pytest.approx(far_distance)
    assert decision.winner_agent_id == "agent-far"
    assert orchestrator.awarded_agent_ids == ["agent-far"]


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

    async def next_allocation() -> dict[str, Any]:
        async for _, payload in bus.subscribe("swarm:allocations"):
            return cast(dict[str, Any], json.loads(payload))
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
