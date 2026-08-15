"""Central multi-agent execution groups.

The parent objective never reaches a physical agent. SwarmOS decomposes it into
child missions, centrally selects one physical executor per role, and tracks the
logical group as auditable truth. Member agents never negotiate roles or command
peers.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from swarm_core.allocator import build_bid
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMember,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.fsm import is_available
from swarm_core.messages import Anomaly, Award, Geo, MissionProgress, MissionTask
from swarm_core.missions import (
    COOPERATIVE_VERIFY,
    COOPERATIVE_VERIFY_KIND,
    PATROL,
    VERIFY,
    MissionKind,
)
from swarm_core.runtime_events import MissionRuntimeEvent

from orchestrator.swarm_orchestrator.service import MIN_BATTERY_PCT, Orchestrator

logger = logging.getLogger("swarm.orchestrator.execution_groups")

EXECUTION_GROUP_TOPIC = "swarm:execution-groups"
MISSION_OBJECTIVE_TOPIC = "swarm:missions:objectives"


@dataclass(frozen=True)
class ExecutionRolePlan:
    role: str
    mission: MissionTask


@dataclass
class ExecutionGroupOrchestrator(Orchestrator):
    """Orchestrator with SwarmOS-owned one-objective/many-agent execution."""

    cooperative_verify_enabled: bool = False
    cooperative_verify_min_confidence: float = 0.90
    cooperative_verify_team_size: int = 3
    cooperative_verify_hover_s: float = 15.0
    max_group_replacements_per_role: int = 1

    _execution_groups: dict[str, ExecutionGroup] = field(default_factory=dict)
    _group_role_templates: dict[str, dict[str, MissionTask]] = field(
        default_factory=dict
    )
    _group_task_to_role: dict[str, tuple[str, str]] = field(default_factory=dict)
    _group_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def run(self) -> None:
        await asyncio.gather(
            super().run(),
            self._execution_group_progress_loop(),
            self._objective_loop(),
        )

    @property
    def execution_groups(self) -> dict[str, ExecutionGroup]:
        return self._execution_groups

    def group_role_for_mission(self, mission_id: str) -> str | None:
        mapping = self._group_task_to_role.get(mission_id)
        return mapping[1] if mapping is not None else None

    async def _anomaly_loop(self) -> None:
        """Choose single-agent or cooperative verification centrally."""

        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                anomaly = Anomaly.model_validate_json(payload)
            except Exception as exc:
                logger.warning("invalid anomaly payload: %s", exc)
                continue

            logger.info(
                "anomaly received: %s @ (%.5f, %.5f)",
                anomaly.kind.value,
                anomaly.geo.lat,
                anomaly.geo.lon,
            )
            if self._should_cooperative_verify(anomaly):
                parent = COOPERATIVE_VERIFY(
                    geo=anomaly.geo,
                    team_size=self.cooperative_verify_team_size,
                    hover_s=self.cooperative_verify_hover_s,
                    priority=80 + int(anomaly.confidence * 20),
                )
                await self.dispatch_execution_group(parent, anomaly_id=anomaly.id)
                continue

            mission = VERIFY(
                geo=anomaly.geo,
                hover_s=self.verify_hover_s,
                priority=80 + int(anomaly.confidence * 20),
            )
            await self._auction_and_dispatch(mission, anomaly_id=anomaly.id)

    def _should_cooperative_verify(self, anomaly: Anomaly) -> bool:
        return (
            self.cooperative_verify_enabled
            and self.cooperative_verify_team_size > 1
            and anomaly.confidence >= self.cooperative_verify_min_confidence
        )

    async def _objective_loop(self) -> None:
        """Accept explicit orchestration-only group objectives from the bus."""

        async for _topic, payload in self.bus.subscribe(MISSION_OBJECTIVE_TOPIC):
            try:
                objective = MissionTask.model_validate_json(payload)
                await self.dispatch_execution_group(objective)
            except Exception as exc:
                logger.warning("rejected execution-group objective: %s", exc)

    async def dispatch_execution_group(
        self,
        objective: MissionTask,
        *,
        anomaly_id: str | None = None,
    ) -> ExecutionGroup:
        """Plan and dispatch a group objective without sending the parent to agents."""

        if objective.kind == COOPERATIVE_VERIFY_KIND:
            plans = self._cooperative_verify_plans(objective)
        elif objective.kind == MissionKind.COVER.value:
            plans = self._cover_plans(objective)
        else:
            raise ValueError(
                "execution groups require an orchestration-only COOPERATIVE_VERIFY "
                "or COVER objective"
            )
        return await self._form_and_dispatch_group(
            objective=objective,
            plans=plans,
            anomaly_id=anomaly_id,
        )

    def _cooperative_verify_plans(
        self, objective: MissionTask
    ) -> list[ExecutionRolePlan]:
        geo = Geo(**objective.params["geo"])
        team_size = max(2, int(objective.params.get("team_size", 3)))
        hover_s = float(
            objective.params.get("hover_s", self.cooperative_verify_hover_s)
        )
        base_altitude_m = float(objective.params.get("base_altitude_m", 40.0))
        altitude_step_m = float(objective.params.get("altitude_step_m", 15.0))
        configured_roles = list(objective.params.get("roles", []))
        default_roles = ["PRIMARY_OBSERVER", "SECONDARY_OBSERVER", "OVERWATCH"]

        plans: list[ExecutionRolePlan] = []
        for idx in range(team_size):
            role = (
                configured_roles[idx]
                if idx < len(configured_roles)
                else default_roles[idx]
                if idx < len(default_roles)
                else f"OBSERVER_{idx + 1}"
            )
            child = VERIFY(
                geo=geo,
                hover_s=hover_s,
                altitude_m=base_altitude_m + altitude_step_m * idx,
                priority=objective.priority,
                deadline_s=None,
            )
            child.params["execution_role"] = role
            child.params["parent_objective_id"] = objective.id
            plans.append(ExecutionRolePlan(role=role, mission=child))
        return plans

    def _cover_plans(self, objective: MissionTask) -> list[ExecutionRolePlan]:
        area = [Geo(**raw) for raw in objective.params.get("area", [])]
        fleet_size = int(objective.params.get("fleet_size", 0))
        if fleet_size < 1:
            raise ValueError("COVER fleet_size must be >= 1")
        if not area:
            raise ValueError("COVER requires a non-empty area")

        plans: list[ExecutionRolePlan] = []
        for idx in range(fleet_size):
            slice_area = area[idx::fleet_size] or area
            child = PATROL(
                area=slice_area,
                altitude_m=float(objective.params.get("altitude_m", 60.0)),
                priority=objective.priority,
            )
            role = f"COVERAGE_SLICE_{idx + 1}"
            child.params["execution_role"] = role
            child.params["parent_objective_id"] = objective.id
            child.params["slice_index"] = idx
            child.params["slice_count"] = fleet_size
            plans.append(ExecutionRolePlan(role=role, mission=child))
        return plans

    async def _form_and_dispatch_group(
        self,
        *,
        objective: MissionTask,
        plans: list[ExecutionRolePlan],
        anomaly_id: str | None,
    ) -> ExecutionGroup:
        if not plans:
            raise ValueError("execution group requires at least one role")

        group = ExecutionGroup(
            objective_mission_id=objective.id,
            objective_kind=objective.kind,
            anomaly_id=anomaly_id,
            requested_members=len(plans),
        )
        assignments: list[
            tuple[ExecutionRolePlan, str, float, dict[str, float]]
        ] = []
        reserved: set[str] = set()

        for plan in plans:
            choice = self._select_group_candidate(
                plan.mission, excluded_agent_ids=reserved
            )
            if choice is None:
                group.state = ExecutionGroupState.FAILED
                group.failure_reason = "INSUFFICIENT_ELIGIBLE_CAPACITY"
                self._execution_groups[group.id] = group
                await self._publish_group(group)
                return group
            agent_id, score, breakdown = choice
            reserved.add(agent_id)
            assignments.append((plan, agent_id, score, breakdown))

        members: list[ExecutionGroupMember] = []
        templates: dict[str, MissionTask] = {}
        for plan, agent_id, score, breakdown in assignments:
            child = plan.mission
            child.params["execution_group_id"] = group.id
            members.append(
                ExecutionGroupMember(
                    agent_id=agent_id,
                    role=plan.role,
                    mission_id=child.id,
                    score=score,
                    score_breakdown=breakdown,
                )
            )
            templates[plan.role] = self._clone_mission(child)
            self._group_task_to_role[child.id] = (group.id, plan.role)

        group.members = members
        group.state = ExecutionGroupState.ACTIVE
        self._execution_groups[group.id] = group
        self._group_role_templates[group.id] = templates

        for plan, agent_id, _score, _breakdown in assignments:
            self._busy.add(agent_id)
            self._agent_mission_ids[agent_id] = plan.mission.id

        try:
            await self._publish_group(group)
        except Exception:
            for plan, agent_id, _score, _breakdown in assignments:
                self._busy.discard(agent_id)
                if self._agent_mission_ids.get(agent_id) == plan.mission.id:
                    self._agent_mission_ids.pop(agent_id, None)
            raise

        for (plan, agent_id, score, _breakdown), member in zip(
            assignments, members, strict=True
        ):
            await self._publish_group_award(plan.mission, agent_id, score)
            self._start_mission(agent_id, plan.mission, is_verify=True)
            logger.info(
                "execution group %s role %s -> %s mission=%s",
                group.id,
                member.role,
                agent_id,
                member.mission_id,
            )
        return group

    def _select_group_candidate(
        self,
        mission: MissionTask,
        *,
        excluded_agent_ids: set[str],
    ) -> tuple[str, float, dict[str, float]] | None:
        ranked: list[tuple[str, float, dict[str, float]]] = []
        for state in self._snapshot_fleet():
            if state.agent_id in excluded_agent_ids:
                continue
            if state.agent_id in self._busy or state.current_mission_id is not None:
                continue
            if state.battery_pct < MIN_BATTERY_PCT:
                continue
            if not is_available(state.fsm_state):
                continue
            bid = build_bid(mission, state)
            ranked.append((state.agent_id, bid.score, dict(bid.reason)))
        if not ranked:
            return None
        ranked.sort(key=lambda row: (-row[1], row[0]))
        return ranked[0]

    async def _publish_group_award(
        self, mission: MissionTask, agent_id: str, score: float
    ) -> None:
        mission.assigned_agent = agent_id
        award = Award(mission_id=mission.id, winner_agent_id=agent_id, score=score)
        await self.bus.publish("swarm:missions:award", award.model_dump_json())

    async def _run_mission(
        self,
        agent_id: str,
        adapter: object,
        mission: MissionTask,
        *,
        is_verify: bool,
    ) -> None:
        """Run group children with explicit terminal failure truth."""

        if mission.id not in self._group_task_to_role:
            await super()._run_mission(
                agent_id, adapter, mission, is_verify=is_verify
            )
            return

        terminal_seen = False
        try:
            async for progress in adapter.execute_mission(mission):  # type: ignore[attr-defined]
                if not is_verify:
                    continue
                await self._publish_group_child_progress(
                    agent_id=agent_id,
                    adapter=adapter,
                    progress=progress,
                )
                if progress.phase in ("DONE", "FAILED"):
                    terminal_seen = True
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("group mission %s failed: %s", mission.id, exc)
            if is_verify and not terminal_seen:
                failure = MissionProgress(
                    mission_id=mission.id,
                    phase="FAILED",
                    progress_pct=0.0,
                    error=f"{type(exc).__name__}: {exc}"[:240],
                )
                await self._publish_group_child_progress(
                    agent_id=agent_id,
                    adapter=adapter,
                    progress=failure,
                )
        finally:
            self._busy.discard(agent_id)
            self._verifying.discard(agent_id)
            if self._agent_tasks.get(agent_id) is asyncio.current_task():
                self._agent_tasks.pop(agent_id, None)
                self._agent_mission_ids.pop(agent_id, None)

    def _enrich_group_progress(
        self, progress: MissionProgress, agent_id: str
    ) -> MissionProgress:
        mapping = self._group_task_to_role.get(progress.mission_id)
        if mapping is None:
            return progress.model_copy(update={"agent_id": agent_id})
        group_id, role = mapping
        group = self._execution_groups.get(group_id)
        return progress.model_copy(
            update={
                "agent_id": agent_id,
                "execution_group_id": group_id,
                "execution_role": role,
                "parent_objective_id": (
                    group.objective_mission_id if group is not None else None
                ),
            }
        )

    async def _publish_group_child_progress(
        self,
        *,
        agent_id: str,
        adapter: object,
        progress: MissionProgress,
    ) -> None:
        progress = self._enrich_group_progress(progress, agent_id)
        progress = self._enrich_group_progress(progress, agent_id)
        progress = self._enrich_group_progress(progress, agent_id)
        progress = self._enrich_group_progress(progress, agent_id)
        progress = self._enrich_group_progress(progress, agent_id)
        await self.bus.publish(
            f"swarm:missions:progress:{progress.mission_id}",
            progress.model_dump_json(),
        )
        evidence = None
        evidence_for_phase = getattr(adapter, "runtime_evidence_for_phase", None)
        if callable(evidence_for_phase):
            try:
                evidence = evidence_for_phase(progress.phase)
            except Exception:
                logger.exception(
                    "runtime evidence projection failed for %s %s",
                    agent_id,
                    progress.phase,
                )
        runtime_event = MissionRuntimeEvent(
            mission_id=progress.mission_id,
            agent_id=agent_id,
            phase=progress.phase,
            progress_pct=progress.progress_pct,
            evidence=evidence,
            error=progress.error,
            ts=progress.ts,
        )
        await self.bus.publish(
            "swarm:missions:runtime", runtime_event.model_dump_json()
        )

    async def _execution_group_progress_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:missions:progress:*"):
            try:
                progress = MissionProgress.model_validate_json(payload)
            except Exception:
                continue
            mapping = self._group_task_to_role.get(progress.mission_id)
            if mapping is None:
                continue
            async with self._group_lock:
                await self._apply_group_progress(progress, *mapping)

    async def _apply_group_progress(
        self,
        progress: MissionProgress,
        group_id: str,
        role: str,
    ) -> None:
        group = self._execution_groups.get(group_id)
        if group is None or group.state in {
            ExecutionGroupState.COMPLETED,
            ExecutionGroupState.FAILED,
        }:
            return

        member_index = next(
            (
                idx
                for idx, member in enumerate(group.members)
                if member.mission_id == progress.mission_id
            ),
            None,
        )
        if member_index is None:
            return
        member = group.members[member_index]

        if progress.phase == "DONE":
            member = member.model_copy(
                update={"state": ExecutionGroupMemberState.COMPLETED}
            )
            group.members[member_index] = member
            if self._all_group_roles_completed(group):
                group.state = ExecutionGroupState.COMPLETED
                group.failure_reason = None
            else:
                group.state = ExecutionGroupState.ACTIVE
            await self._publish_group(group)
            return

        if progress.phase == "FAILED":
            if member.state is ExecutionGroupMemberState.REPLACED:
                return
            member = member.model_copy(
                update={"state": ExecutionGroupMemberState.FAILED}
            )
            group.members[member_index] = member
            group.state = ExecutionGroupState.DEGRADED
            await self._publish_group(group)
            await self._replace_failed_member(group, role, member_index)
            return

        if member.state is not ExecutionGroupMemberState.ACTIVE:
            group.members[member_index] = member.model_copy(
                update={"state": ExecutionGroupMemberState.ACTIVE}
            )
            group.state = ExecutionGroupState.ACTIVE
            await self._publish_group(group)

    async def _replace_failed_member(
        self,
        group: ExecutionGroup,
        role: str,
        failed_index: int,
    ) -> None:
        prior_for_role = [member for member in group.members if member.role == role]
        replacements_used = max(0, len(prior_for_role) - 1)
        if replacements_used >= self.max_group_replacements_per_role:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = f"ROLE_FAILED:{role}:REPLACEMENT_LIMIT"
            await self._publish_group(group)
            return

        template = self._group_role_templates[group.id][role]
        replacement_mission = self._clone_mission(template)
        replacement_mission.params["execution_group_id"] = group.id
        used_agents = {member.agent_id for member in group.members}
        choice = self._select_group_candidate(
            replacement_mission,
            excluded_agent_ids=used_agents,
        )
        if choice is None:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = f"ROLE_FAILED:{role}:NO_REPLACEMENT"
            await self._publish_group(group)
            return

        agent_id, score, breakdown = choice
        failed = group.members[failed_index]
        group.members[failed_index] = failed.model_copy(
            update={"state": ExecutionGroupMemberState.REPLACED}
        )
        replacement = ExecutionGroupMember(
            agent_id=agent_id,
            role=role,
            mission_id=replacement_mission.id,
            state=ExecutionGroupMemberState.ASSIGNED,
            score=score,
            score_breakdown=breakdown,
            replaces_agent_id=failed.agent_id,
        )
        group.members.append(replacement)
        group.state = ExecutionGroupState.DEGRADED
        group.failure_reason = None
        self._group_task_to_role[replacement_mission.id] = (group.id, role)
        await self._publish_group(group)
        await self._publish_group_award(replacement_mission, agent_id, score)
        self._start_mission(agent_id, replacement_mission, is_verify=True)
        logger.info(
            "execution group %s replaced %s with %s for role %s",
            group.id,
            failed.agent_id,
            agent_id,
            role,
        )

    def _all_group_roles_completed(self, group: ExecutionGroup) -> bool:
        roles = self._group_role_templates.get(group.id, {})
        return bool(roles) and all(
            any(
                member.role == role
                and member.state is ExecutionGroupMemberState.COMPLETED
                for member in group.members
            )
            for role in roles
        )

    async def _publish_group(self, group: ExecutionGroup) -> None:
        group.ts = datetime.now(UTC)
        self._execution_groups[group.id] = group
        await self.bus.publish(EXECUTION_GROUP_TOPIC, group.model_dump_json())

    @staticmethod
    def _clone_mission(template: MissionTask) -> MissionTask:
        return MissionTask(
            kind=template.kind,
            params=dict(template.params),
            priority=template.priority,
            deadline=template.deadline,
        )


__all__ = (
    "EXECUTION_GROUP_TOPIC",
    "MISSION_OBJECTIVE_TOPIC",
    "ExecutionGroupOrchestrator",
    "ExecutionRolePlan",
)
