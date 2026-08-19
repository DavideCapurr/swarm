"""SwarmOS-owned multi-agent execution-group truth.

An execution group is a logical coordination object, never an autonomous
sub-swarm. SwarmOS creates it, selects every member, assigns every role, and
replaces members when required. Physical agents only receive their own child
``MissionTask`` and never gain authority over peers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


_STRICT = ConfigDict(extra="forbid")


class ExecutionGroupState(str, Enum):
    FORMING = "FORMING"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ExecutionGroupMemberState(str, Enum):
    ASSIGNED = "ASSIGNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REPLACED = "REPLACED"
    # Capacity was deliberately pulled from this group by SwarmOS policy. This
    # is not a physical failure and not a replacement of the member in-place.
    DIVERTED = "DIVERTED"


class ExecutionGroupMember(BaseModel):
    """One SwarmOS-owned role assignment inside a logical group."""

    model_config = _STRICT

    agent_id: str
    role: str
    mission_id: str
    state: ExecutionGroupMemberState = ExecutionGroupMemberState.ASSIGNED
    score: float
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    replaces_agent_id: str | None = None
    # Set when this assignment itself was obtained by preempting committed
    # capacity. These fields make the capacity transfer auditable without
    # asking the UI to infer it from timing or aircraft identity.
    diverted_from_mission_id: str | None = None
    diverted_from_objective_id: str | None = None
    ts: datetime = Field(default_factory=_now)


class ExecutionGroup(BaseModel):
    """Authoritative composition and lifecycle of one multi-agent objective."""

    model_config = _STRICT

    id: str = Field(default_factory=_new_id)
    objective_mission_id: str
    objective_kind: str
    anomaly_id: str | None = None
    # Set when SwarmOS dispatched this group to reinforce an already-running one
    # against the same objective. Published provenance, exactly like
    # `ExecutionGroupMember.replaces_agent_id` — a reader must never have to
    # infer the relationship from a shared `anomaly_id`.
    reinforces_group_id: str | None = None
    requested_members: int = Field(..., ge=1)
    members: list[ExecutionGroupMember] = Field(default_factory=list)
    state: ExecutionGroupState = ExecutionGroupState.FORMING
    failure_reason: str | None = None
    ts: datetime = Field(default_factory=_now)


__all__ = (
    "ExecutionGroup",
    "ExecutionGroupMember",
    "ExecutionGroupMemberState",
    "ExecutionGroupState",
)
