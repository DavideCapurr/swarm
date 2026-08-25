from __future__ import annotations

import asyncio

import pytest
from swarm_core.authority import (
    MissionAuthorityEffect,
    MissionAuthorityGrant,
    MissionAuthorityRule,
    MissionAuthorityVerdict,
    MissionDecisionKind,
    MissionHardConstraints,
)
from swarm_core.execution_groups import ExecutionGroupState
from swarm_core.messages import (
    AgentState,
    FleetState,
    Geo,
    MissionTask,
    ObjectiveApprovalCommand,
    ObjectiveAuthorityPolicy,
)
from swarm_core.missions import COOPERATIVE_VERIFY, VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.tests.test_execution_groups import (
    FakeAdapter,
    StaticExecutionGroupOrchestrator,
    _wait_group_terminal,
)


def _fleet() -> list[FleetState]:
    return [
        FleetState(
            agent_id="agent-1",
            vendor="fake",
            model="thin-executor",
            fsm_state=AgentState.DOCKED,
            battery_pct=95.0,
            geo=Geo(lat=45.0, lon=9.0),
            capabilities=["thermal_observation"],
        ),
        FleetState(
            agent_id="agent-2",
            vendor="fake",
            model="thin-executor",
            fsm_state=AgentState.DOCKED,
            battery_pct=85.0,
            geo=Geo(lat=45.0, lon=9.0),
            capabilities=["visual_observation"],
        ),
        FleetState(
            agent_id="agent-3",
            vendor="fake",
            model="thin-executor",
            fsm_state=AgentState.DOCKED,
            battery_pct=75.0,
            geo=Geo(lat=45.0, lon=9.0),
            capabilities=["thermal_observation", "visual_observation"],
        ),
    ]


async def _orchestrator() -> tuple[
    StaticExecutionGroupOrchestrator, dict[str, FakeAdapter]
]:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = {agent.agent_id: FakeAdapter(agent.agent_id) for agent in _fleet()}
    for adapter in adapters.values():
        registry.register(adapter)  # type: ignore[arg-type]
    orchestrator = StaticExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(),
    )
    progress_task = asyncio.create_task(orchestrator._execution_group_progress_loop())
    orchestrator._background_tasks.add(progress_task)
    await asyncio.sleep(0)
    return orchestrator, adapters


def _objective(**kwargs: object) -> MissionTask:
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        team_size=2,
        hover_s=0.0,
        **kwargs,  # type: ignore[arg-type]
    )
    objective.params["role_requirements"] = {
        "PRIMARY_OBSERVER": ["thermal_observation"],
        "SECONDARY_OBSERVER": ["visual_observation"],
    }
    return objective


@pytest.mark.asyncio
async def test_recommendation_without_launch_authority_does_not_execute() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = _objective(
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED
    )

    group = await orchestrator.dispatch_execution_group(objective)
    decision = orchestrator.mission_decisions[group.decision_id or ""]

    assert group.state is ExecutionGroupState.FORMING
    assert decision.authority_verdict is MissionAuthorityVerdict.REVIEW_REQUIRED
    assert objective.status.value == "waiting_for_approval"
    assert not any(adapter.executed for adapter in adapters.values())


@pytest.mark.asyncio
async def test_approved_exact_recommendation_executes() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = _objective(
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED
    )
    group = await orchestrator.dispatch_execution_group(objective)

    approved = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=group.decision_id or "",
            approved_by="risk-owner",
        )
    )

    assert approved is group
    terminal = await _wait_group_terminal(orchestrator, group.id)
    assert terminal.state is ExecutionGroupState.COMPLETED
    assert objective.status.value == "unresolved"
    assert sum(len(adapter.executed) for adapter in adapters.values()) == 2


@pytest.mark.asyncio
async def test_single_executor_launch_uses_the_same_exact_decision_pipeline() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = VERIFY(
        geo=Geo(lat=45.001, lon=9.001),
        hover_s=0.0,
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED,
        required_capabilities=["thermal_observation"],
    )

    await orchestrator._auction_and_dispatch(objective, anomaly_id="anomaly-1")
    decision = next(
        row
        for row in orchestrator.mission_decisions.values()
        if row.objective_id == objective.id
    )
    group = orchestrator.execution_groups[
        orchestrator._decision_groups[decision.decision_id]
    ]

    assert decision.selected_assignments[0].role == "EXECUTOR"
    assert decision.authority_verdict is MissionAuthorityVerdict.REVIEW_REQUIRED
    assert not any(adapter.executed for adapter in adapters.values())
    assert "execution_group_id" not in objective.params

    approved = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=decision.decision_id,
            approved_by="risk-owner",
        )
    )

    assert approved is group
    await _wait_group_terminal(orchestrator, group.id)
    assert sum(len(adapter.executed) for adapter in adapters.values()) == 1


