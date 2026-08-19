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
from swarm_core.missions import (
    COOPERATIVE_VERIFY,
    COOPERATIVE_VERIFY_KIND,
    MissionKind,
)

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.execution_groups import (
    EXECUTION_GROUP_TOPIC,
    ExecutionGroupOrchestrator,
    ReinforcementObservation,
    shortfall_reinforcement_policy,
)


class FakeAdapter:
    vendor = "fake"
    model = "thin-executor"

    def __init__(
        self,
        agent_id: str,
        *,
        fail_first: bool = False,
        fail_always: bool = False,
        raise_first: bool = False,
        hold: asyncio.Event | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.fail_first = fail_first
        self.fail_always = fail_always
        self.raise_first = raise_first
        # When set, the executor stays EN_ROUTE until the event is released, so
        # a test can observe the group while it is still running.
        self.hold = hold
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
        if self.fail_always or (self.fail_first and not self.failed_once):
            self.failed_once = True
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=25.0,
                error="injected failure",
            )
            return
        if self.hold is not None:
            await self.hold.wait()
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


async def _collect_group_frames(
    bus: InMemoryBus, sink: list[ExecutionGroup]
) -> None:
    async for _topic, payload in bus.subscribe(EXECUTION_GROUP_TOPIC):
        sink.append(ExecutionGroup.model_validate_json(payload))


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
async def test_partial_strength_group_dispatches_the_roles_it_can_fill() -> None:
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

    # Two of three roles were fillable, so two fly. The shortfall is readable
    # from the counts alone — no extra field carries it.
    assert terminal.requested_members == 3
    assert len(terminal.members) == 2
    assert len(terminal.members) < terminal.requested_members
    assert terminal.failure_reason is None
    assert terminal.state is ExecutionGroupState.COMPLETED
    assert {member.role for member in terminal.members} == {
        "PRIMARY_OBSERVER",
        "SECONDARY_OBSERVER",
    }
    assert all(len(adapter.executed) == 1 for adapter in adapters)


@pytest.mark.asyncio
async def test_execution_group_fails_closed_when_no_role_can_be_filled() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [FakeAdapter("agent-1"), FakeAdapter("agent-2")]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        # Both below MIN_BATTERY_PCT: no role is fillable at all.
        fleet_fixture=_fleet(10.0, 12.0),
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


@pytest.mark.asyncio
async def test_replacement_cap_per_role_is_unchanged() -> None:
    """The per-role replacement cap keeps its exact prior behaviour."""

    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [
        FakeAdapter("agent-1", fail_always=True),
        FakeAdapter("agent-2"),
        FakeAdapter("agent-3"),
        FakeAdapter("agent-4", fail_always=True),
    ]
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

    # One replacement is allowed; the second failure on the same role stops it.
    assert terminal.state is ExecutionGroupState.FAILED
    assert terminal.failure_reason == "ROLE_FAILED:PRIMARY_OBSERVER:REPLACEMENT_LIMIT"
    replacements = [
        member for member in terminal.members if member.replaces_agent_id is not None
    ]
    assert len(replacements) == 1
    assert replacements[0].replaces_agent_id == "agent-1"
    # Replacement is a repair inside one swarm, never a second swarm.
    assert all(
        held.reinforces_group_id is None
        for held in orchestrator.execution_groups.values()
    )


# ── the reinforcement policy seam ────────────────────────────────────────────


def _observation(**overrides: object) -> ReinforcementObservation:
    base: dict[str, object] = {
        "objective_kind": COOPERATIVE_VERIFY_KIND,
        "objective_state": ExecutionGroupState.ACTIVE,
        "requested_members": 3,
        "committed_members": 2,
        "eligible_agents": 1,
        "reinforcements_dispatched": 0,
        "max_reinforcements": 1,
    }
    base.update(overrides)
    return ReinforcementObservation(**base)  # type: ignore[arg-type]


def test_policy_reinforces_a_running_under_strength_objective() -> None:
    decision = shortfall_reinforcement_policy(_observation())
    assert decision.reinforce is True
    assert decision.strength == 1
    assert decision.reason == "STRENGTH_SHORTFALL"


def test_policy_clamps_strength_to_available_capacity() -> None:
    decision = shortfall_reinforcement_policy(
        _observation(committed_members=1, eligible_agents=1)
    )
    assert decision.strength == 1

    decision = shortfall_reinforcement_policy(
        _observation(committed_members=1, eligible_agents=5)
    )
    assert decision.strength == 2


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"objective_state": ExecutionGroupState.COMPLETED}, "GROUP_NOT_RUNNING"),
        ({"objective_state": ExecutionGroupState.FAILED}, "GROUP_NOT_RUNNING"),
        ({"reinforcements_dispatched": 1}, "REINFORCEMENT_LIMIT"),
        ({"max_reinforcements": 0}, "REINFORCEMENT_LIMIT"),
        ({"committed_members": 3}, "AT_REQUESTED_STRENGTH"),
        ({"eligible_agents": 0}, "NO_ELIGIBLE_CAPACITY"),
    ],
)
def test_policy_declines_with_a_named_reason(
    overrides: dict[str, object], reason: str
) -> None:
    decision = shortfall_reinforcement_policy(_observation(**overrides))
    assert decision.reinforce is False
    assert decision.strength == 0
    assert decision.reason == reason


