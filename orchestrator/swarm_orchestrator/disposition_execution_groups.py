"""Disposition-aware execution-group orchestration.

Composition decides *who* serves an objective. This layer decides *where* the
active roles should station once membership changes. The decision is published
as first-class SwarmOS truth. Physical retask is separately gated so a simulator
can prove execution without silently extending the MAVLink/SITL claim boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from swarm_core.disposition import (
    DispositionAssignment,
    DispositionDecision,
    compute_disposition,
)
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMember,
    ExecutionGroupMemberState,
)
from swarm_core.messages import Geo, MissionTask
from swarm_core.missions import MissionKind

from orchestrator.swarm_orchestrator.demand_execution_groups import (
    DemandAwareExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.execution_groups import (
    RUNNING_GROUP_STATES,
    ReinforcementDecision,
)

DISPOSITION_TOPIC = "swarm:dispositions"

_ACTIVE_MEMBER_STATES = frozenset(
    {
        ExecutionGroupMemberState.ASSIGNED,
        ExecutionGroupMemberState.ACTIVE,
    }
)


@dataclass
class DispositionExecutionGroupOrchestrator(DemandAwareExecutionGroupOrchestrator):
    """Derive objective station geometry from live SwarmOS-owned membership."""

    execute_disposition_retask: bool = False
    disposition_base_radius_m: float = 14.0
    disposition_radius_step_m: float = 8.0
    _disposition_revisions: dict[str, int] = field(default_factory=dict)
    _disposition_signatures: dict[
        str, tuple[tuple[str, str, str], ...]
    ] = field(default_factory=dict)

    async def _form_and_dispatch_group(
        self,
        *,
        objective: MissionTask,
        plans: list[Any],
        anomaly_id: str | None,
        reinforces_group_id: str | None = None,
    ) -> ExecutionGroup:
        group = await super()._form_and_dispatch_group(
            objective=objective,
            plans=plans,
            anomaly_id=anomaly_id,
            reinforces_group_id=reinforces_group_id,
        )
        if (
            reinforces_group_id is None
            and group.members
            and group.state in RUNNING_GROUP_STATES
        ):
            await self._reconcile_disposition(group.id, reason="COMPOSITION")
        return group

    async def _dispatch_reinforcement(
        self,
        origin: ExecutionGroup,
        record: Any,
        decision: ReinforcementDecision,
    ) -> ExecutionGroup:
        group = await super()._dispatch_reinforcement(origin, record, decision)
        if group.members and origin.state in RUNNING_GROUP_STATES:
            await self._reconcile_disposition(origin.id, reason="REINFORCEMENT")
        return group

    async def _replace_failed_member(
        self,
        group: ExecutionGroup,
        role: str,
        failed_index: int,
    ) -> None:
        await super()._replace_failed_member(group, role, failed_index)
        if group.state not in RUNNING_GROUP_STATES:
            return
        origin_id = group.reinforces_group_id or group.id
        await self._reconcile_disposition(origin_id, reason="REPLACEMENT")

    def _objective_groups(self, origin_id: str) -> list[ExecutionGroup]:
        origin = self._execution_groups.get(origin_id)
        if origin is None:
            return []
        groups = [origin]
        record = self._reinforcement_records.get(origin_id)
        if record is not None:
            groups.extend(
                self._execution_groups[group_id]
                for group_id in record.reinforcement_group_ids
                if group_id in self._execution_groups
            )
        return groups

    @staticmethod
    def _active_members(
        groups: list[ExecutionGroup],
    ) -> list[tuple[ExecutionGroup, int, ExecutionGroupMember]]:
        active: list[tuple[ExecutionGroup, int, ExecutionGroupMember]] = []
        for group in groups:
            if group.state not in RUNNING_GROUP_STATES:
                continue
            for index, member in enumerate(group.members):
                if member.state in _ACTIVE_MEMBER_STATES:
                    active.append((group, index, member))
        return active

    def _objective_center(self, origin_id: str) -> Geo | None:
        record = self._reinforcement_records.get(origin_id)
        if record is None:
            return None
        raw = record.objective.params.get("geo")
        if not isinstance(raw, dict):
            return None
        try:
            return Geo(**raw)
        except Exception:
            return None

    async def _reconcile_disposition(self, origin_id: str, *, reason: str) -> None:
        groups = self._objective_groups(origin_id)
        center = self._objective_center(origin_id)
        if not groups or center is None:
            return

        active = self._active_members(groups)
        if not active:
            return
        signature = tuple(
            (group.id, member.agent_id, member.role)
            for group, _index, member in active
        )
        if self._disposition_signatures.get(origin_id) == signature:
            return

        geometry = compute_disposition(
            center,
            [member.role for _group, _index, member in active],
            base_radius_m=self.disposition_base_radius_m,
            radius_step_m=self.disposition_radius_step_m,
        )
        revision = self._disposition_revisions.get(origin_id, 0) + 1
        self._disposition_revisions[origin_id] = revision
        self._disposition_signatures[origin_id] = signature

        assignments: list[DispositionAssignment] = []
        touched_groups: set[str] = set()

        for (group, member_index, member), slot in zip(
            active, geometry.slots, strict=True
        ):
            mission = self._agent_missions.get(member.agent_id)
            altitude_m = (
                float(mission.params.get("altitude_m", slot.geo.alt_m))
                if mission is not None
                else slot.geo.alt_m
            )
            target = slot.geo.model_copy(update={"alt_m": altitude_m})
            mission_id = member.mission_id

            if (
                self.execute_disposition_retask
                and mission is not None
                and mission.id == member.mission_id
                and mission.kind == MissionKind.VERIFY.value
            ):
                retask = self._clone_mission(mission)
                retask.params["geo"] = target.model_dump()
                retask.params["disposition_revision"] = revision
                retask.params["disposition_reason"] = reason

                self._group_task_to_role.pop(member.mission_id, None)
                self._group_task_to_role[retask.id] = (group.id, member.role)
                templates = self._group_role_templates.get(group.id)
                if templates is not None:
                    templates[member.role] = self._clone_mission(retask)

                group.members[member_index] = member.model_copy(
                    update={
                        "mission_id": retask.id,
                        "state": ExecutionGroupMemberState.ASSIGNED,
                    }
                )
                self._start_mission(member.agent_id, retask, is_verify=True)
                mission_id = retask.id
                touched_groups.add(group.id)

            assignments.append(
                DispositionAssignment(
                    group_id=group.id,
                    agent_id=member.agent_id,
                    role=member.role,
                    mission_id=mission_id,
                    geo=target,
                )
            )

        for group in groups:
            if group.id in touched_groups:
                await self._publish_group(group)

        frame = DispositionDecision(
            objective_mission_id=groups[0].objective_mission_id,
            revision=revision,
            reason=reason,
            center=center,
            active_members=len(assignments),
            radius_m=geometry.radius_m,
            assignments=assignments,
        )
        await self.bus.publish(DISPOSITION_TOPIC, frame.model_dump_json())


__all__ = (
    "DISPOSITION_TOPIC",
    "DispositionExecutionGroupOrchestrator",
)
