"""Adaptive execution-group orchestration.

This module strengthens the existing ExecutionGroupOrchestrator without moving
policy into demo code. It adds the missing bridge between objective demand and
already-committed capacity:

* executable child missions retain their parent objective's demand policy;
* group composition, reinforcement and replacement all use the same capacity
  planner and may consume safely-preemptible airborne capacity;
* every SwarmOS-owned commitment is tracked as a MissionTask, not just a BUSY
  bit, so donor priority and minimum capacity are available to policy;
* diversion provenance is carried into the receiving group;
* when capacity is removed from a COVER group, its remaining PATROL slices are
  recomputed from the new membership rather than leaving geometric holes;
* simultaneous shortfalls are reconciled in explicit objective-priority order.

The physical adapters remain thin executors. They never choose a role, donor,
replacement, reinforcement, or reconciliation order.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from orchestrator.swarm_orchestrator.capacity import (
    CapacitySource,
    choose_capacity,
    evaluate_capacity,
    objective_key,
)
from orchestrator.swarm_orchestrator.execution_groups import (
    _ObjectiveReinforcementRecord,
    ExecutionGroupOrchestrator,
    ExecutionRolePlan,
    ReinforcementObservation,
    RUNNING_GROUP_STATES,
)
from orchestrator.swarm_orchestrator.service import MIN_BATTERY_PCT
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.messages import Geo, MissionTask
from swarm_core.missions import PATROL, MissionKind
from swarm_core.objectives import demand_for_mission, stamp_objective_demand


_LOST_STATES = frozenset(
    {
        ExecutionGroupMemberState.FAILED,
        ExecutionGroupMemberState.REPLACED,
        ExecutionGroupMemberState.DIVERTED,
    }
)


@dataclass
class AdaptiveExecutionGroupOrchestrator(ExecutionGroupOrchestrator):
    """ExecutionGroupOrchestrator with continuous capacity reconciliation."""

    continuous_patrol_min_capacity: int = 0
    continuous_patrol_preemptible: bool = True
    _agent_missions: dict[str, MissionTask] = field(default_factory=dict)
    _reconcile_tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    def _cooperative_verify_plans(
        self, objective: MissionTask
    ) -> list[ExecutionRolePlan]:
        plans = super()._cooperative_verify_plans(objective)
        for plan in plans:
            stamp_objective_demand(plan.mission, objective)
        return plans

    def _cover_plans(self, objective: MissionTask) -> list[ExecutionRolePlan]:
        plans = super()._cover_plans(objective)
        for plan in plans:
            stamp_objective_demand(plan.mission, objective)
        return plans

    def _select_group_candidate(
        self,
        mission: MissionTask,
        *,
        excluded_agent_ids: set[str],
    ) -> tuple[str, float, dict[str, float]] | None:
        planned_preemptions = {
            agent_id
            for agent_id in excluded_agent_ids
            if agent_id in self._agent_missions
        }
        choice = choose_capacity(
            mission,
            self._snapshot_fleet(),
            active_missions=self._agent_missions,
            excluded_agent_ids=excluded_agent_ids,
            planned_preemptions=planned_preemptions,
            min_battery_pct=MIN_BATTERY_PCT,
        )
        if choice is None:
            return None

        if choice.source is CapacitySource.PREEMPTIBLE:
            mission.params["diverted_from_mission_id"] = (
                choice.diverted_from_mission_id
            )
            mission.params["diverted_from_objective_id"] = (
                choice.diverted_from_objective_id
            )
        return choice.agent_id, choice.score, choice.score_breakdown

    async def _form_and_dispatch_group(
        self,
        *,
        objective: MissionTask,
        plans: list[ExecutionRolePlan],
        anomaly_id: str | None,
        reinforces_group_id: str | None = None,
    ) -> ExecutionGroup:
        group = await super()._form_and_dispatch_group(
            objective=objective,
            plans=plans,
            anomaly_id=anomaly_id,
            reinforces_group_id=reinforces_group_id,
        )
        if not group.members:
            return group

        changed = False
        for index, member in enumerate(group.members):
            mission = self._agent_missions.get(member.agent_id)
            if mission is None or mission.id != member.mission_id:
                continue
            diverted_from = mission.params.get("diverted_from_mission_id")
            diverted_objective = mission.params.get("diverted_from_objective_id")
            if diverted_from is None and diverted_objective is None:
                continue
            group.members[index] = member.model_copy(
                update={
                    "diverted_from_mission_id": diverted_from,
                    "diverted_from_objective_id": diverted_objective,
                }
            )
            changed = True
        if changed:
            await self._publish_group(group)
        return group

    async def review_reinforcements(self) -> list[ExecutionGroup]:
        """Reconcile all active shortfalls in explicit priority order."""

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
                    self._reinforcement_records.pop(origin_id, None)
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

    def _observe_objective(
        self,
        origin: ExecutionGroup,
        record: _ObjectiveReinforcementRecord,
    ) -> ReinforcementObservation:
        groups = [origin] + [
            self._execution_groups[group_id]
            for group_id in record.reinforcement_group_ids
            if group_id in self._execution_groups
        ]
        committed = sum(
            1
            for group in groups
            for member in group.members
            if member.state not in _LOST_STATES
        )

        eligible = 0
        if record.unfilled_plans:
            probe = self._clone_mission(record.unfilled_plans[0].mission)
            capacity = evaluate_capacity(
                probe,
                self._snapshot_fleet(),
                active_missions=self._agent_missions,
                min_battery_pct=MIN_BATTERY_PCT,
            )
            eligible = len(capacity.all)

        return ReinforcementObservation(
            objective_kind=origin.objective_kind,
            objective_state=origin.state,
            requested_members=origin.requested_members,
            committed_members=committed,
            eligible_agents=eligible,
            reinforcements_dispatched=len(record.reinforcement_group_ids),
            max_reinforcements=self.max_reinforcements_per_objective,
        )

    async def _run_mission(
        self,
        agent_id: str,
        adapter: object,
        mission: MissionTask,
        *,
        is_verify: bool,
    ) -> None:
        """Preserve successor ownership when a mission is adaptively retasked."""

        current_task = asyncio.current_task()
        try:
            await super()._run_mission(
                agent_id,
                adapter,
                mission,
                is_verify=is_verify,
            )
        finally:
            successor = self._agent_tasks.get(agent_id)
            if (
                successor is not None
                and successor is not current_task
                and not successor.done()
            ):
                self._busy.add(agent_id)
                successor_mission = self._agent_missions.get(agent_id)
                if successor_mission is not None:
                    self._agent_mission_ids[agent_id] = successor_mission.id
                    if (
                        successor_mission.id in self._group_task_to_role
                        or successor_mission.kind == MissionKind.VERIFY.value
                    ):
                        self._verifying.add(agent_id)
                    else:
                        self._verifying.discard(agent_id)

    def _start_mission(
        self, agent_id: str, mission: MissionTask, *, is_verify: bool
    ) -> asyncio.Task[None]:
        if (
            mission.kind == MissionKind.PATROL.value
            and self.continuous_patrol
            and "parent_objective_id" not in mission.params
        ):
            fleet_size = max(1, len(self._snapshot_fleet()))
            minimum = max(0, min(self.continuous_patrol_min_capacity, fleet_size))
            mission.params.update(
                {
                    "parent_objective_id": "continuous-patrol",
                    "objective_minimum_capacity": minimum,
                    "objective_desired_capacity": fleet_size,
                    "objective_preemptible": self.continuous_patrol_preemptible,
                    "objective_acceptable_degradation": minimum < fleet_size,
                    "objective_preemption_policy": (
                        "higher_priority"
                        if self.continuous_patrol_preemptible
                        else "never"
                    ),
                }
            )

        prior = self._agent_missions.get(agent_id)
        diverted_from = mission.params.get("diverted_from_mission_id")
        if prior is not None and prior.id != mission.id:
            task = self._agent_tasks.get(agent_id)
            if task is not None and not task.done():
                task.cancel()
            if diverted_from == prior.id:
                self._record_diversion(agent_id, prior)

        self._agent_missions[agent_id] = mission
        task = super()._start_mission(agent_id, mission, is_verify=is_verify)
        self._attach_tracking_cleanup(agent_id, mission, task)
        return task

    def _attach_tracking_cleanup(
        self,
        agent_id: str,
        mission: MissionTask,
        task: asyncio.Task[None],
    ) -> None:
        def _cleanup(_: asyncio.Task[None]) -> None:
            current = self._agent_missions.get(agent_id)
            if current is not None and current.id == mission.id:
                self._agent_missions.pop(agent_id, None)

        task.add_done_callback(_cleanup)

    def _record_diversion(self, agent_id: str, donor: MissionTask) -> None:
        mapping = self._group_task_to_role.get(donor.id)
        if mapping is not None:
            group_id, _role = mapping
            group = self._execution_groups.get(group_id)
            if group is not None:
                for index, member in enumerate(group.members):
                    if member.mission_id != donor.id:
                        continue
                    group.members[index] = member.model_copy(
                        update={"state": ExecutionGroupMemberState.DIVERTED}
                    )
                    break
                group.state = ExecutionGroupState.DEGRADED
                self._schedule_reconcile(f"group:{group_id}")
            return

        if objective_key(donor) == "continuous-patrol":
            self._schedule_reconcile("continuous-patrol")

    def _schedule_reconcile(self, key: str) -> None:
        existing = self._reconcile_tasks.get(key)
        if existing is not None and not existing.done():
            existing.cancel()
        task = asyncio.create_task(self._delayed_reconcile(key))
        self._reconcile_tasks[key] = task
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _delayed_reconcile(self, key: str) -> None:
        await asyncio.sleep(0.02)
        if key.startswith("group:"):
            await self._recompute_cover_group(key.split(":", 1)[1])
        elif key == "continuous-patrol":
            await self._recompute_continuous_patrol()

    async def _recompute_continuous_patrol(self) -> None:
        active = sorted(
            (agent_id, mission)
            for agent_id, mission in self._agent_missions.items()
            if objective_key(mission) == "continuous-patrol"
            and mission.kind == MissionKind.PATROL.value
        )
        if not active:
            return
        desired = max(
            int(mission.params.get("objective_desired_capacity", len(active)))
            for _, mission in active
        )
        minimum = max(
            int(mission.params.get("objective_minimum_capacity", 0))
            for _, mission in active
        )
        n = len(active)
        for index, (agent_id, old) in enumerate(active):
            task = self._agent_tasks.get(agent_id)
            if task is not None and not task.done():
                task.cancel()
            replacement = PATROL(
                area=self._patrol_area(index, n),
                altitude_m=self.patrol_altitude_m,
                priority=old.priority,
            )
            replacement.params.update(
                {
                    "parent_objective_id": "continuous-patrol",
                    "objective_minimum_capacity": minimum,
                    "objective_desired_capacity": desired,
                    "objective_preemptible": self.continuous_patrol_preemptible,
                    "objective_acceptable_degradation": minimum < desired,
                    "objective_preemption_policy": (
                        "higher_priority"
                        if self.continuous_patrol_preemptible
                        else "never"
                    ),
                    "recomputed_from_capacity": n,
                }
            )
            self._agent_missions[agent_id] = replacement
            new_task = super()._start_mission(agent_id, replacement, is_verify=False)
            self._attach_tracking_cleanup(agent_id, replacement, new_task)

    async def _recompute_cover_group(self, group_id: str) -> None:
        group = self._execution_groups.get(group_id)
        record = self._reinforcement_records.get(group_id)
        if (
            group is None
            or record is None
            or record.objective.kind != MissionKind.COVER.value
            or group.state not in RUNNING_GROUP_STATES
        ):
            if group is not None:
                await self._publish_group(group)
            return

        active_members = sorted(
            (
                member
                for member in group.members
                if member.state not in _LOST_STATES
                and member.state is not ExecutionGroupMemberState.COMPLETED
            ),
            key=lambda member: member.agent_id,
        )
        if not active_members:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = "COVER_CAPACITY_EXHAUSTED"
            await self._publish_group(group)
            return

        objective = record.objective
        area = [Geo(**raw) for raw in objective.params.get("area", [])]
        current_capacity = len(active_members)
        templates: dict[str, MissionTask] = {}

        for index, member in enumerate(active_members):
            old_task = self._agent_tasks.get(member.agent_id)
            if old_task is not None and not old_task.done():
                old_task.cancel()

            slice_area = area[index::current_capacity] or area
            child = PATROL(
                area=slice_area,
                altitude_m=float(objective.params.get("altitude_m", 60.0)),
                priority=objective.priority,
            )
            role = f"COVERAGE_SLICE_{index + 1}"
            child.params.update(
                {
                    "execution_role": role,
                    "execution_group_id": group.id,
                    "slice_index": index,
                    "slice_count": current_capacity,
                    "recomputed_from_capacity": current_capacity,
                }
            )
            stamp_objective_demand(child, objective)

            old_mission_id = member.mission_id
            self._group_task_to_role.pop(old_mission_id, None)
            self._group_task_to_role[child.id] = (group.id, role)
            templates[role] = self._clone_mission(child)

            member_index = group.members.index(member)
            group.members[member_index] = member.model_copy(
                update={
                    "role": role,
                    "mission_id": child.id,
                    "state": ExecutionGroupMemberState.ASSIGNED,
                }
            )
            self._agent_missions[member.agent_id] = child
            new_task = super()._start_mission(member.agent_id, child, is_verify=True)
            self._attach_tracking_cleanup(member.agent_id, child, new_task)

        self._group_role_templates[group.id] = templates
        demand = demand_for_mission(objective)
        group.state = (
            ExecutionGroupState.ACTIVE
            if current_capacity >= demand.desired_capacity
            else ExecutionGroupState.DEGRADED
        )
        group.failure_reason = None

        missing = max(0, demand.desired_capacity - current_capacity)
        if missing:
            full_plans = super()._cover_plans(objective)
            for plan in full_plans:
                stamp_objective_demand(plan.mission, objective)
            record.unfilled_plans = full_plans[-missing:]
        else:
            record.unfilled_plans = []

        await self._publish_group(group)

    @staticmethod
    def _clone_mission(template: MissionTask) -> MissionTask:
        params = dict(template.params)
        params.pop("diverted_from_mission_id", None)
        params.pop("diverted_from_objective_id", None)
        return MissionTask(
            kind=template.kind,
            params=params,
            priority=template.priority,
            deadline=template.deadline,
        )


__all__ = ("AdaptiveExecutionGroupOrchestrator",)
