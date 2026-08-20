from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.execution_groups import ExecutionGroupMemberState, ExecutionGroupState
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    FleetState,
    Geo,
    MissionProgress,
    MissionTask,
)
from swarm_core.missions import COVER

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.alarm_driven import (
    AlarmDrivenExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus import InMemoryBus


class HoldingAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.release = asyncio.Event()

    async def execute_mission(
        self, mission: MissionTask
    ) -> AsyncIterator[MissionProgress]:
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
class StaticScaleOrchestrator(AlarmDrivenExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _state(agent_id: str, state: AgentState, index: int) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=95.0 - index * 0.1,
        geo=Geo(lat=45.0 + index * 0.000002, lon=9.0),
    )


def _sweep() -> MissionTask:
    area = [
        Geo(lat=45.0000, lon=9.0000),
        Geo(lat=45.0010, lon=9.0000),
        Geo(lat=45.0010, lon=9.0010),
        Geo(lat=45.0000, lon=9.0010),
    ]
    return COVER(
        area=area,
        fleet_size=30,
        minimum_capacity=27,
        preemptible=True,
        priority=10,
    )


async def _cleanup(
    orchestrator: AlarmDrivenExecutionGroupOrchestrator,
    run_task: asyncio.Task[None],
    bus: InMemoryBus,
) -> None:
    run_task.cancel()
    await asyncio.gather(run_task, return_exceptions=True)
    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await bus.close()


@pytest.mark.asyncio
async def test_high_priority_alarm_reduces_30_sweep_to_floor_27_then_reinforces() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    agent_ids = [f"agent-{idx:02d}" for idx in range(1, 32)]
    for agent_id in agent_ids:
        registry.register(HoldingAdapter(agent_id))  # type: ignore[arg-type]

    orchestrator = StaticScaleOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            *[
                _state(agent_id, AgentState.DOCKED, idx)
                for idx, agent_id in enumerate(agent_ids[:30], start=1)
            ],
            _state(agent_ids[30], AgentState.OFFLINE, 31),
        ],
        alarm_policy=AlarmResponsePolicy(max_team_size=4),
        reinforcement_review_period_s=0.02,
        max_reinforcements_per_objective=2,
    )

    sweep = _sweep()
    sweep_group = await orchestrator.dispatch_execution_group(sweep)
    assert len(sweep_group.members) == 30

    # External world truth only: the sweep owners are airborne; the spare is
    # unavailable. Which three sweep members are borrowed is deliberately not
    # specified here.
    orchestrator.fleet_fixture = [
        *[
            _state(agent_id, AgentState.EN_ROUTE, idx)
            for idx, agent_id in enumerate(agent_ids[:30], start=1)
        ],
        _state(agent_ids[30], AgentState.OFFLINE, 31),
    ]
    run_task = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)

    alarm = Anomaly(
        id="scale-alarm",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0005, lon=9.0005),
        confidence=0.99,
    )
    payload = alarm.model_dump_json()
    assert "agent-" not in payload
    await bus.publish("swarm:anomalies", payload)

    async def _wait_for_response_and_replan() -> None:
        while True:
            responses = [
                group
                for group in orchestrator.execution_groups.values()
                if group.anomaly_id == alarm.id
                and group.reinforces_group_id is None
            ]
            if not responses:
                await asyncio.sleep(0.005)
                continue
            donor = orchestrator.execution_groups[sweep_group.id]
            diverted = [
                member
                for member in donor.members
                if member.state is ExecutionGroupMemberState.DIVERTED
            ]
            survivors = [
                member
                for member in donor.members
                if member.state
                not in {
                    ExecutionGroupMemberState.DIVERTED,
                    ExecutionGroupMemberState.FAILED,
                    ExecutionGroupMemberState.REPLACED,
                    ExecutionGroupMemberState.COMPLETED,
                }
            ]
            replanned = len(survivors) == 27 and all(
                (mission := orchestrator._agent_missions.get(member.agent_id))
                is not None
                and mission.params.get("slice_count") == 27
                and mission.params.get("recomputed_from_capacity") == 27
                for member in survivors
            )
            if len(diverted) == 3 and replanned:
                return
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_for_response_and_replan(), timeout=2.0)
    response = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.anomaly_id == alarm.id
        and group.reinforces_group_id is None
    )
    donor = orchestrator.execution_groups[sweep_group.id]

    # This is the product invariant behind the old scripted 30 -> 27 beat:
    # policy asks for four/minimum three, donor policy protects 27, therefore
    # exactly three are diverted and the response begins at 3/4 strength.
    assert response.requested_members == 4
    assert len(response.members) == 3
    assert donor.state is ExecutionGroupState.DEGRADED
    assert sum(
        member.state is ExecutionGroupMemberState.DIVERTED
        for member in donor.members
    ) == 3
    assert sum(
        member.state
        not in {
            ExecutionGroupMemberState.DIVERTED,
            ExecutionGroupMemberState.FAILED,
            ExecutionGroupMemberState.REPLACED,
            ExecutionGroupMemberState.COMPLETED,
        }
        for member in donor.members
    ) == 27

    # One more external fact: previously unavailable capacity returns. The test
    # does not call reinforcement or name a receiving role/group.
    orchestrator.fleet_fixture = [
        *[
            _state(agent_id, AgentState.EN_ROUTE, idx)
            for idx, agent_id in enumerate(agent_ids[:30], start=1)
        ],
        _state(agent_ids[30], AgentState.DOCKED, 31),
    ]

    async def _wait_for_reinforcement() -> None:
        while not any(
            group.reinforces_group_id == response.id
            for group in orchestrator.execution_groups.values()
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_for_reinforcement(), timeout=2.0)
    reinforcement = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.reinforces_group_id == response.id
    )

    assert reinforcement.objective_mission_id == response.objective_mission_id
    assert reinforcement.anomaly_id == alarm.id
    assert len(reinforcement.members) == 1
    assert len(response.members) + len(reinforcement.members) == 4

    await _cleanup(orchestrator, run_task, bus)
