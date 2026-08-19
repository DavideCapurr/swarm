"""Alarm-driven adaptive SwarmOS orchestrator.

The scenario publishes an ``Anomaly``.  SwarmOS derives the response objective,
capacity demand, composition and any preemption/reinforcement.  No scenario code
names an executor or a swarm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from swarm_core.messages import Anomaly
from swarm_core.missions import COOPERATIVE_VERIFY_KIND

from orchestrator.swarm_orchestrator.adaptive_execution_groups import (
    AdaptiveExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy

logger = logging.getLogger("swarm.orchestrator.alarm_driven")


@dataclass
class AlarmDrivenExecutionGroupOrchestrator(AdaptiveExecutionGroupOrchestrator):
    """Adaptive orchestrator whose public stimulus is world-state alarm truth."""

    alarm_policy: AlarmResponsePolicy = field(default_factory=AlarmResponsePolicy)

    async def _anomaly_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                alarm = Anomaly.model_validate_json(payload)
            except Exception as exc:
                logger.warning("invalid anomaly payload: %s", exc)
                continue

            objective = self.alarm_policy.objective_for(alarm)
            logger.info(
                "alarm %s c=%.2f -> objective %s priority=%d",
                alarm.id,
                alarm.confidence,
                objective.kind,
                objective.priority,
            )
            if objective.kind == COOPERATIVE_VERIFY_KIND:
                await self.dispatch_execution_group(objective, anomaly_id=alarm.id)
            else:
                await self._auction_and_dispatch(objective, anomaly_id=alarm.id)


__all__ = ("AlarmDrivenExecutionGroupOrchestrator",)
