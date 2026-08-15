from __future__ import annotations

import pytest
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMember,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.messages import Anomaly, AnomalyKind, AnomalyState, Geo, MissionProgress

from swarm_os.coordinator import SwarmCoordinator
from swarm_os.state import SwarmState


def _group(anomaly_id: str, *, state: ExecutionGroupState) -> ExecutionGroup:
    member_state = (
        ExecutionGroupMemberState.COMPLETED
        if state is ExecutionGroupState.COMPLETED
        else ExecutionGroupMemberState.ACTIVE
    )
    return ExecutionGroup(
        id="group-aggregate-test",
        objective_mission_id="objective-aggregate-test",
        objective_kind="COOPERATIVE_VERIFY",
        anomaly_id=anomaly_id,
        requested_members=3,
        state=state,
        members=[
            ExecutionGroupMember(
                agent_id="mav-001",
                role="PRIMARY_OBSERVER",
                mission_id="child-primary",
                state=member_state,
                score=2.9,
            ),
            ExecutionGroupMember(
                agent_id="mav-002",
                role="SECONDARY_OBSERVER",
                mission_id="child-secondary",
                state=member_state,
                score=2.7,
            ),
            ExecutionGroupMember(
                agent_id="mav-003",
                role="OVERWATCH",
                mission_id="child-overwatch",
                state=member_state,
                score=2.5,
            ),
        ],
    )


@pytest.mark.asyncio
async def test_child_done_cannot_verify_cooperative_objective() -> None:
    state = SwarmState.vineyard()
    state.set_autonomy_enabled(False)
    coordinator = SwarmCoordinator(state)
    anomaly = Anomaly(
        id="intrusion-coop",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=44.7001, lon=8.0301),
        confidence=0.99,
    )

    await coordinator.apply_anomaly(anomaly)
    assert state.anomalies[anomaly.id].state is AnomalyState.PENDING

    active = _group(anomaly.id, state=ExecutionGroupState.ACTIVE)
    await coordinator.apply_execution_group(active)
    projected = state.anomalies[anomaly.id]
    assert projected.state is AnomalyState.VERIFYING
    assert projected.verifying_agent == "mav-001"

    await coordinator.apply_mission_progress(
        MissionProgress(
            mission_id="child-primary",
            agent_id="mav-001",
            execution_group_id=active.id,
            execution_role="PRIMARY_OBSERVER",
            parent_objective_id=active.objective_mission_id,
            phase="DONE",
            progress_pct=100.0,
        )
    )

    # One member completing is evidence, not authority to complete the shared
    # objective. Only the aggregate ExecutionGroup lifecycle can do that.
    assert state.anomalies[anomaly.id].state is AnomalyState.VERIFYING

    completed = _group(anomaly.id, state=ExecutionGroupState.COMPLETED)
    await coordinator.apply_execution_group(completed)
    assert state.anomalies[anomaly.id].state is AnomalyState.VERIFIED


@pytest.mark.asyncio
async def test_unrecoverable_group_failure_returns_anomaly_to_pending() -> None:
    state = SwarmState.vineyard()
    state.set_autonomy_enabled(False)
    coordinator = SwarmCoordinator(state)
    anomaly = Anomaly(
        id="intrusion-failed-group",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=44.7001, lon=8.0301),
        confidence=0.99,
    )

    await coordinator.apply_anomaly(anomaly)
    await coordinator.apply_execution_group(
        _group(anomaly.id, state=ExecutionGroupState.ACTIVE)
    )
    assert state.anomalies[anomaly.id].state is AnomalyState.VERIFYING

    failed = _group(anomaly.id, state=ExecutionGroupState.FAILED).model_copy(
        update={"failure_reason": "ROLE_FAILED:OVERWATCH:NO_REPLACEMENT"}
    )
    await coordinator.apply_execution_group(failed)

    projected = state.anomalies[anomaly.id]
    assert projected.state is AnomalyState.PENDING
    assert projected.verifying_agent is None
