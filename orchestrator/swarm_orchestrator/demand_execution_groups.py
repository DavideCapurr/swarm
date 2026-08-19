"""Demand-aware admission for adaptive execution groups."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from swarm_core.execution_groups import ExecutionGroup, ExecutionGroupState
from swarm_core.messages import MissionTask
from swarm_core.objectives import demand_for_mission

from orchestrator.swarm_orchestrator.adaptive_execution_groups import (
    AdaptiveExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.execution_groups import ExecutionRolePlan

logger = logging.getLogger("swarm.orchestrator.demand_execution_groups")


@dataclass
class DemandAwareExecutionGroupOrchestrator(AdaptiveExecutionGroupOrchestrator):
    """Adaptive orchestration with a hard minimum-capacity admission gate."""

    def _feasible_capacity_for_plans(self, plans: list[ExecutionRolePlan]) -> int:
        reserved: set[str] = set()
        for plan in plans:
            probe = self._clone_mission(plan.mission)
            choice = self._select_group_candidate(
                probe,
                excluded_agent_ids=reserved,
            )
            if choice is not None:
                reserved.add(choice[0])
        return len(reserved)

    async def _form_and_dispatch_group(
        self,
        *,
        objective: MissionTask,
        plans: list[ExecutionRolePlan],
        anomaly_id: str | None,
        reinforces_group_id: str | None = None,
    ) -> ExecutionGroup:
        if reinforces_group_id is None:
            demand = demand_for_mission(objective)
            feasible = self._feasible_capacity_for_plans(plans)
            if feasible < demand.minimum_capacity:
                group = ExecutionGroup(
                    objective_mission_id=objective.id,
                    objective_kind=objective.kind,
                    anomaly_id=anomaly_id,
                    requested_members=len(plans),
                    state=ExecutionGroupState.FAILED,
                    failure_reason="BELOW_MINIMUM_CAPACITY",
                )
                self._execution_groups[group.id] = group
                await self._publish_group(group)
                logger.info(
                    "objective %s refused: feasible=%d minimum=%d desired=%d",
                    objective.id,
                    feasible,
                    demand.minimum_capacity,
                    demand.desired_capacity,
                )
                return group

        return await super()._form_and_dispatch_group(
            objective=objective,
            plans=plans,
            anomaly_id=anomaly_id,
            reinforces_group_id=reinforces_group_id,
        )


__all__ = ("DemandAwareExecutionGroupOrchestrator",)
