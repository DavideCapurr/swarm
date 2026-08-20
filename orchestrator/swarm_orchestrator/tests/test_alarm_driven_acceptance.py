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
from orchestrator.swarm_orchestrator.bus import InMemoryBus


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
class StaticAlarmOrchestrator(AlarmDrivenExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _member(agent_id: str, state: AgentState) -> FleetState:
    # Different positions and batteries make selection deterministic without
    # scenario code naming the winner. The capacity planner sees these values.
    index = int(agent_id.rsplit("-", 1)[1])
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=96.0 - index,
        geo=Geo(lat=45.0 + index * 0.00005, lon=9.0 + index * 0.00003),
    )


def _sweep() -> MissionTask:
    return COVER(
        area=[
            Geo(lat=45.0000, lon=9.0000),
            Geo(lat=45.0008, lon=9.0000),
            Geo(lat=45.0008, lon=9.0008),
            Geo(lat=45.0000, lon=9.0008),
            Geo(lat=45.0004, lon=9.0002),
            Geo(lat=45.0004, lon=9.0006),
            Geo(lat=45.0002, lon=9.0004),
            Geo(lat=45.0006, lon=9.0004),
        ],
        fleet_size=4,
        minimum_capacity=2,
        preemptible=True,
        priority=10,
    )


async def _wait_for_alarm_group(
    orchestrator: StaticAlarmOrchestrator,
    alarm_id: str,
) -> str:
    async def _wait() -> str:
        while True:
            for group_id, group in orchestrator.execution_groups.items():
                if group.anomaly_id == alarm_id:
                    return group_id
            await asyncio.sleep(0.005)

    return await asyncio.wait_for(_wait(), timeout=1.0)


async def _wait_for_reinforcement_group(
    orchestrator: StaticAlarmOrchestrator,
    origin_group_id: str,
) -> str:
    async def _wait() -> str:
        while True:
            for group_id, group in orchestrator.execution_groups.items():
                if group.reinforces_group_id == origin_group_id:
                    return group_id
            await asyncio.sleep(0.005)

    return await asyncio.wait_for(_wait(), timeout=1.0)


async def _shutdown(
    orchestrator: StaticAlarmOrchestrator,
    *runtime_tasks: asyncio.Task[None],
) -> None:
    for task in runtime_tasks:
        task.cancel()
    if runtime_tasks:
        await asyncio.gather(*runtime_tasks, return_exceptions=True)

    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_alarm_is_the_only_response_trigger_and_swarmos_builds_the_chain() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter(f"agent-{idx}") for idx in range(1, 6)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAlarmOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            *[_member(f"agent-{idx}", AgentState.DOCKED) for idx in range(1, 5)],
            _member("agent-5", AgentState.OFFLINE),
        ],
        max_reinforcements_per_objective=1,
        reinforcement_review_period_s=0.01,
    )

    # Initial world state only: four executors are assigned to a continuous
    # coverage objective. The scenario does not pre-name response capacity.
    sweep = await orchestrator.dispatch_execution_group(_sweep())
    assert len(sweep.members) == 4

    orchestrator.fleet_fixture = [
        *[_member(f"agent-{idx}", AgentState.EN_ROUTE) for idx in range(1, 5)],
        _member("agent-5", AgentState.OFFLINE),
    ]

    # Start the actual orchestrator runtime. From here on, the test changes only
    # external world truth and waits for SwarmOS outputs; it never calls a
    # response/reinforcement decision method directly.
    runtime = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)
    alarm = Anomaly(
        id="alarm-input-only",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.00045, lon=9.00045),
        confidence=0.97,
    )
    # This is the only response-side scenario input. No executor, role, group or
    # reinforcement identifier exists in the event.
    alarm_payload = alarm.model_dump_json()
    assert "agent-" not in alarm_payload
    assert "mav-" not in alarm_payload
    await bus.publish("swarm:anomalies", alarm_payload)

    response_id = await _wait_for_alarm_group(orchestrator, alarm.id)
    await asyncio.sleep(0.08)
    response = orchestrator.execution_groups[response_id]
    sweep_now = orchestrator.execution_groups[sweep.id]

    # Default high-confidence demand is three members. The sweep floor permits
    # exactly two transfers, so the response begins genuinely under strength.
    assert response.requested_members == 3
    assert len(response.members) == 2
    assert response.objective_mission_id != alarm.id
    assert response.anomaly_id == alarm.id
    assert all(
        member.diverted_from_objective_id == sweep.objective_mission_id
        for member in response.members
    )
    assert sum(
        member.state is ExecutionGroupMemberState.DIVERTED
        for member in sweep_now.members
    ) == 2

    # The donor plan is not left with two holes: its surviving child missions
    # have been recomputed against the remaining strength.
    survivors = [
        member
        for member in sweep_now.members
        if member.state is not ExecutionGroupMemberState.DIVERTED
    ]
    assert len(survivors) == 2
    for member in survivors:
        mission = orchestrator._agent_missions[member.agent_id]
        assert mission.params["slice_count"] == 2
        assert mission.params["recomputed_from_capacity"] == 2

    # External world development only: previously unavailable capacity returns.
    # The scenario still does not say "reinforce", call a review function, or
    # name a swarm member. The periodic SwarmOS reconciliation loop must notice.
    orchestrator.fleet_fixture = [
        *[_member(f"agent-{idx}", AgentState.EN_ROUTE) for idx in range(1, 5)],
        _member("agent-5", AgentState.DOCKED),
    ]
    reinforcement_id = await _wait_for_reinforcement_group(orchestrator, response.id)
    reinforcement = orchestrator.execution_groups[reinforcement_id]

    assert reinforcement.reinforces_group_id == response.id
    assert reinforcement.objective_mission_id == response.objective_mission_id
    assert reinforcement.anomaly_id == alarm.id
    assert [member.agent_id for member in reinforcement.members] == ["agent-5"]

    await _shutdown(orchestrator, runtime)
    await bus.close()


