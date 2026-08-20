"""Simulation-only external fault events.

Fault identity is a fact about the simulated world. It is deliberately separate
from recovery: this message can say which executor became unavailable and why,
but it cannot name a replacement, role reassignment, reinforcement or formation.
Those remain SwarmOS decisions.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from orchestrator.swarm_orchestrator.bus import Bus

EXECUTOR_FAULT_TOPIC = "swarm:sim:faults"
logger = logging.getLogger("sim.faults")


class FailureInjectable(Protocol):
    def inject_failure(self, reason: str) -> None: ...


def _now() -> datetime:
    return datetime.now(UTC)


class ExecutorFault(BaseModel):
    """Physical failure fact only; response fields are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="SIMULATED_EXECUTOR_FAILURE", min_length=1, max_length=240)
    ts: datetime = Field(default_factory=_now)


async def consume_executor_faults(
    bus: Bus,
    adapters: Mapping[str, FailureInjectable],
) -> None:
    """Apply external world faults to simulator executors, never recovery."""

    async for _topic, payload in bus.subscribe(EXECUTOR_FAULT_TOPIC):
        try:
            fault = ExecutorFault.model_validate_json(payload)
        except Exception as exc:
            logger.warning("invalid simulator fault payload: %s", exc)
            continue
        adapter = adapters.get(fault.agent_id)
        if adapter is None:
            logger.warning("simulator fault names unknown executor %s", fault.agent_id)
            continue
        adapter.inject_failure(fault.reason)
        logger.info("external simulator fault: %s (%s)", fault.agent_id, fault.reason)


__all__ = (
    "EXECUTOR_FAULT_TOPIC",
    "ExecutorFault",
    "consume_executor_faults",
)
