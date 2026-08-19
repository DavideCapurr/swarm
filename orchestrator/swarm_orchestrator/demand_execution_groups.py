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
from orchestrator.swarm_orchestrator.execution_groups import (
    RUNNING_GROUP_STATES,
    ExecutionRolePlan,
)

logger = logging.getLogger("swarm.orchestrator.demand_execution_groups")


@dataclass
class DemandAwareExecutionGroupOrchestrator(AdaptiveExecutionGroupOrchestrator):
    """Adaptive orchestration with hard admission and persistent demand truth.

    A running objective remains relevant even while it is temporarily at desired
    strength. Later preemption can make it under-strength, at which point SwarmOS
    needs the original objective contract to recompute the donor and create new
    reconciliation demand. Therefore satisfied records are retained until the
    originating group becomes terminal; they are not merely reinforcement queue
    entries.
    """

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

    async def review_reinforcements(self) -> list[ExecutionGroup]:
        """Reconcile shortfalls without forgetting satisfied live objectives.

        The base reinforcement queue can discard a record once no roles are
        missing. Demand-aware orchestration cannot do that: a later policy-owned
        diversion may create a new shortfall and COVER replanning needs the
        original objective geometry and minimum/desired contract.
        """

        dispatched: list[ExecutionGroup] = []
        async with self._group_lock:
            origin_ids = sorted(
                self._reinforcement_records,
                key=lambda origin_id: (
                    -self._reinforcement_records[origin_id].objective.priority,
                    origin_id,
                ),
            )
            for origin_id in origin_ids:
                record = self._reinforcement_records.get(origin_id)
                if record is None:
                    continue
                origin = self._execution_groups.get(origin_id)
                if origin is None or origin.state not in RUNNING_GROUP_STATES:
                    self._reinforcement_records.pop(origin_id, None)
                    continue
                if not record.unfilled_plans:
                    # Keep the live objective contract. A later diversion can
                    # populate a fresh shortfall during donor recomputation.
                    continue
                decision = self.reinforcement_policy(
                    self._observe_objective(origin, record)
                )
                if not decision.reinforce or decision.strength < 1:
                    continue
                dispatched.append(
                    await self._dispatch_reinforcement(origin, record, decision)
                )
        return dispatched


__all__ = ("DemandAwareExecutionGroupOrchestrator",)