def test_policy_reinforces_a_degraded_group() -> None:
    decision = shortfall_reinforcement_policy(
        _observation(objective_state=ExecutionGroupState.DEGRADED)
    )
    assert decision.reinforce is True


# ── reinforcement as a second swarm ──────────────────────────────────────────


async def _run_under_strength_objective(
    orchestrator: StaticExecutionGroupOrchestrator,
) -> tuple[ExecutionGroup, MissionTask]:
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
        hover_s=0.0,
    )
    group = await orchestrator.dispatch_execution_group(
        objective, anomaly_id="anomaly-1"
    )
    assert group.state is ExecutionGroupState.ACTIVE
    assert len(group.members) == 2
    return group, objective


@pytest.mark.asyncio
async def test_reinforcement_dispatches_a_second_group_with_published_provenance() -> (
    None
):
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    hold = asyncio.Event()
    adapters = [FakeAdapter(f"agent-{idx}", hold=hold) for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        # agent-3 is below MIN_BATTERY_PCT at composition time.
        fleet_fixture=_fleet(95.0, 85.0, 10.0),
    )
    published: list[ExecutionGroup] = []
    frames_task = asyncio.create_task(_collect_group_frames(bus, published))
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    origin, objective = await _run_under_strength_objective(orchestrator)

    # An executor becomes eligible again. The review is SwarmOS-initiated.
    orchestrator.fleet_fixture = _fleet(95.0, 85.0, 90.0)
    dispatched = await orchestrator.review_reinforcements()

    hold.set()
    origin_terminal = await _wait_group_terminal(orchestrator, origin.id)
    reinforcement = dispatched[0]
    reinforcement_terminal = await _wait_group_terminal(orchestrator, reinforcement.id)

    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    frames_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await frames_task
    await bus.close()

    assert len(dispatched) == 1
    # Reinforcement is another unit of command, not extra members on the first.
    assert reinforcement.id != origin.id
    assert reinforcement_terminal.reinforces_group_id == origin.id
    assert origin_terminal.reinforces_group_id is None
    assert len(origin_terminal.members) == 2
    assert [member.agent_id for member in reinforcement_terminal.members] == ["agent-3"]
    assert reinforcement_terminal.requested_members == 1
    assert reinforcement_terminal.members[0].role == "OVERWATCH"
    # No member carries replacement provenance: nothing failed.
    assert all(
        member.replaces_agent_id is None
        for member in reinforcement_terminal.members + origin_terminal.members
    )
    # Same objective, same anomaly — the relationship is published, not inferred.
    assert reinforcement_terminal.objective_mission_id == objective.id
    assert reinforcement_terminal.anomaly_id == "anomaly-1"
    assert reinforcement_terminal.objective_kind == origin_terminal.objective_kind
    # The child mission carries the objective through to the executor.
    assert adapters[2].executed[0].params["parent_objective_id"] == objective.id
    assert adapters[2].executed[0].params["execution_group_id"] == reinforcement.id
    assert adapters[2].executed[0].id != adapters[0].executed[0].id

    reinforcing_frames = [
        frame for frame in published if frame.reinforces_group_id == origin.id
    ]
    assert reinforcing_frames
    assert all(frame.id == reinforcement.id for frame in reinforcing_frames)
    assert reinforcing_frames[-1].state is ExecutionGroupState.COMPLETED


@pytest.mark.asyncio
async def test_reinforcement_is_withheld_when_the_policy_declines() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    hold = asyncio.Event()
    adapters = [FakeAdapter(f"agent-{idx}", hold=hold) for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(95.0, 85.0, 10.0),
        max_reinforcements_per_objective=0,
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    origin, _objective = await _run_under_strength_objective(orchestrator)

    orchestrator.fleet_fixture = _fleet(95.0, 85.0, 90.0)
    dispatched = await orchestrator.review_reinforcements()

    hold.set()
    await _wait_group_terminal(orchestrator, origin.id)
    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await bus.close()

    # The mechanism was ready and capacity existed; only the judgement withheld.
    assert dispatched == []
    assert list(orchestrator.execution_groups) == [origin.id]
    assert adapters[2].executed == []


@pytest.mark.asyncio
async def test_full_strength_objective_is_never_reinforced() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    hold = asyncio.Event()
    adapters = [FakeAdapter(f"agent-{idx}", hold=hold) for idx in range(1, 5)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(95.0, 85.0, 75.0, 65.0),
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=3,
        hover_s=0.0,
    )
    group = await orchestrator.dispatch_execution_group(objective)
    assert len(group.members) == 3

    dispatched = await orchestrator.review_reinforcements()

    hold.set()
    await _wait_group_terminal(orchestrator, group.id)
    progress_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await progress_task
    await bus.close()

    # A spare was eligible the whole time; strength was already satisfied.
    assert dispatched == []
    assert adapters[3].executed == []
