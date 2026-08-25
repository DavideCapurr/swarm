"""Mission-scoped delegated authority and immutable decision records."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from swarm_core.geometry import path_within_polygon
from swarm_core.messages import Geo, MissionTask, ObjectiveStatus


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


_STRICT = ConfigDict(extra="forbid")
_IMMUTABLE = ConfigDict(extra="forbid", frozen=True)


class MissionDecisionKind(str, Enum):
    LAUNCH_COMPOSITION = "LAUNCH_COMPOSITION"
    REPLACE_FAILED_EXECUTOR = "REPLACE_FAILED_EXECUTOR"
    REINFORCE_CAPACITY = "REINFORCE_CAPACITY"


class MissionAuthorityEffect(str, Enum):
    AUTO_AUTHORIZE = "auto_authorize"
    REVIEW_REQUIRED = "review_required"
    DENY = "deny"


class MissionAuthorityVerdict(str, Enum):
    AUTO_AUTHORIZED = "auto_authorized"
    REVIEW_REQUIRED = "review_required"
    DENIED = "denied"


class MissionReviewAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    OVERRIDE = "override"


class MissionAuthorityConstraints(BaseModel):
    """Small typed constraint set for the three implemented decision kinds."""

    model_config = _STRICT

    max_agents: int | None = Field(None, ge=1)
    allowed_agent_ids: list[str] = Field(default_factory=list)
    allowed_mission_kinds: list[str] = Field(default_factory=list)
    authorized_area: list[Geo] | None = Field(None, min_length=3)
    max_altitude_m: float | None = Field(None, gt=0.0)


class MissionHardConstraints(BaseModel):
    """Non-waivable site/airspace constraints evaluated before commitment."""

    model_config = _STRICT

    authorized_area: list[Geo] | None = Field(None, min_length=3)
    max_altitude_m: float | None = Field(None, gt=0.0)


class MissionAuthorityRule(BaseModel):
    model_config = _STRICT

    decision_kind: MissionDecisionKind
    effect: MissionAuthorityEffect
    constraints: MissionAuthorityConstraints = Field(
        default_factory=MissionAuthorityConstraints
    )


class MissionAuthorityGrant(BaseModel):
    """Authority delegated by one mission/risk owner for one objective."""

    model_config = _IMMUTABLE

    grant_id: str = Field(default_factory=_new_id)
    revision: int = Field(1, ge=1)
    objective_id: str
    holder_id: str
    approver_ids: list[str] = Field(default_factory=list)
    default_effect: MissionAuthorityEffect = MissionAuthorityEffect.REVIEW_REQUIRED
    delegated_rules: list[MissionAuthorityRule] = Field(default_factory=list)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    revoked_at: datetime | None = None
    created_at: datetime = Field(default_factory=_now)


class CandidateAssessment(BaseModel):
    """Deterministic assessment of one unit for one role."""

    model_config = _IMMUTABLE

    agent_id: str
    role: str
    supplied_capabilities: list[str] = Field(default_factory=list)
    availability_state: str
    score: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    selected: bool = False
    exclusion_reasons: list[str] = Field(default_factory=list)


class SelectedAssignment(BaseModel):
    model_config = _IMMUTABLE

    agent_id: str
    role: str
    mission_id: str
    supplied_capabilities: list[str] = Field(default_factory=list)


class MissionDecision(BaseModel):
    """Immutable record of what SwarmOS knew and why it selected a composition."""

    model_config = _IMMUTABLE

    decision_id: str = Field(default_factory=_new_id)
    objective_id: str
    objective_revision: int = Field(..., ge=1)
    decision_kind: MissionDecisionKind
    requirements_snapshot: dict[str, Any] = Field(default_factory=dict)
    constraints_snapshot: dict[str, Any] = Field(default_factory=dict)
    candidate_assessments: list[CandidateAssessment] = Field(default_factory=list)
    selected_assignments: list[SelectedAssignment] = Field(default_factory=list)
    full_requirements_satisfied: bool
    authority_grant_id: str | None = None
    authority_grant_revision: int | None = Field(None, ge=1)
    authority_verdict: MissionAuthorityVerdict
    authority_reasons: list[str] = Field(default_factory=list)
    supersedes_decision_id: str | None = None
    created_at: datetime = Field(default_factory=_now)


class MissionDecisionReview(BaseModel):
    """Append-only authenticated review of one immutable decision."""

    model_config = _IMMUTABLE

    review_id: str = Field(default_factory=_new_id)
    decision_id: str
    objective_id: str
    action: MissionReviewAction
    actor_id: str
    replacement_decision_id: str | None = None
    created_at: datetime = Field(default_factory=_now)


class ObjectiveStateFrame(BaseModel):
    """Current semantic objective state, separate from executor lifecycle."""

    model_config = _IMMUTABLE

    objective_id: str
    objective_revision: int = Field(..., ge=1)
    status: ObjectiveStatus
    decision_id: str | None = None
    reason: str | None = None
    ts: datetime = Field(default_factory=_now)


def legacy_authority_effect(
    policy: str, decision_kind: MissionDecisionKind
) -> MissionAuthorityEffect:
    """Compatibility map for objectives created before explicit grants exist."""

    if policy == "approval_required" and decision_kind is MissionDecisionKind.LAUNCH_COMPOSITION:
        return MissionAuthorityEffect.REVIEW_REQUIRED
    return MissionAuthorityEffect.AUTO_AUTHORIZE


def evaluate_mission_hard_constraints(
    objective: MissionTask,
    constraints: MissionHardConstraints | None,
) -> tuple[list[str], dict[str, Any]]:
    """Return non-waivable violations and the exact site-policy snapshot."""

    if constraints is None:
        return [], {}
    snapshot = constraints.model_dump(mode="json")
    reasons: list[str] = []
    raw_points = (
        [objective.params["geo"]]
        if "geo" in objective.params
        else list(objective.params.get("area", []))
    )
    try:
        points = [Geo.model_validate(point) for point in raw_points]
    except Exception:
        return ["HARD_CONSTRAINT_INVALID_GEOMETRY"], snapshot
    if (
        constraints.authorized_area is not None
        and points
        and not path_within_polygon(points, constraints.authorized_area)
    ):
        reasons.append("HARD_CONSTRAINT_OUTSIDE_GEOFENCE")

    requested_altitudes = [point.alt_m for point in points]
    if "altitude_m" in objective.params:
        requested_altitudes.append(float(objective.params["altitude_m"]))
    if "base_altitude_m" in objective.params:
        team_size = max(1, int(objective.params.get("team_size", 1)))
        requested_altitudes.append(
            float(objective.params["base_altitude_m"])
            + float(objective.params.get("altitude_step_m", 0.0)) * (team_size - 1)
        )
    if (
        constraints.max_altitude_m is not None
        and requested_altitudes
        and max(requested_altitudes) > constraints.max_altitude_m
    ):
        reasons.append("HARD_CONSTRAINT_ALTITUDE_EXCEEDED")
    return reasons, snapshot


def evaluate_mission_authority(
    *,
    objective: MissionTask,
    decision_kind: MissionDecisionKind,
    selected_agent_ids: list[str],
    grant: MissionAuthorityGrant | None,
    at: datetime | None = None,
) -> tuple[MissionAuthorityVerdict, list[str], dict[str, Any]]:
    """Evaluate one decision against the exact grant revision, fail closed."""

    if grant is None:
        effect = legacy_authority_effect(objective.authority_policy.value, decision_kind)
        verdict = (
            MissionAuthorityVerdict.AUTO_AUTHORIZED
            if effect is MissionAuthorityEffect.AUTO_AUTHORIZE
            else MissionAuthorityVerdict.REVIEW_REQUIRED
        )
        return verdict, ["LEGACY_AUTHORITY_POLICY"], {}

    reasons: list[str] = []
    now = at or datetime.now(UTC)
    if grant.objective_id != objective.id:
        return MissionAuthorityVerdict.DENIED, ["GRANT_OBJECTIVE_MISMATCH"], {}
    if objective.authority_grant_id != grant.grant_id:
        return MissionAuthorityVerdict.DENIED, ["GRANT_ID_MISMATCH"], {}
    if objective.authority_grant_revision != grant.revision:
        return MissionAuthorityVerdict.DENIED, ["GRANT_REVISION_STALE"], {}
    if grant.revoked_at is not None and grant.revoked_at <= now:
        return MissionAuthorityVerdict.DENIED, ["GRANT_REVOKED"], {}
    if grant.valid_from is not None and now < grant.valid_from:
        return MissionAuthorityVerdict.DENIED, ["GRANT_NOT_YET_VALID"], {}
    if grant.valid_until is not None and now > grant.valid_until:
        return MissionAuthorityVerdict.DENIED, ["GRANT_EXPIRED"], {}

    matching = [
        rule for rule in grant.delegated_rules if rule.decision_kind is decision_kind
    ]
    if len(matching) > 1:
        return MissionAuthorityVerdict.DENIED, ["AMBIGUOUS_AUTHORITY_RULE"], {}
    rule = matching[0] if matching else None
    effect = rule.effect if rule is not None else grant.default_effect
    constraints = rule.constraints if rule is not None else MissionAuthorityConstraints()
    snapshot = constraints.model_dump(mode="json")

    if effect is MissionAuthorityEffect.DENY:
        return MissionAuthorityVerdict.DENIED, ["DECISION_KIND_DENIED"], snapshot
    if effect is MissionAuthorityEffect.REVIEW_REQUIRED:
        return MissionAuthorityVerdict.REVIEW_REQUIRED, ["REVIEW_REQUIRED"], snapshot

    if constraints.max_agents is not None and len(selected_agent_ids) > constraints.max_agents:
        reasons.append("MAX_AGENTS_EXCEEDED")
    if constraints.allowed_agent_ids:
        disallowed = sorted(set(selected_agent_ids) - set(constraints.allowed_agent_ids))
        if disallowed:
            reasons.append("EXECUTOR_OUTSIDE_DELEGATION")
    if (
        constraints.allowed_mission_kinds
        and objective.kind not in constraints.allowed_mission_kinds
    ):
        reasons.append("MISSION_KIND_OUTSIDE_DELEGATION")
    if constraints.authorized_area is not None:
        raw_points = (
            [objective.params["geo"]]
            if "geo" in objective.params
            else list(objective.params.get("area", []))
        )
        points = [Geo(**point) for point in raw_points]
        if not path_within_polygon(points, constraints.authorized_area):
            reasons.append("OUTSIDE_DELEGATED_AREA")
    if constraints.max_altitude_m is not None:
        requested_altitude = float(objective.params.get("altitude_m", 0.0))
        if "base_altitude_m" in objective.params:
            team_size = max(1, int(objective.params.get("team_size", 1)))
            requested_altitude = float(objective.params["base_altitude_m"]) + (
                float(objective.params.get("altitude_step_m", 0.0)) * (team_size - 1)
            )
        if requested_altitude > constraints.max_altitude_m:
            reasons.append("ALTITUDE_OUTSIDE_DELEGATION")

    if reasons:
        return MissionAuthorityVerdict.REVIEW_REQUIRED, reasons, snapshot
    return MissionAuthorityVerdict.AUTO_AUTHORIZED, ["MATCHED_DELEGATED_RULE"], snapshot


__all__ = (
    "CandidateAssessment",
    "MissionAuthorityConstraints",
    "MissionAuthorityEffect",
    "MissionAuthorityGrant",
    "MissionAuthorityRule",
    "MissionAuthorityVerdict",
    "MissionDecision",
    "MissionDecisionKind",
    "MissionDecisionReview",
    "MissionHardConstraints",
    "MissionReviewAction",
    "ObjectiveStateFrame",
    "SelectedAssignment",
    "evaluate_mission_authority",
    "evaluate_mission_hard_constraints",
    "legacy_authority_effect",
)
