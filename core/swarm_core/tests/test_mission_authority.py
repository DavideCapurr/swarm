from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from swarm_core.authority import (
    MissionAuthorityConstraints,
    MissionAuthorityEffect,
    MissionAuthorityGrant,
    MissionAuthorityRule,
    MissionAuthorityVerdict,
    MissionDecisionKind,
    MissionHardConstraints,
    evaluate_mission_authority,
    evaluate_mission_hard_constraints,
    legacy_authority_effect,
)
from swarm_core.messages import Geo, ObjectiveAuthorityPolicy
from swarm_core.missions import COOPERATIVE_VERIFY


def test_legacy_policy_maps_launch_to_review_but_changes_to_delegated() -> None:
    policy = ObjectiveAuthorityPolicy.APPROVAL_REQUIRED.value

    assert (
        legacy_authority_effect(policy, MissionDecisionKind.LAUNCH_COMPOSITION)
        is MissionAuthorityEffect.REVIEW_REQUIRED
    )
    assert (
        legacy_authority_effect(policy, MissionDecisionKind.REPLACE_FAILED_EXECUTOR)
        is MissionAuthorityEffect.AUTO_AUTHORIZE
    )
    assert (
        legacy_authority_effect(policy, MissionDecisionKind.REINFORCE_CAPACITY)
        is MissionAuthorityEffect.AUTO_AUTHORIZE
    )


def test_unknown_authority_constraint_fails_closed_at_validation() -> None:
    with pytest.raises(ValidationError):
        MissionAuthorityConstraints.model_validate({"unknown_constraint": True})


def test_exact_grant_revision_auto_authorizes_only_inside_typed_constraints() -> None:
    now = datetime.now(UTC)
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0, lon=9.0),
        team_size=2,
        authority_grant_id="grant-1",
        authority_grant_revision=2,
    )
    grant = MissionAuthorityGrant(
        grant_id="grant-1",
        revision=2,
        objective_id=objective.id,
        holder_id="risk-owner",
        valid_from=now - timedelta(minutes=1),
        valid_until=now + timedelta(minutes=10),
        delegated_rules=[
            MissionAuthorityRule(
                decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
                effect=MissionAuthorityEffect.AUTO_AUTHORIZE,
                constraints=MissionAuthorityConstraints(
                    max_agents=2,
                    allowed_agent_ids=["agent-1", "agent-2"],
                    allowed_mission_kinds=[objective.kind],
                    authorized_area=[
                        Geo(lat=44.9, lon=8.9),
                        Geo(lat=44.9, lon=9.1),
                        Geo(lat=45.1, lon=9.1),
                        Geo(lat=45.1, lon=8.9),
                    ],
                    max_altitude_m=80.0,
                ),
            )
        ],
    )

    verdict, reasons, snapshot = evaluate_mission_authority(
        objective=objective,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        selected_agent_ids=["agent-1", "agent-2"],
        grant=grant,
        at=now,
    )
    assert verdict is MissionAuthorityVerdict.AUTO_AUTHORIZED
    assert reasons == ["MATCHED_DELEGATED_RULE"]
    assert snapshot["max_agents"] == 2

    verdict, reasons, _ = evaluate_mission_authority(
        objective=objective,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        selected_agent_ids=["agent-1", "agent-3"],
        grant=grant,
        at=now,
    )
    assert verdict is MissionAuthorityVerdict.REVIEW_REQUIRED
    assert "EXECUTOR_OUTSIDE_DELEGATION" in reasons


def test_stale_or_revoked_grant_cannot_be_approved_away() -> None:
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=45.0, lon=9.0),
        team_size=2,
        authority_grant_id="grant-1",
        authority_grant_revision=1,
    )
    grant = MissionAuthorityGrant(
        grant_id="grant-1",
        revision=2,
        objective_id=objective.id,
        holder_id="risk-owner",
    )

    verdict, reasons, _ = evaluate_mission_authority(
        objective=objective,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        selected_agent_ids=["agent-1", "agent-2"],
        grant=grant,
    )
    assert verdict is MissionAuthorityVerdict.DENIED
    assert reasons == ["GRANT_REVISION_STALE"]

    revoked_objective = objective.model_copy(
        update={"authority_grant_revision": 2}
    )
    revoked = grant.model_copy(update={"revoked_at": datetime.now(UTC)})
    verdict, reasons, _ = evaluate_mission_authority(
        objective=revoked_objective,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        selected_agent_ids=["agent-1", "agent-2"],
        grant=revoked,
    )
    assert verdict is MissionAuthorityVerdict.DENIED
    assert reasons == ["GRANT_REVOKED"]


def test_hard_geofence_and_altitude_constraints_are_non_waivable_facts() -> None:
    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=46.0, lon=10.0),
        team_size=2,
        base_altitude_m=70.0,
        altitude_step_m=20.0,
    )
    constraints = MissionHardConstraints(
        authorized_area=[
            Geo(lat=44.9, lon=8.9),
            Geo(lat=44.9, lon=9.1),
            Geo(lat=45.1, lon=9.1),
            Geo(lat=45.1, lon=8.9),
        ],
        max_altitude_m=80.0,
    )

    reasons, snapshot = evaluate_mission_hard_constraints(objective, constraints)

    assert reasons == [
        "HARD_CONSTRAINT_OUTSIDE_GEOFENCE",
        "HARD_CONSTRAINT_ALTITUDE_EXCEEDED",
    ]
    assert snapshot["max_altitude_m"] == 80.0
