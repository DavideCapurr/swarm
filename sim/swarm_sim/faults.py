"""Simulation-only external fault events.

Fault identity is a fact about the simulated world. It is deliberately separate
from recovery: this message can say which executor became unavailable and why,
but it cannot name a replacement, role reassignment, reinforcement or formation.
Those remain SwarmOS decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(UTC)


class ExecutorFault(BaseModel):
    agent_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="SIMULATED_EXECUTOR_FAILURE", min_length=1, max_length=240)
    ts: datetime = Field(default_factory=_now)


__all__ = ("ExecutorFault",)
