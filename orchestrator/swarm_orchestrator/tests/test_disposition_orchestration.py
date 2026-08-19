from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.disposition import DispositionDecision
from swarm_core.messages import AgentState, FleetState, Geo, MissionProgress, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.disposition_execution_groups import (
    DISPOSITION_TOPIC,
    DispositionExecutionGroupOrchestrator,
)


class HoldingAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.release = asyncio.Event()
        self.executed: list[MissionTask] = []

    async def execute_mission(
        self, mission: MissionTask
    ) -> AsyncIterator[MissionProgress]:
        self.executed.append(mission)
        yield MissionProgress(
            mission_id=mission.id,
            phase="EN_ROUTE",
            progress_pct=20.0,
        )
        await self.release.wait()
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


@dataclass
class StaticDispositionOrchestrator(DispositionExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _state(agent_id: str, state: AgentState) -> FleetState:
    index = int(agent_id.rsplit("-", 1)[1])
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=95.0 - index,
        geo=Geo(lat=45.0 + index * 0.00005, lon=9.0),
    )


async def _next_disposition(bus: InMemoryBus) -> DispositionDecision:
    async for _topic, payload in bus.subscribe(DISPOSITION_TOPIC):
        return DispositionDecision.model_validate_json(payload)
    raise AssertionError("disposition subscription ended")


async def _cleanup(orchestrator: DispositionExecutionGroupOrchestrator) -> None:
    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_initial_composition_publishes_and_executes_swarmos_disposition() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter("agent-1"), HoldingAdapter("agent-2")]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticDispositionOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            _state("agent-1", AgentState.DOCKED),
            _state("agent-2", AgentState.DOCKED),
        ],
        execute_disposition_retask=True,
    )
    listener = asyncio.create_task(_next_disposition(bus))
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=2,
        minimum_capacity=2,
        hover_s=60.0,
        priority=90,
    )
    group = await orchestrator.dispatch_execution_group(objective)
    decision = await asyncio.wait_for(listener, timeout=1.0)
    await asyncio.sleep(0)

    assert decision.objective_mission_id == objective.id
    assert decision.revision == 1
    assert decision.reason == "COMPOSITION"
    assert decision.active_members == 2
    assert decision.radius_m == 22.0
    assert {assignment.agent_id for assignment in decision.assignments} == {
        "agent-1",
        "agent-2",
    }
    assert all(
        assignment.geo.lat != objective.params["geo"]["lat"]
        or assignment.geo.lon != objective.params["geo"]["lon"]
        for assignment in decision.assignments
    )

    current = orchestrator.execution_groups[group.id]
    assert {member.mission_id for member in current.members} == {
        assignment.mission_id for assignment in decision.assignments
    }
    for adapter in adapters:
        assert any(
            mission.params.get("disposition_revision") == 1
            for mission in adapter.executed
        )

    await _cleanup(orchestrator)
    await bus.close()


@pytest.mark.asyncio
async def test_reinforcement_automatically_widens_and_retasks_existing_members() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = {
        f"agent-{idx}": HoldingAdapter(f"agent-{idx}") for idx in range(1, 4)
    }
    for adapter in adapters.values():
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticDispositionOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            _state("agent-1", AgentState.DOCKED),
            _state("agent-2", AgentState.DOCKED),
            _state("agent-3", AgentState.OFFLINE),
        ],
        execute_disposition_retask=True,
        max_reinforcements_per_objective=1,
    )

    first_listener = asyncio.create_task(_next_disposition(bus))
    await asyncio.sleep(0)
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
        minimum_capacity=2,
        hover_s=60.0,
        priority=90,
    )
    origin = await orchestrator.dispatch_execution_group(objective)
    first = await asyncio.wait_for(first_listener, timeout=1.0)
    assert len(origin.members) == 2
    assert first.active_members == 2
    assert first.radius_m == 22.0

    # World-state change only: the third executor becomes available. The normal
    # reinforcement policy decides to add it; disposition reacts to the new
    # membership and widens without a scenario-specified formation command.
    orchestrator.fleet_fixture = [
        _state("agent-1", AgentState.EN_ROUTE),
        _state("agent-2", AgentState.EN_ROUTE),
        _state("agent-3", AgentState.DOCKED),
    ]
    second_listener = asyncio.create_task(_next_disposition(bus))
    await asyncio.sleep(0)
    reinforcements = await orchestrator.review_reinforcements()
    second = await asyncio.wait_for(second_listener, timeout=1.0)
    await asyncio.sleep(0)

    assert len(reinforcements) == 1
    assert reinforcements[0].reinforces_group_id == origin.id
    assert second.revision == 2
    assert second.reason == "REINFORCEMENT"
    assert second.active_members == 3
    assert second.radius_m == 30.0
    assert {assignment.agent_id for assignment in second.assignments} == {
        "agent-1",
        "agent-2",
        "agent-3",
    }

    # Existing members were not merely drawn farther apart: their executable
    # child missions were superseded by revision-2 targets.
    for agent_id in ("agent-1", "agent-2"):
        assert any(
            mission.params.get("disposition_revision") == 2
            for mission in adapters[agent_id].executed
        )

    await _cleanup(orchestrator)
    await bus.close()
