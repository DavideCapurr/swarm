from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.execution_groups import ExecutionGroupMemberState
from swarm_core.messages import AgentState, FleetState, Geo, MissionProgress, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY, COVER

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.adaptive_execution_groups import (
    AdaptiveExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.bus import InMemoryBus


class FailureAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(self, agent_id: str, *, fail_first: bool = False) -> None:
        self.agent_id = agent_id
        self.fail_first = fail_first
        self.failed = False
        self.hold = asyncio.Event()
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
        await asyncio.sleep(0)
        if self.fail_first and not self.failed:
            self.failed = True
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=20.0,
                error="injected response failure",
            )
            return
        await self.hold.wait()
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


@dataclass
class StaticAdaptive(AdaptiveExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _state(agent_id: str, state: AgentState) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=90.0,
        geo=Geo(lat=45.0, lon=9.0),
    )


async def _cleanup(orchestrator: AdaptiveExecutionGroupOrchestrator) -> None:
    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_response_role_is_replaced_by_policy_selected_donor_capacity() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = {
        f"agent-{idx}": FailureAdapter(
            f"agent-{idx}", fail_first=(idx == 4)
        )
        for idx in range(1, 6)
    }
    for adapter in adapters.values():
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAdaptive(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            _state("agent-1", AgentState.DOCKED),
            _state("agent-2", AgentState.DOCKED),
            _state("agent-3", AgentState.DOCKED),
            _state("agent-4", AgentState.OFFLINE),
            _state("agent-5", AgentState.OFFLINE),
        ],
    )
    progress = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    cover = COVER(
        area=[
            Geo(lat=45.0000, lon=9.0000),
            Geo(lat=45.0004, lon=9.0000),
            Geo(lat=45.0004, lon=9.0004),
            Geo(lat=45.0000, lon=9.0004),
        ],
        fleet_size=3,
        minimum_capacity=1,
        preemptible=True,
        priority=10,
    )
    donor = await orchestrator.dispatch_execution_group(cover)

    orchestrator.fleet_fixture = [
        _state("agent-1", AgentState.EN_ROUTE),
        _state("agent-2", AgentState.EN_ROUTE),
        _state("agent-3", AgentState.EN_ROUTE),
        _state("agent-4", AgentState.DOCKED),
        _state("agent-5", AgentState.DOCKED),
    ]
    response = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0001, lon=9.0001),
        team_size=2,
        minimum_capacity=1,
        hover_s=60.0,
        priority=90,
    )
    group = await orchestrator.dispatch_execution_group(response)

    async def _wait_replacement() -> None:
        while not any(
            member.replaces_agent_id == "agent-4"
            for member in orchestrator.execution_groups[group.id].members
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_replacement(), timeout=1.0)
    await asyncio.sleep(0.08)

    response_now = orchestrator.execution_groups[group.id]
    replacement = next(
        member
        for member in response_now.members
        if member.replaces_agent_id == "agent-4"
    )
    failed = next(
        member for member in response_now.members if member.agent_id == "agent-4"
    )
    donor_now = orchestrator.execution_groups[donor.id]

    assert failed.state is ExecutionGroupMemberState.REPLACED
    assert replacement.role == failed.role
    assert replacement.agent_id in {"agent-1", "agent-2", "agent-3"}
    assert sum(
        member.state is ExecutionGroupMemberState.DIVERTED
        for member in donor_now.members
    ) == 1
    assert len(
        [
            member
            for member in donor_now.members
            if member.state
            not in {
                ExecutionGroupMemberState.DIVERTED,
                ExecutionGroupMemberState.REPLACED,
                ExecutionGroupMemberState.FAILED,
            }
        ]
    ) == 2

    progress.cancel()
    await asyncio.gather(progress, return_exceptions=True)
    await _cleanup(orchestrator)
    await bus.close()
