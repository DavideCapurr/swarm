from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest
from swarm_core.execution_groups import (
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.messages import AgentState, FleetState, Geo, MissionProgress, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY, COVER, VERIFY
from swarm_core.objectives import stamp_objective_demand

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.adaptive_execution_groups import (
    AdaptiveExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.capacity import (
    CapacitySource,
    choose_capacity,
    evaluate_capacity,
)


class HoldingAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(self, agent_id: str, *, finish: bool = False) -> None:
        self.agent_id = agent_id
        self.finish = finish
        self.release = asyncio.Event()
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
        if not self.finish:
            await self.release.wait()
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


@dataclass
class StaticAdaptiveOrchestrator(AdaptiveExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)


def _member(
    agent_id: str,
    *,
    state: AgentState = AgentState.DOCKED,
    battery: float = 90.0,
    lat: float = 45.0,
    lon: float = 9.0,
) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="fake",
        model="thin-executor",
        fsm_state=state,
        battery_pct=battery,
        geo=Geo(lat=lat, lon=lon),
    )


def _cover_objective(*, minimum: int, preemptible: bool = True) -> MissionTask:
    return COVER(
        area=[
            Geo(lat=45.0000, lon=9.0000),
            Geo(lat=45.0005, lon=9.0000),
            Geo(lat=45.0005, lon=9.0005),
            Geo(lat=45.0000, lon=9.0005),
            Geo(lat=45.0002, lon=9.0002),
            Geo(lat=45.0004, lon=9.0004),
        ],
        fleet_size=3,
        minimum_capacity=minimum,
        preemptible=preemptible,
        priority=10,
    )


def _active_cover_child(
    parent: MissionTask,
    *,
    agent_id: str,
    role: str,
) -> MissionTask:
    child = MissionTask(
        kind="PATROL",
        params={
            "area": parent.params["area"],
            "execution_role": role,
        },
        priority=parent.priority,
        assigned_agent=agent_id,
    )
    stamp_objective_demand(child, parent)
    return child


def test_higher_priority_request_uses_policy_ranked_preemptible_capacity() -> None:
    cover = _cover_objective(minimum=1)
    active = {
        "agent-z": _active_cover_child(cover, agent_id="agent-z", role="SLICE_A"),
        "agent-a": _active_cover_child(cover, agent_id="agent-a", role="SLICE_B"),
    }
    request = VERIFY(
        geo=Geo(lat=45.0000, lon=9.0000),
        priority=90,
        deadline_s=None,
    )
    fleet = [
        # Lexicographically smaller, but much farther away.
        _member(
            "agent-a",
            state=AgentState.EN_ROUTE,
            lat=45.0200,
            lon=9.0200,
        ),
        _member(
            "agent-z",
            state=AgentState.EN_ROUTE,
            lat=45.0001,
            lon=9.0001,
        ),
    ]

    choice = choose_capacity(request, fleet, active_missions=active)

    assert choice is not None
    assert choice.source is CapacitySource.PREEMPTIBLE
    assert choice.agent_id == "agent-z"
    assert choice.diverted_from_objective_id == cover.id


def test_idle_capacity_is_preferred_and_counterfactuals_change_the_decision() -> None:
    cover = _cover_objective(minimum=1)
    donor = _active_cover_child(cover, agent_id="donor", role="SLICE_A")
    request = VERIFY(
        geo=Geo(lat=45.0, lon=9.0), priority=90, deadline_s=None
    )
    active = {"donor": donor}

    with_idle = evaluate_capacity(
        request,
        [
            _member("donor", state=AgentState.EN_ROUTE),
            _member("idle", state=AgentState.DOCKED),
        ],
        active_missions=active,
    )
    assert [choice.agent_id for choice in with_idle.idle] == ["idle"]
    assert [choice.agent_id for choice in with_idle.preemptible] == ["donor"]
    assert choose_capacity(
        request,
        [
            _member("donor", state=AgentState.EN_ROUTE),
            _member("idle", state=AgentState.DOCKED),
        ],
        active_missions=active,
    ).agent_id == "idle"  # type: ignore[union-attr]

    # Same world, but the idle executor is unavailable: SwarmOS changes source
    # without any aircraft id being edited into policy code.
    no_idle = choose_capacity(
        request,
        [
            _member("donor", state=AgentState.EN_ROUTE),
            _member("idle", state=AgentState.OFFLINE),
        ],
        active_missions=active,
    )
    assert no_idle is not None
    assert no_idle.agent_id == "donor"
    assert no_idle.source is CapacitySource.PREEMPTIBLE

    # Lower-priority work cannot steal the same donor.
    low_priority = VERIFY(
        geo=Geo(lat=45.0, lon=9.0), priority=5, deadline_s=None
    )
    assert (
        choose_capacity(
            low_priority,
            [_member("donor", state=AgentState.EN_ROUTE)],
            active_missions=active,
        )
        is None
    )


def test_non_preemptible_and_minimum_floor_are_hard_guards() -> None:
    request = VERIFY(
        geo=Geo(lat=45.0, lon=9.0), priority=90, deadline_s=None
    )

    fixed_cover = _cover_objective(minimum=1, preemptible=False)
    fixed_active = {
        "agent-1": _active_cover_child(
            fixed_cover, agent_id="agent-1", role="SLICE_A"
        )
    }
    assert (
        choose_capacity(
            request,
            [_member("agent-1", state=AgentState.EN_ROUTE)],
            active_missions=fixed_active,
        )
        is None
    )

    floor_cover = _cover_objective(minimum=2, preemptible=True)
    floor_active = {
        f"agent-{idx}": _active_cover_child(
            floor_cover,
            agent_id=f"agent-{idx}",
            role=f"SLICE_{idx}",
        )
        for idx in range(1, 4)
    }
    fleet = [
        _member(f"agent-{idx}", state=AgentState.EN_ROUTE)
        for idx in range(1, 4)
    ]
    first = choose_capacity(request, fleet, active_missions=floor_active)
    assert first is not None
    second = choose_capacity(
        request,
        fleet,
        active_missions=floor_active,
        excluded_agent_ids={first.agent_id},
        planned_preemptions={first.agent_id},
    )
    assert second is None


async def _cancel_orchestrator(orchestrator: AdaptiveExecutionGroupOrchestrator) -> None:
    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_multi_agent_composition_diverts_and_recomputes_the_donor_cover() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter(f"agent-{idx}") for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAdaptiveOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[_member(f"agent-{idx}") for idx in range(1, 4)],
    )
    cover = _cover_objective(minimum=1)
    donor = await orchestrator.dispatch_execution_group(cover)
    assert len(donor.members) == 3

    # The same physical executors are now airborne and committed to the sweep.
    orchestrator.fleet_fixture = [
        _member(f"agent-{idx}", state=AgentState.EN_ROUTE)
        for idx in range(1, 4)
    ]
    response = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0001, lon=9.0001),
        team_size=2,
        minimum_capacity=1,
        priority=90,
        hover_s=60.0,
    )
    response_group = await orchestrator.dispatch_execution_group(response)
    await asyncio.sleep(0.08)

    donor_now = orchestrator.execution_groups[donor.id]
    response_now = orchestrator.execution_groups[response_group.id]
    diverted = [
        member
        for member in donor_now.members
        if member.state is ExecutionGroupMemberState.DIVERTED
    ]
    active = [
        member
        for member in donor_now.members
        if member.state not in {
            ExecutionGroupMemberState.DIVERTED,
            ExecutionGroupMemberState.FAILED,
            ExecutionGroupMemberState.REPLACED,
        }
    ]

    assert len(response_now.members) == 2
    assert len(diverted) == 2
    assert len(active) == 1
    assert donor_now.state is ExecutionGroupState.DEGRADED
    assert all(
        member.diverted_from_objective_id == cover.id
        for member in response_now.members
    )
    # Rebalance is an actual mission recomputation: the surviving sweep child
    # now owns the whole remaining disposition rather than its old one-third
    # slice with two holes beside it.
    survivor_mission = orchestrator._agent_missions[active[0].agent_id]
    assert survivor_mission.params["slice_count"] == 1
    assert survivor_mission.params["recomputed_from_capacity"] == 1
    assert len(survivor_mission.params["area"]) == len(cover.params["area"])

    await _cancel_orchestrator(orchestrator)
    await bus.close()


