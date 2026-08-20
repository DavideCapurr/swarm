from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.capabilities import Capability
from swarm_core.execution_groups import ExecutionGroupState
from swarm_core.messages import AgentState, FleetState, Geo, MissionProgress, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.execution_groups import ExecutionGroupOrchestrator


class FakeAdapter:
    vendor = "fake"
    model = "executor"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.executed: list[MissionTask] = []

    async def execute_mission(
        self, mission: MissionTask
    ) -> AsyncIterator[MissionProgress]:
        self.executed.append(mission)
        yield MissionProgress(
            mission_id=mission.id,
            phase="EN_ROUTE",
            progress_pct=25.0,
        )
        await asyncio.sleep(0)
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


@dataclass
class StaticExecutionGroupOrchestrator(ExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _state(
    agent_id: str,
    *,
    lat: float,
    capabilities: list[str],
    battery: float = 90.0,
) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="executor",
        fsm_state=AgentState.DOCKED,
        battery_pct=battery,
        geo=Geo(lat=lat, lon=9.0),
        capabilities=capabilities,
    )


@pytest.mark.asyncio
async def test_execution_group_composes_only_capable_physical_capacity() -> None:
    """A nearer incapable executor must never enter a capability-bound group."""

    thermal = Capability.THERMAL_OBSERVATION.value
    fleet = [
        _state("near-visual", lat=45.0001, capabilities=[Capability.VISUAL_OBSERVATION.value]),
        _state("thermal-1", lat=45.0050, capabilities=[thermal], battery=92.0),
        _state("thermal-2", lat=45.0080, capabilities=[thermal], battery=88.0),
    ]

    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [FakeAdapter(state.agent_id) for state in fleet]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=fleet,
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0, lon=9.0),
        team_size=2,
        hover_s=0.0,
        required_capabilities=[thermal],
    )
    group = await orchestrator.dispatch_execution_group(objective)

    async def wait_terminal() -> None:
        while orchestrator.execution_groups[group.id].state not in {
            ExecutionGroupState.COMPLETED,
            ExecutionGroupState.FAILED,
        }:
            await asyncio.sleep(0.005)

    await asyncio.wait_for(wait_terminal(), timeout=2.0)
    terminal = orchestrator.execution_groups[group.id]

    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await bus.close()

    assert terminal.state is ExecutionGroupState.COMPLETED
    assert {member.agent_id for member in terminal.members} == {
        "thermal-1",
        "thermal-2",
    }
    assert all(
        mission.params["required_capabilities"] == [thermal]
        for adapter in adapters
        for mission in adapter.executed
    )
    assert next(a for a in adapters if a.agent_id == "near-visual").executed == []


def test_group_candidate_ranking_still_applies_after_capability_filter() -> None:
    """Capability gating is eligibility, not a replacement for existing scoring."""

    thermal = Capability.THERMAL_OBSERVATION.value
    fleet = [
        _state("far-high", lat=45.03, capabilities=[thermal], battery=99.0),
        _state("near-mid", lat=45.001, capabilities=[thermal], battery=80.0),
        _state("nearest-wrong", lat=45.0001, capabilities=[Capability.VISUAL_OBSERVATION.value]),
    ]
    orchestrator = StaticExecutionGroupOrchestrator(
        bus=InMemoryBus(),
        registry=AdapterRegistry(),
        fleet_fixture=fleet,
    )
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0, lon=9.0),
        team_size=2,
        required_capabilities=[thermal],
    )
    child = orchestrator._cooperative_verify_plans(objective)[0].mission

    choice = orchestrator._select_group_candidate(child, excluded_agent_ids=set())

    assert choice is not None
    assert choice[0] == "near-mid"
