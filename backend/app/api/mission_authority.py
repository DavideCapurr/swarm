"""Authenticated mission-authority grant and decision-review API."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.authority import (
    MissionAuthorityEffect,
    MissionAuthorityGrant,
    MissionAuthorityRule,
    MissionAuthorityVerdict,
)
from swarm_core.messages import ObjectiveApprovalCommand

from backend.app.auth.deps import (
    Principal,
    require_commander,
    require_operator,
    require_viewer,
)
from backend.app.db import get_repository
from orchestrator.swarm_orchestrator.bus import Bus
from swarm_os import SWARM_STATE

router = APIRouter(prefix="/mission-authority")


class GrantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: str | None = None
    revision: int = Field(1, ge=1)
    objective_id: str
    approver_ids: list[str] = Field(default_factory=list)
    default_effect: MissionAuthorityEffect = MissionAuthorityEffect.REVIEW_REQUIRED
    delegated_rules: list[MissionAuthorityRule] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    revoked_at: datetime | None = None


class OverrideAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    agent_id: str


class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["approve", "reject", "override"]
    override_assignments: list[OverrideAssignment] = Field(default_factory=list)


def _bus() -> Bus:
    from backend.app.main import bus_consumer

    return bus_consumer.bus


@router.post("/grants", status_code=status.HTTP_202_ACCEPTED)
async def create_grant(
    body: GrantBody,
    principal: Annotated[Principal, Depends(require_commander)],
) -> dict[str, str | int]:
    values = body.model_dump(exclude={"grant_id"})
    grant = MissionAuthorityGrant(
        **values,
        **({"grant_id": body.grant_id} if body.grant_id is not None else {}),
        holder_id=principal.operator_id,
    )
    existing = SWARM_STATE.mission_authority_grants.get(
        (grant.grant_id, grant.revision)
    )
    if existing is None and get_repository().enabled:
        rows = await get_repository().list_mission_authority_grants(
            objective_id=grant.objective_id,
            limit=500,
        )
        existing = next(
            (
                row
                for row in rows
                if row.grant_id == grant.grant_id and row.revision == grant.revision
            ),
            None,
        )
    if existing is not None:
        raise HTTPException(status_code=409, detail="grant_revision_already_exists")
    await _bus().publish(
        "swarm:mission-authority-grants", grant.model_dump_json()
    )
    return {"grant_id": grant.grant_id, "revision": grant.revision}


@router.post("/decisions/{decision_id}/review", status_code=status.HTTP_202_ACCEPTED)
async def review_decision(
    decision_id: str,
    body: ReviewBody,
    principal: Annotated[Principal, Depends(require_operator)],
) -> dict[str, str]:
    decision = SWARM_STATE.mission_decisions.get(decision_id)
    if decision is None:
        rows = await get_repository().list_mission_decisions(limit=500)
        decision = next((row for row in rows if row.decision_id == decision_id), None)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision_not_found")
    if decision.authority_verdict is MissionAuthorityVerdict.DENIED:
        raise HTTPException(status_code=409, detail="decision_not_reviewable")

    if decision.authority_grant_id is not None:
        revision = decision.authority_grant_revision
        grant = SWARM_STATE.mission_authority_grants.get(
            (decision.authority_grant_id, revision or 0)
        )
        if grant is None and get_repository().enabled:
            grants = await get_repository().list_mission_authority_grants(
                objective_id=decision.objective_id,
                limit=500,
            )
            grant = next(
                (
                    row
                    for row in grants
                    if row.grant_id == decision.authority_grant_id
                    and row.revision == revision
                ),
                None,
            )
        if grant is None:
            raise HTTPException(status_code=409, detail="authority_grant_unavailable")
        allowed = principal.operator_id == grant.holder_id or (
            principal.operator_id in grant.approver_ids
        )
        if not allowed:
            raise HTTPException(status_code=403, detail="not_mission_approver")

    command = ObjectiveApprovalCommand(
        objective_id=decision.objective_id,
        decision_id=decision.decision_id,
        approved_by=principal.operator_id,
        action=body.action,
        override_assignments=[
            assignment.model_dump() for assignment in body.override_assignments
        ],
    )
    await _bus().publish("swarm:missions:approvals", command.model_dump_json())
    return {"decision_id": decision.decision_id, "status": "review_submitted"}


@router.get("/grants")
async def list_grants(
    _: Annotated[Principal, Depends(require_viewer)],
    objective_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    if get_repository().enabled:
        rows = await get_repository().list_mission_authority_grants(
            objective_id=objective_id, limit=limit
        )
    else:
        rows = list(SWARM_STATE.mission_authority_grants.values())
        if objective_id is not None:
            rows = [row for row in rows if row.objective_id == objective_id]
    return {"grants": [row.model_dump(mode="json") for row in rows[-limit:]]}


@router.get("/decisions")
async def list_decisions(
    _: Annotated[Principal, Depends(require_viewer)],
    objective_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    if get_repository().enabled:
        rows = await get_repository().list_mission_decisions(
            objective_id=objective_id, limit=limit
        )
    else:
        rows = list(SWARM_STATE.mission_decisions.values())
        if objective_id is not None:
            rows = [row for row in rows if row.objective_id == objective_id]
    return {"decisions": [row.model_dump(mode="json") for row in rows[-limit:]]}


@router.get("/reviews")
async def list_reviews(
    _: Annotated[Principal, Depends(require_viewer)],
    decision_id: str | None = None,
    objective_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    if get_repository().enabled:
        rows = await get_repository().list_mission_decision_reviews(
            decision_id=decision_id,
            objective_id=objective_id,
            limit=limit,
        )
    else:
        rows = list(SWARM_STATE.mission_decision_reviews)
        if decision_id is not None:
            rows = [row for row in rows if row.decision_id == decision_id]
        if objective_id is not None:
            rows = [row for row in rows if row.objective_id == objective_id]
    return {"reviews": [row.model_dump(mode="json") for row in rows[-limit:]]}


@router.get("/objectives")
async def list_objective_states(
    _: Annotated[Principal, Depends(require_viewer)],
    objective_id: str | None = None,
) -> dict[str, object]:
    rows = list(SWARM_STATE.objective_states.values())
    if objective_id is not None:
        rows = [row for row in rows if row.objective_id == objective_id]
    return {"objective_states": [row.model_dump(mode="json") for row in rows]}
