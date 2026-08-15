"""Structured allocator truth published for operator-facing surfaces.

The allocator already owns eligibility and scoring.  This module only gives
those decisions a strict transport shape so a Console can render the real
auction instead of reconstructing or narrating it client-side.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from swarm_core.messages import AgentState


def _now() -> datetime:
    return datetime.now(UTC)


_STRICT = ConfigDict(extra="forbid")


class AllocationExclusionReason(str, Enum):
    BUSY = "BUSY"
    LOW_BATTERY = "LOW_BATTERY"
    UNAVAILABLE = "UNAVAILABLE"


class AllocationScoreBreakdown(BaseModel):
    """Exact terms returned by ``allocator.score_bid``."""

    model_config = _STRICT

    distance_m: float
    distance_score: float
    battery_pct: float
    battery_score: float
    priority: float
    priority_score: float
    busy_penalty: float


class AllocationEligibleUnit(BaseModel):
    model_config = _STRICT

    agent_id: str
    fsm_state: AgentState
    battery_pct: float = Field(..., ge=0.0, le=100.0)
    score: float
    score_breakdown: AllocationScoreBreakdown


class AllocationExcludedUnit(BaseModel):
    model_config = _STRICT

    agent_id: str
    fsm_state: AgentState
    battery_pct: float = Field(..., ge=0.0, le=100.0)
    reason: AllocationExclusionReason
    active_mission_id: str | None = None


class AllocationDecision(BaseModel):
    """One complete allocator evaluation for one mission."""

    model_config = _STRICT

    mission_id: str
    mission_kind: str
    anomaly_id: str | None = None
    mode: Literal["auction", "diversion", "no_award"] = "auction"
    eligible_units: list[AllocationEligibleUnit] = Field(default_factory=list)
    excluded_units: list[AllocationExcludedUnit] = Field(default_factory=list)
    winner_agent_id: str | None = None
    winner_score: float | None = None
    ts: datetime = Field(default_factory=_now)


__all__ = (
    "AllocationDecision",
    "AllocationEligibleUnit",
    "AllocationExcludedUnit",
    "AllocationExclusionReason",
    "AllocationScoreBreakdown",
)
