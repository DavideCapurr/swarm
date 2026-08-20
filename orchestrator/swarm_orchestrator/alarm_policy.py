"""Reusable alarm-to-objective policy.

An alarm is an external fact about the world.  This module is the SwarmOS
policy that converts that fact into mission demand.  Demo timelines must publish
the alarm; they must not publish the chosen aircraft, team size, swarm ids, or
reinforcement decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from swarm_core.messages import Anomaly, MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY, VERIFY


@dataclass(frozen=True)
class AlarmResponsePolicy:
    """Deterministic initial demand policy for a newly observed alarm."""

    cooperative_threshold: float = 0.80
    high_confidence_threshold: float = 0.93
    max_team_size: int = 3
    single_hover_s: float = 15.0
    cooperative_hover_s: float = 15.0

    def objective_for(self, alarm: Anomaly) -> MissionTask:
        priority = 80 + int(alarm.confidence * 20)
        if alarm.confidence < self.cooperative_threshold or self.max_team_size < 2:
            mission = VERIFY(
                geo=alarm.geo,
                hover_s=self.single_hover_s,
                priority=priority,
            )
            mission.params["alarm_id"] = alarm.id
            mission.params["demand_reason"] = "CONFIDENCE_SINGLE_EXECUTOR"
            return mission

        desired = 2
        if (
            alarm.confidence >= self.high_confidence_threshold
            and self.max_team_size >= 3
        ):
            desired = self.max_team_size

        # The objective may begin degraded and reconcile upward; this is what
        # makes reinforcement a consequence of capacity state instead of a
        # timeline command.
        minimum = max(1, desired - 1)
        mission = COOPERATIVE_VERIFY(
            geo=alarm.geo,
            team_size=desired,
            minimum_capacity=minimum,
            hover_s=self.cooperative_hover_s,
            priority=priority,
        )
        mission.params["alarm_id"] = alarm.id
        mission.params["demand_reason"] = (
            "HIGH_CONFIDENCE_MULTI_EXECUTOR"
            if desired >= 3
            else "ELEVATED_CONFIDENCE_MULTI_EXECUTOR"
        )
        return mission


__all__ = ("AlarmResponsePolicy",)
