"""Authenticated mission-authority API boundary tests."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.authority import (
    MissionAuthorityGrant,
    MissionAuthorityVerdict,
    MissionDecision,
    MissionDecisionKind,
)
from swarm_core.messages import ObjectiveApprovalCommand

from backend.app.api import mission_authority
from swarm_os import SWARM_STATE

TEST_COMMANDER_ID = "op-commander01"
TEST_OPERATOR_ID = "op-operator01"


@dataclass
class RecordingBus:
    published: list[tuple[str, str]] = field(default_factory=list)

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))


@pytest.fixture()
def authority_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, RecordingBus]:
    SWARM_STATE.mission_authority_grants.clear()
    SWARM_STATE.mission_decisions.clear()
    SWARM_STATE.mission_decision_reviews.clear()
    SWARM_STATE.objective_states.clear()
    bus = RecordingBus()
    monkeypatch.setattr(mission_authority, "_bus", lambda: bus)
    app = FastAPI()
    app.include_router(mission_authority.router)
    return TestClient(app), bus


def test_grant_holder_is_derived_from_authenticated_commander(
    authority_client: tuple[TestClient, RecordingBus],
    commander_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    response = client.post(
        "/mission-authority/grants",
        headers=commander_headers,
        json={"objective_id": "objective-1", "approver_ids": [TEST_OPERATOR_ID]},
    )

    assert response.status_code == 202
    topic, payload = bus.published[-1]
    grant = MissionAuthorityGrant.model_validate_json(payload)
    assert topic == "swarm:mission-authority-grants"
    assert grant.holder_id == TEST_COMMANDER_ID


def test_grant_body_cannot_spoof_holder(
    authority_client: tuple[TestClient, RecordingBus],
    commander_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    response = client.post(
        "/mission-authority/grants",
        headers=commander_headers,
        json={
            "objective_id": "objective-1",
            "holder_id": "attacker-supplied",
        },
    )

    assert response.status_code == 422
    assert bus.published == []


def test_existing_grant_revision_cannot_be_rewritten(
    authority_client: tuple[TestClient, RecordingBus],
    commander_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    existing = MissionAuthorityGrant(
        grant_id="grant-immutable",
        revision=1,
        objective_id="objective-1",
        holder_id=TEST_COMMANDER_ID,
    )
    SWARM_STATE.mission_authority_grants[
        (existing.grant_id, existing.revision)
    ] = existing

    response = client.post(
        "/mission-authority/grants",
        headers=commander_headers,
        json={
            "grant_id": existing.grant_id,
            "revision": existing.revision,
            "objective_id": existing.objective_id,
            "approver_ids": [TEST_OPERATOR_ID],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "grant_revision_already_exists"
    assert bus.published == []


def test_review_actor_is_derived_from_jwt_and_bound_to_exact_decision(
    authority_client: tuple[TestClient, RecordingBus],
    operator_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    grant = MissionAuthorityGrant(
        grant_id="grant-1",
        objective_id="objective-1",
        holder_id=TEST_COMMANDER_ID,
        approver_ids=[TEST_OPERATOR_ID],
    )
    decision = MissionDecision(
        decision_id="decision-1",
        objective_id="objective-1",
        objective_revision=1,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        full_requirements_satisfied=True,
        authority_grant_id=grant.grant_id,
        authority_grant_revision=grant.revision,
        authority_verdict=MissionAuthorityVerdict.REVIEW_REQUIRED,
    )
    SWARM_STATE.mission_authority_grants[(grant.grant_id, grant.revision)] = grant
    SWARM_STATE.mission_decisions[decision.decision_id] = decision

    response = client.post(
        "/mission-authority/decisions/decision-1/review",
        headers=operator_headers,
        json={"action": "approve"},
    )

    assert response.status_code == 202
    topic, payload = bus.published[-1]
    command = ObjectiveApprovalCommand.model_validate_json(payload)
    assert topic == "swarm:missions:approvals"
    assert command.decision_id == decision.decision_id
    assert command.objective_id == decision.objective_id
    assert command.approved_by == TEST_OPERATOR_ID


def test_review_body_cannot_spoof_actor(
    authority_client: tuple[TestClient, RecordingBus],
    operator_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    decision = MissionDecision(
        decision_id="decision-legacy",
        objective_id="objective-legacy",
        objective_revision=1,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        full_requirements_satisfied=True,
        authority_verdict=MissionAuthorityVerdict.REVIEW_REQUIRED,
    )
    SWARM_STATE.mission_decisions[decision.decision_id] = decision

    response = client.post(
        "/mission-authority/decisions/decision-legacy/review",
        headers=operator_headers,
        json={"action": "approve", "approved_by": "risk-owner-spoof"},
    )

    assert response.status_code == 422
    assert bus.published == []


def test_non_approver_cannot_review_explicit_grant(
    authority_client: tuple[TestClient, RecordingBus],
    operator_headers: dict[str, str],
) -> None:
    client, bus = authority_client
    grant = MissionAuthorityGrant(
        grant_id="grant-locked",
        objective_id="objective-locked",
        holder_id=TEST_COMMANDER_ID,
    )
    decision = MissionDecision(
        decision_id="decision-locked",
        objective_id=grant.objective_id,
        objective_revision=1,
        decision_kind=MissionDecisionKind.LAUNCH_COMPOSITION,
        full_requirements_satisfied=True,
        authority_grant_id=grant.grant_id,
        authority_grant_revision=grant.revision,
        authority_verdict=MissionAuthorityVerdict.REVIEW_REQUIRED,
    )
    SWARM_STATE.mission_authority_grants[(grant.grant_id, grant.revision)] = grant
    SWARM_STATE.mission_decisions[decision.decision_id] = decision

    response = client.post(
        "/mission-authority/decisions/decision-locked/review",
        headers=operator_headers,
        json={"action": "approve"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "not_mission_approver"
    assert bus.published == []
