"""Structured mission-runtime frames for operator-facing truth surfaces.

MissionProgress remains the adapter/orchestrator execution contract.  These
frames add the owning agent and any adapter-supplied proof behind a phase, so a
Console never has to infer why ON_STATION or RTL was reported.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    from uuid import uuid4

    return uuid4().hex


class MissionRuntimeEvidence(str, Enum):
    MAVLINK_MISSION_ITEM_REACHED = "mavlink_mission_item_reached"
    MAVLINK_RTL_COMMAND_ACKNOWLEDGED = "mavlink_rtl_command_acknowledged"


class MissionRuntimeEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    mission_id: str
    agent_id: str
    phase: str
    progress_pct: float = Field(0.0, ge=0.0, le=100.0)
    evidence: MissionRuntimeEvidence | None = None
    error: str | None = None
    ts: datetime = Field(default_factory=_now)


__all__ = ("MissionRuntimeEvent", "MissionRuntimeEvidence")
