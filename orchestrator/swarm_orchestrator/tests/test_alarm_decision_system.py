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
        self.executed: list[MissionTask] = []
        self.release = asyncio.Event()

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


def _state(
    agent_id: str,
    state: AgentState,
    *,
    lat: float = 45.0,
    lon: float = 9.0,
) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=90.0,
        geo=Geo(lat=lat, lon=lon),
    )


def _coverage() -> MissionTask:
    return COVER(
        area=[
            Geo(lat=45.0000, lon=9.0000),
            Geo(lat=45.0005, lon=9.0000),
            Geo(lat=45.0005, lon=9.0005),
            Geo(lat=45.0000, lon=9.0005),
            Geo(lat=45.0002, lon=9.0001),
            Geo(lat=45.0004, lon=9.0003),
        ],
        fleet_size=4,
        minimum_capacity=2,
        preemptible=True,
        priority=10,
    )


async def _stop(
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
async def test_alarm_response_refuses_to_start_below_its_declared_minimum() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapter = HoldingAdapter("agent-1")
    registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAlarmOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[_state("agent-1", AgentState.DOCKED)],
        alarm_policy=AlarmResponsePolicy(max_team_size=3),
        reinforcement_review_period_s=0.02,
    )
    run_task = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)

    alarm = Anomaly(
        id="external-alarm-minimum",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0001, lon=9.0001),
        confidence=0.97,
    )
    await bus.publish("swarm:anomalies", alarm.model_dump_json())

    async def _wait_for_refusal() -> None:
        while not any(
            group.anomaly_id == alarm.id
            for group in orchestrator.execution_groups.values()
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_for_refusal(), timeout=1.0)
    response = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.anomaly_id == alarm.id
    )

    assert response.requested_members == 3
    assert response.members == []
    assert response.state is ExecutionGroupState.FAILED
    assert response.failure_reason == "BELOW_MINIMUM_CAPACITY"
    assert adapter.executed == []

    await _stop(orchestrator, run_task, bus)


@pytest.mark.asyncio
async def test_external_alarm_drives_diversion_rebalance_and_reinforcement() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = {f"agent-{idx}": HoldingAdapter(f"agent-{idx}") for idx in range(1, 6)}
    for adapter in adapters.values():
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAlarmOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[
            _state("agent-1", AgentState.DOCKED),
            _state("agent-2", AgentState.DOCKED),
            _state("agent-3", AgentState.DOCKED),
            _state("agent-4", AgentState.DOCKED),
            _state("agent-5", AgentState.OFFLINE),
        ],
        alarm_policy=AlarmResponsePolicy(max_team_size=3),
        reinforcement_review_period_s=0.02,
        max_reinforcements_per_objective=1,
    )

    # External mission demand: this area requires continuous coverage. SwarmOS
    # chooses all four initial owners; the test never names which one should be
    # diverted later.
    cover = _coverage()
    donor = await orchestrator.dispatch_execution_group(cover)
    assert len(donor.members) == 4
    original_cover_agents = {member.agent_id for member in donor.members}

    # World-state change only: those owners are now airborne and one spare is
    # unavailable. No response executor, group id or reinforcement is supplied.
    orchestrator.fleet_fixture = [
        _state("agent-1", AgentState.EN_ROUTE),
        _state("agent-2", AgentState.EN_ROUTE),
        _state("agent-3", AgentState.EN_ROUTE),
        _state("agent-4", AgentState.EN_ROUTE),
        _state("agent-5", AgentState.OFFLINE),
    ]
    run_task = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)

    alarm = Anomaly(
        id="external-alarm-response",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0001, lon=9.0001),
        confidence=0.97,
    )
    alarm_payload = alarm.model_dump_json()
    assert "agent-" not in alarm_payload
    await bus.publish("swarm:anomalies", alarm_payload)

    async def _wait_for_response() -> None:
        while not any(
            group.anomaly_id == alarm.id
            for group in orchestrator.execution_groups.values()
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_for_response(), timeout=1.0)
    response = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.anomaly_id == alarm.id
    )
    await asyncio.sleep(0.08)

    # Alarm policy asks for three with minimum two. The coverage floor permits
    # exactly two diversions, so the response is admitted at 2/3 strength and
    # the donor is recomputed at its protected 2/4 floor.
    assert response.requested_members == 3
    assert len(response.members) == 2
    assert {member.agent_id for member in response.members} <= original_cover_agents
    assert all(
        member.diverted_from_objective_id == cover.id for member in response.members
    )

    donor_now = orchestrator.execution_groups[donor.id]
    diverted = [
        member
        for member in donor_now.members
        if member.state is ExecutionGroupMemberState.DIVERTED
    ]
    survivors = [
        member
        for member in donor_now.members
        if member.state
        not in {
            ExecutionGroupMemberState.DIVERTED,
            ExecutionGroupMemberState.FAILED,
            ExecutionGroupMemberState.REPLACED,
        }
    ]
    assert len(diverted) == 2
    assert len(survivors) == 2
    assert donor_now.state is ExecutionGroupState.DEGRADED
    assert all(
        orchestrator._agent_missions[member.agent_id].params["slice_count"] == 2
        for member in survivors
    )

    # Another external world-state change: capacity becomes available. The
    # periodic reconciliation loop, not this test, decides that the higher-
    # priority response gets it before the degraded sweep.
    orchestrator.fleet_fixture = [
        _state("agent-1", AgentState.EN_ROUTE),
        _state("agent-2", AgentState.EN_ROUTE),
        _state("agent-3", AgentState.EN_ROUTE),
        _state("agent-4", AgentState.EN_ROUTE),
        _state("agent-5", AgentState.DOCKED),
    ]

    async def _wait_for_reinforcement() -> None:
        while not any(
            group.reinforces_group_id == response.id
            for group in orchestrator.execution_groups.values()
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_for_reinforcement(), timeout=1.0)
    reinforcement = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.reinforces_group_id == response.id
    )

    assert reinforcement.objective_mission_id == response.objective_mission_id
    assert reinforcement.anomaly_id == alarm.id
    assert len(reinforcement.members) == 1
    assert reinforcement.members[0].agent_id == "agent-5"

    await _stop(orchestrator, run_task, bus)