@pytest.mark.asyncio
async def test_same_alarm_with_idle_capacity_does_not_degrade_the_sweep() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter(f"agent-{idx}") for idx in range(1, 8)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAlarmOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            *[_member(f"agent-{idx}", AgentState.DOCKED) for idx in range(1, 5)],
            *[_member(f"agent-{idx}", AgentState.OFFLINE) for idx in range(5, 8)],
        ],
    )
    sweep = await orchestrator.dispatch_execution_group(_sweep())

    # Same four sweep members are committed, but this counterfactual has three
    # genuinely idle executors. SwarmOS must consume idle capacity first.
    orchestrator.fleet_fixture = [
        *[_member(f"agent-{idx}", AgentState.EN_ROUTE) for idx in range(1, 5)],
        *[_member(f"agent-{idx}", AgentState.DOCKED) for idx in range(5, 8)],
    ]
    runtime = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)
    alarm = Anomaly(
        id="alarm-idle-counterfactual",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.00045, lon=9.00045),
        confidence=0.97,
    )
    await bus.publish("swarm:anomalies", alarm.model_dump_json())

    response_id = await _wait_for_alarm_group(orchestrator, alarm.id)
    await asyncio.sleep(0.05)
    response = orchestrator.execution_groups[response_id]
    sweep_now = orchestrator.execution_groups[sweep.id]

    assert len(response.members) == 3
    assert {member.agent_id for member in response.members}.issubset(
        {"agent-5", "agent-6", "agent-7"}
    )
    assert all(member.diverted_from_mission_id is None for member in response.members)
    assert all(
        member.state is not ExecutionGroupMemberState.DIVERTED
        for member in sweep_now.members
    )

    await _shutdown(orchestrator, runtime)
    await bus.close()


@pytest.mark.asyncio
async def test_high_confidence_alarm_below_minimum_capacity_dispatches_nobody() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter(f"agent-{idx}") for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    # Confidence 0.97 asks the default alarm policy for 3 members with a hard
    # minimum of 2. Only one executor is available, so SwarmOS must refuse the
    # objective rather than quietly launch a 1/3 group.
    orchestrator = StaticAlarmOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            _member("agent-1", AgentState.DOCKED),
            _member("agent-2", AgentState.OFFLINE),
            _member("agent-3", AgentState.OFFLINE),
        ],
    )
    runtime = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)
    alarm = Anomaly(
        id="alarm-below-minimum",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0, lon=9.0),
        confidence=0.97,
    )
    await bus.publish("swarm:anomalies", alarm.model_dump_json())

    group_id = await _wait_for_alarm_group(orchestrator, alarm.id)
    group = orchestrator.execution_groups[group_id]

    assert group.requested_members == 3
    assert group.state is ExecutionGroupState.FAILED
    assert group.failure_reason == "BELOW_MINIMUM_CAPACITY"
    assert group.members == []
    assert orchestrator._busy == set()
    assert orchestrator._agent_missions == {}
    assert all(adapter.executed == [] for adapter in adapters)

    await _shutdown(orchestrator, runtime)
    await bus.close()