@pytest.mark.asyncio
async def test_under_strength_response_reinforces_when_capacity_later_returns() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter(f"agent-{idx}") for idx in range(1, 5)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAdaptiveOrchestrator(
        bus=bus,
        registry=registry,
        max_reinforcements_per_objective=1,
        fleet_fixture=[
            _member("agent-1"),
            _member("agent-2"),
            _member("agent-3"),
            _member("agent-4", state=AgentState.OFFLINE),
        ],
    )
    cover = _cover_objective(minimum=2)
    donor = await orchestrator.dispatch_execution_group(cover)
    assert len(donor.members) == 3

    orchestrator.fleet_fixture = [
        _member("agent-1", state=AgentState.EN_ROUTE),
        _member("agent-2", state=AgentState.EN_ROUTE),
        _member("agent-3", state=AgentState.EN_ROUTE),
        _member("agent-4", state=AgentState.OFFLINE),
    ]
    response = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0001, lon=9.0001),
        team_size=2,
        minimum_capacity=1,
        priority=90,
        hover_s=60.0,
    )
    origin = await orchestrator.dispatch_execution_group(
        response, anomaly_id="alarm-1"
    )
    await asyncio.sleep(0.08)

    # Donor floor=2 permits exactly one diversion. Response is therefore
    # genuinely under strength rather than being scripted to "need backup".
    assert len(origin.members) == 1
    assert orchestrator.execution_groups[donor.id].state is ExecutionGroupState.DEGRADED

    # External world change only: an executor becomes available. The scenario
    # does not name it as reinforcement; reconciliation discovers it.
    orchestrator.fleet_fixture = [
        _member("agent-1", state=AgentState.EN_ROUTE),
        _member("agent-2", state=AgentState.EN_ROUTE),
        _member("agent-3", state=AgentState.EN_ROUTE),
        _member("agent-4", state=AgentState.DOCKED),
    ]
    reinforcement = await orchestrator.review_reinforcements()

    assert len(reinforcement) == 1
    second = reinforcement[0]
    assert second.id != origin.id
    assert second.reinforces_group_id == origin.id
    assert second.objective_mission_id == response.id
    assert second.anomaly_id == "alarm-1"
    assert [member.agent_id for member in second.members] == ["agent-4"]
    assert len(origin.members) == 1

    await _cancel_orchestrator(orchestrator)
    await bus.close()


@pytest.mark.asyncio
async def test_completed_objective_releases_tracked_capacity() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [HoldingAdapter("agent-1", finish=True), HoldingAdapter("agent-2", finish=True)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticAdaptiveOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=[_member("agent-1"), _member("agent-2")],
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0, lon=9.0),
        team_size=2,
        minimum_capacity=1,
        hover_s=0.0,
        priority=90,
    )
    group = await orchestrator.dispatch_execution_group(objective)

    async def _wait() -> None:
        while orchestrator.execution_groups[group.id].state not in {
            ExecutionGroupState.COMPLETED,
            ExecutionGroupState.FAILED,
        }:
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait(), timeout=1.0)
    await asyncio.sleep(0)

    assert orchestrator.execution_groups[group.id].state is ExecutionGroupState.COMPLETED
    assert orchestrator._agent_missions == {}
    assert orchestrator._busy == set()

    progress_task.cancel()
    await asyncio.gather(progress_task, return_exceptions=True)
    await _cancel_orchestrator(orchestrator)
    await bus.close()
