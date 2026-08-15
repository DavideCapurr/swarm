from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.messages import AgentState, FleetState, Geo, MissionProgress, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY, MissionKind

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.execution_groups import ExecutionGroupOrchestrator


class FakeAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(
        self,
        agent_id: str,
        *,
        fail_first: bool = False,
        raise_first: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self.fail_first = fail_first
        self.raise_first = raise_first
        self.failed_once = False
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
        if self.raise_first and not self.failed_once:
            self.failed_once = True
            raise RuntimeError("injected executor crash")
        if self.fail_first and not self.failed_once:
            self.failed_once = True
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=25.0,
                error="injected failure",
            )
            return
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


def _fleet(*battery: float) -> list[FleetState]:
    return [
        FleetState(
            agent_id=f"agent-{idx + 1}",
            vendor="fake",
            model="thin-executor",
            fsm_state=AgentState.DOCKED,
            battery_pct=value,
            geo=Geo(lat=45.0, lon=9.0),
        )
        for idx, value in enumerate(battery)
    ]


async def _wait_group_terminal(
    orchestrator: ExecutionGroupOrchestrator,
    group_id: str,
    *,
    timeout_s: float = 2.0,
) -> ExecutionGroup:
    async def _wait() -> ExecutionGroup:
        while True:
            group = orchestrator.execution_groups[group_id]
            if group.state in {
                ExecutionGroupState.COMPLETED,
                ExecutionGroupState.FAILED,
            }:
                return group
            await asyncio.sleep(0.005)

    return await asyncio.wait_for(_wait(), timeout=timeout_s)


@pytest.mark.asyncio
async def test_cooperative_verify_assigns_unique_roles_and_never_dispatches_parent() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [FakeAdapter(f"agent-{idx}") for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(95.0, 85.0, 75.0),
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
        hover_s=0.0,
    )
    group = await orchestrator.dispatch_execution_group(objective)
    terminal = await _wait_group_terminal(orchestrator, group.id)

    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await bus.close()

    assert terminal.state is ExecutionGroupState.COMPLETED
    assert len(terminal.members) == 3
    assert len({member.agent_id for member in terminal.members}) == 3
    assert {member.role for member in terminal.members} == {
        "PRIMARY_OBSERVER",
        "SECONDARY_OBSERVER",
        "OVERWATCH",
    }
    assert all(
        member.state is ExecutionGroupMemberState.COMPLETED
        for member in terminal.members
    )
    assert all(
        mission.kind == MissionKind.VERIFY.value
        for adapter in adapters
        for mission in adapter.executed
    )
    assert all(
        mission.params["parent_objective_id"] == objective.id
        for adapter in adapters
        for mission in adapter.executed
    )
    assert all(
        mission.kind != objective.kind
        for adapter in adapters
        for mission in adapter.executed
    )


@pytest.mark.asyncio
async def test_execution_group_fails_closed_before_partial_dispatch() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [FakeAdapter("agent-1"), FakeAdapter("agent-2")]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(95.0, 85.0),
    )
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
    )

    group = await orchestrator.dispatch_execution_group(objective)
    await bus.close()

    assert group.state is ExecutionGroupState.FAILED
    assert group.failure_reason == "INSUFFICIENT_ELIGIBLE_CAPACITY"
    assert group.members == []
    assert all(adapter.executed == [] for adapter in adapters)
    assert orchestrator._busy == set()


async def _assert_failed_member_replaced(adapters: list[FakeAdapter]) -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(99.0, 90.0, 80.0, 70.0),
        max_group_replacements_per_role=1,
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
        hover_s=0.0,
    )
    group = await orchestrator.dispatch_execution_group(objective)
    terminal = await _wait_group_terminal(orchestrator, group.id)

    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await bus.close()

    assert terminal.state is ExecutionGroupState.COMPLETED
    replaced = [member for member in terminal.members if member.replaces_agent_id]
    assert len(replaced) == 1
    assert replaced[0].replaces_agent_id == "agent-1"
    assert replaced[0].agent_id == "agent-4"
    assert replaced[0].state is ExecutionGroupMemberState.COMPLETED
    original = next(
        member for member in terminal.members if member.agent_id == "agent-1"
    )
    assert original.state is ExecutionGroupMemberState.REPLACED


@pytest.mark.asyncio
async def test_failed_member_is_replaced_centrally_by_spare_agent() -> None:
    await _assert_failed_member_replaced(
        [
            FakeAdapter("agent-1", fail_first=True),
            FakeAdapter("agent-2"),
            FakeAdapter("agent-3"),
            FakeAdapter("agent-4"),
        ]
    )


@pytest.mark.asyncio
async def test_executor_exception_becomes_failed_and_triggers_replacement() -> None:
    await _assert_failed_member_replaced(
        [
            FakeAdapter("agent-1", raise_first=True),
            FakeAdapter("agent-2"),
            FakeAdapter("agent-3"),
            FakeAdapter("agent-4"),
        ]
    )
