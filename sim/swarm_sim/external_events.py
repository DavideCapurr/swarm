"""Simulation-only external physical-capacity events.

These messages describe world facts, not SwarmOS responses. In particular,
``CapacityAvailable`` contains no executor identity, mission, role, group,
reinforcement instruction or geometry. The simulator may expose configured
reserve hardware when the fact arrives; SwarmOS then decides whether and how
that newly available capacity should be used.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import Bus

logger = logging.getLogger("sim.external_events")

CAPACITY_AVAILABLE_TOPIC = "swarm:sim:capacity-available"


def _now() -> datetime:
    return datetime.now(UTC)


class CapacityAvailable(BaseModel):
    """Fact that configured reserve physical capacity is now available."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ts: datetime = Field(default_factory=_now)


async def consume_capacity_availability(
    bus: Bus,
    reserve_adapters: Sequence[SimulatedAdapter],
) -> None:
    """Expose reserve simulator hardware; never decide an operational response."""

    async for _topic, payload in bus.subscribe(CAPACITY_AVAILABLE_TOPIC):
        try:
            CapacityAvailable.model_validate_json(payload)
        except Exception as exc:
            logger.warning("invalid simulator capacity event: %s", exc)
            continue

        activated = 0
        for adapter in reserve_adapters:
            if adapter.connected:
                continue
            await adapter.connect()
            activated += 1
        logger.info(
            "external simulator world fact: reserve capacity available (%d activated)",
            activated,
        )


__all__ = (
    "CAPACITY_AVAILABLE_TOPIC",
    "CapacityAvailable",
    "consume_capacity_availability",
)