@pytest.mark.asyncio
async def test_grant_auto_authorizes_launch_and_records_real_rationale() -> None:
    orchestrator, _adapters = await _orchestrator()
    objective = _objective(
        authority_grant_id="grant-1",
        authority_grant_revision=1,
    )
    orchestrator.register_authority_grant(
        MissionAuthorityGrant(
            grant_id="grant-1",
            revision=1,
            objective_id=objective.id,
            holder_id="risk-owner",
            delegated_rules=[
                MissionAuthorityRule(
                    decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
                    effect=MissionAuthorityEffect.AUTO_AUTHORIZE,
                )
            ],
        )
    )

    group = await orchestrator.dispatch_execution_group(objective)
    decision = orchestrator.mission_decisions[group.decision_id or ""]
    await _wait_group_terminal(orchestrator, group.id)

    assert decision.authority_verdict is MissionAuthorityVerdict.AUTO_AUTHORIZED
    assert decision.full_requirements_satisfied is True
    assert {row.role for row in decision.selected_assignments} == {
        "PRIMARY_OBSERVER",
        "SECONDARY_OBSERVER",
    }
    mismatch = [
        row
        for row in decision.candidate_assessments
        if row.role == "PRIMARY_OBSERVER" and row.agent_id == "agent-2"
    ]
    assert mismatch[0].exclusion_reasons == ["CAPABILITY_MISMATCH"]


@pytest.mark.asyncio
async def test_rejection_is_audited_and_never_executes() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = _objective(
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED
    )
    group = await orchestrator.dispatch_execution_group(objective)

    rejected = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=group.decision_id or "",
            approved_by="risk-owner",
            action="reject",
        )
    )

    assert rejected is group
    assert group.failure_reason == "DECISION_REJECTED"
    assert not any(adapter.executed for adapter in adapters.values())
    assert next(iter(orchestrator._decision_reviews.values())).action.value == "reject"


@pytest.mark.asyncio
async def test_override_creates_superseding_decision_and_executes_new_selection() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = _objective(
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED
    )
    original_group = await orchestrator.dispatch_execution_group(objective)
    original_decision_id = original_group.decision_id or ""

    replacement = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=original_decision_id,
            approved_by="risk-owner",
            action="override",
            override_assignments=[
                {"role": "PRIMARY_OBSERVER", "agent_id": "agent-3"},
                {"role": "SECONDARY_OBSERVER", "agent_id": "agent-2"},
            ],
        )
    )

    assert replacement is not None
    replacement_decision = orchestrator.mission_decisions[
        replacement.decision_id or ""
    ]
    assert replacement_decision.supersedes_decision_id == original_decision_id
    assert [
        row.agent_id for row in replacement_decision.selected_assignments
    ] == ["agent-3", "agent-2"]
    await _wait_group_terminal(orchestrator, replacement.id)
    assert not adapters["agent-1"].executed


@pytest.mark.asyncio
async def test_new_grant_revision_between_recommendation_and_claim_blocks_dispatch() -> None:
    orchestrator, adapters = await _orchestrator()
    objective = _objective(
        authority_grant_id="grant-1",
        authority_grant_revision=1,
    )
    first = MissionAuthorityGrant(
        grant_id="grant-1",
        revision=1,
        objective_id=objective.id,
        holder_id="risk-owner",
    )
    orchestrator.register_authority_grant(first)
    group = await orchestrator.dispatch_execution_group(objective)
    orchestrator.register_authority_grant(
        first.model_copy(update={"revision": 2})
    )

    result = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=group.decision_id or "",
            approved_by="risk-owner",
        )
    )

    assert result is None
    await asyncio.sleep(0)
    assert not any(adapter.executed for adapter in adapters.values())


@pytest.mark.asyncio
async def test_hard_geofence_denial_cannot_be_approved() -> None:
    orchestrator, adapters = await _orchestrator()
    orchestrator.hard_constraint_provider = lambda: MissionHardConstraints(
        authorized_area=[
            Geo(lat=44.0, lon=8.0),
            Geo(lat=44.0, lon=8.1),
            Geo(lat=44.1, lon=8.1),
            Geo(lat=44.1, lon=8.0),
        ],
        max_altitude_m=120.0,
    )
    objective = _objective(
        authority_policy=ObjectiveAuthorityPolicy.APPROVAL_REQUIRED
    )

    group = await orchestrator.dispatch_execution_group(objective)
    decision = orchestrator.mission_decisions[group.decision_id or ""]
    result = await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=decision.decision_id,
            approved_by="risk-owner",
        )
    )

    assert decision.authority_verdict is MissionAuthorityVerdict.DENIED
    assert "HARD_CONSTRAINT_OUTSIDE_GEOFENCE" in decision.authority_reasons
    assert result is None
    assert not any(adapter.executed for adapter in adapters.values())
