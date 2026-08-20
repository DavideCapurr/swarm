"""Bus-backed fleet runtimes driven by the reusable alarm response policy.

These classes are opt-in deployment entrypoints. The external stimulus is an
``Anomaly``; SwarmOS derives objective kind, demand, priority and composition.
They deliberately do not replace the legacy bus runtime by default so existing
validated deployments keep their current behaviour unless policy mode is
explicitly enabled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from swarm_core.messages import Anomaly
from swarm_core.missions import COOPERATIVE_VERIFY_KIND

from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator
from orchestrator.swarm_orchestrator.presence_bus import (
    PresenceResponseBusFleetOrchestrator,
)

logger = logging.getLogger("swarm.orchestrator.policy_bus")


@dataclass
class AlarmPolicyBusFleetOrchestrator(BusFleetOrchestrator):
    """Real bus-backed fleet where alarm truth is the response input."""

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


@dataclass
class AlarmPolicyPresenceResponseBusFleetOrchestrator(
    PresenceResponseBusFleetOrchestrator
):
    """Alarm-policy runtime retaining bounded presence-response provenance."""

    alarm_policy: AlarmResponsePolicy = field(default_factory=AlarmResponsePolicy)

    async def _anomaly_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                alarm = Anomaly.model_validate_json(payload)
            except Exception as exc:
                logger.warning("invalid anomaly payload: %s", exc)
                continue

            self._remember_anomaly(alarm)
            objective = self.alarm_policy.objective_for(alarm)
            logger.info(
                "alarm %s c=%.2f -> objective %s priority=%d with presence provenance",
                alarm.id,
                alarm.confidence,
                objective.kind,
                objective.priority,
            )
            if objective.kind == COOPERATIVE_VERIFY_KIND:
                await self.dispatch_execution_group(objective, anomaly_id=alarm.id)
                continue

            self._mission_anomalies[objective.id] = alarm
            await self._auction_and_dispatch(objective, anomaly_id=alarm.id)
            if objective.assigned_agent is None:
                self._mission_anomalies.pop(objective.id, None)


__all__ = (
    "AlarmPolicyBusFleetOrchestrator",
    "AlarmPolicyPresenceResponseBusFleetOrchestrator",
)
