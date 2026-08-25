"""Central multi-agent execution groups.

The parent objective never reaches a physical agent. SwarmOS decomposes it into
child missions, centrally selects one physical executor per role, and tracks the
logical group as auditable truth. Member agents never negotiate roles or command
peers.

Composition is partial-strength: SwarmOS dispatches the roles it can fill and
refuses only when no role can be filled. When capacity returns, SwarmOS may
reinforce a running objective with a *second* group — the swarm is the unit of
command, so added strength is another unit, not extra members bolted onto the
first. Whether an objective needs reinforcing is a policy decision
(`shortfall_reinforcement_policy`), kept separate from the compose/dispatch/
publish mechanism so it can be replaced without touching dispatch.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from swarm_core.allocations import (
    AllocationEligibleUnit,
    AllocationExcludedUnit,
    AllocationExclusionReason,
    AllocationScoreBreakdown,
)
from swarm_core.allocator import build_bid, has_capabilities, required_capabilities
from swarm_core.authority import (
    CandidateAssessment,
    MissionAuthorityGrant,
    MissionAuthorityVerdict,
    MissionDecision,
    MissionDecisionKind,
    MissionDecisionReview,
    MissionHardConstraints,
    MissionReviewAction,
    ObjectiveStateFrame,
    SelectedAssignment,
    evaluate_mission_authority,
    evaluate_mission_hard_constraints,
)
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMember,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.fsm import is_available
from swarm_core.messages import (
    Anomaly,
    Award,
    FleetState,
    Geo,
    MissionProgress,
    MissionTask,
    ObjectiveApprovalCommand,
    ObjectiveStatus,
    SensorKind,
)
from swarm_core.missions import (
    COOPERATIVE_VERIFY,
    COOPERATIVE_VERIFY_KIND,
    PATROL,
    VERIFY,
    MissionKind,
)
from swarm_core.runtime_events import MissionRuntimeEvent

from orchestrator.swarm_orchestrator.service import (
    MIN_BATTERY_PCT,
    Orchestrator,
    verification_capabilities,
    verification_sensors,
)

logger = logging.getLogger("swarm.orchestrator.execution_groups")

EXECUTION_GROUP_TOPIC = "swarm:execution-groups"
MISSION_OBJECTIVE_TOPIC = "swarm:missions:objectives"
OBJECTIVE_APPROVAL_TOPIC = "swarm:missions:approvals"
MISSION_AUTHORITY_GRANT_TOPIC = "swarm:mission-authority-grants"
MISSION_DECISION_TOPIC = "swarm:mission-decisions"
MISSION_DECISION_REVIEW_TOPIC = "swarm:mission-decision-reviews"
MISSION_OBJECTIVE_STATE_TOPIC = "swarm:mission-objective-states"

RUNNING_GROUP_STATES = frozenset(
    {ExecutionGroupState.ACTIVE, ExecutionGroupState.DEGRADED}
)
_LOST_MEMBER_STATES = frozenset(
    {ExecutionGroupMemberState.FAILED, ExecutionGroupMemberState.REPLACED}
)


@dataclass(frozen=True)
class ExecutionRolePlan:
    role: str
    mission: MissionTask


def _role_requirements(objective: MissionTask, role: str) -> list[str]:
    """Resolve role-specific requirements, falling back to objective-wide ones."""

    configured = objective.params.get("role_requirements", {})
    if not isinstance(configured, dict):
        raise ValueError("role_requirements must be a role-to-capabilities mapping")
    raw = configured.get(role, objective.params.get("required_capabilities", []))
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise ValueError(f"role_requirements[{role!r}] must be a list of strings")
    return sorted(set(raw))


@dataclass(frozen=True)
class ReinforcementObservation:
    """The complete input to the reinforcement judgement."""

    objective_kind: str
    objective_state: ExecutionGroupState
    requested_members: int
    committed_members: int
    eligible_agents: int
    reinforcements_dispatched: int
    max_reinforcements: int


@dataclass(frozen=True)
class ReinforcementDecision:
    """The complete output of the reinforcement judgement."""

    reinforce: bool
    strength: int
    reason: str


ReinforcementPolicy = Callable[[ReinforcementObservation], ReinforcementDecision]
HardConstraintProvider = Callable[[], MissionHardConstraints | None]


def shortfall_reinforcement_policy(
    observation: ReinforcementObservation,
) -> ReinforcementDecision:
    if observation.objective_state not in RUNNING_GROUP_STATES:
        return ReinforcementDecision(False, 0, "GROUP_NOT_RUNNING")
    if observation.reinforcements_dispatched >= observation.max_reinforcements:
        return ReinforcementDecision(False, 0, "REINFORCEMENT_LIMIT")
    shortfall = observation.requested_members - observation.committed_members
    if shortfall <= 0:
        return ReinforcementDecision(False, 0, "AT_REQUESTED_STRENGTH")
    if observation.eligible_agents < 1:
        return ReinforcementDecision(False, 0, "NO_ELIGIBLE_CAPACITY")
    return ReinforcementDecision(
        True, min(shortfall, observation.eligible_agents), "STRENGTH_SHORTFALL"
    )


@dataclass
class _ObjectiveReinforcementRecord:
    objective: MissionTask
    anomaly_id: str | None
    unfilled_plans: list[ExecutionRolePlan]
    reinforcement_group_ids: list[str] = field(default_factory=list)


@dataclass
class ExecutionGroupOrchestrator(Orchestrator):
    """Orchestrator with SwarmOS-owned one-objective/many-agent execution."""

    cooperative_verify_enabled: bool = False
    cooperative_verify_min_confidence: float = 0.90
    cooperative_verify_team_size: int = 3
    cooperative_verify_hover_s: float = 15.0
    max_group_replacements_per_role: int = 1
    max_reinforcements_per_objective: int = 1
    reinforcement_review_period_s: float = 2.0
    reinforcement_policy: ReinforcementPolicy = shortfall_reinforcement_policy
    hard_constraint_provider: HardConstraintProvider | None = None

    _execution_groups: dict[str, ExecutionGroup] = field(default_factory=dict)
    _group_role_templates: dict[str, dict[str, MissionTask]] = field(
        default_factory=dict
    )
    _group_missions: dict[str, MissionTask] = field(default_factory=dict)
    _group_task_to_role: dict[str, tuple[str, str]] = field(default_factory=dict)
    _reinforcement_records: dict[str, _ObjectiveReinforcementRecord] = field(
        default_factory=dict
    )
    _objectives: dict[str, MissionTask] = field(default_factory=dict)
    _pending_proposals: dict[str, str] = field(default_factory=dict)
    _proposal_snapshots: dict[str, str] = field(default_factory=dict)
    _authority_grants: dict[tuple[str, int], MissionAuthorityGrant] = field(
        default_factory=dict
    )
    _latest_grant_revision: dict[str, int] = field(default_factory=dict)
    _mission_decisions: dict[str, MissionDecision] = field(default_factory=dict)
    _decision_reviews: dict[str, MissionDecisionReview] = field(default_factory=dict)
    _decision_groups: dict[str, str] = field(default_factory=dict)
    _objective_decisions: dict[str, str] = field(default_factory=dict)
    _approved_decisions: dict[str, str] = field(default_factory=dict)
    _group_candidate_assessments: dict[str, list[CandidateAssessment]] = field(
        default_factory=dict
    )
    _group_diversions: dict[str, dict[str, str | None]] = field(
        default_factory=dict
    )
    _group_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def run(self) -> None:
        await asyncio.gather(
            super().run(),
            self._execution_group_progress_loop(),
            self._objective_loop(),
            self._objective_approval_loop(),
            self._authority_grant_loop(),
            self._reinforcement_loop(),
        )

    @property
    def execution_groups(self) -> dict[str, ExecutionGroup]:
        return self._execution_groups

    @property
    def objectives(self) -> dict[str, MissionTask]:
        return self._objectives

    @property
    def mission_decisions(self) -> dict[str, MissionDecision]:
        return self._mission_decisions

    @property
    def authority_grants(self) -> dict[tuple[str, int], MissionAuthorityGrant]:
        return self._authority_grants

    def register_authority_grant(self, grant: MissionAuthorityGrant) -> None:
        key = (grant.grant_id, grant.revision)
        existing = self._authority_grants.get(key)
        if existing is not None and existing != grant:
            raise ValueError("authority grant revision is immutable")
        self._authority_grants[key] = grant
        self._latest_grant_revision[grant.grant_id] = max(
            grant.revision,
            self._latest_grant_revision.get(grant.grant_id, 0),
        )

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
            sensors = verification_sensors(anomaly)
            requirements = verification_capabilities(anomaly)
            if self._should_cooperative_verify(anomaly):
                parent = COOPERATIVE_VERIFY(
                    geo=anomaly.geo,
                    team_size=self.cooperative_verify_team_size,
                    sensors=sensors,
                    hover_s=self.cooperative_verify_hover_s,
                    priority=80 + int(anomaly.confidence * 20),
                    required_capabilities=requirements,
                )
                await self.dispatch_execution_group(parent, anomaly_id=anomaly.id)
                continue

            mission = VERIFY(
                geo=anomaly.geo,
                sensors=sensors,
                hover_s=self.verify_hover_s,
                priority=80 + int(anomaly.confidence * 20),
                required_capabilities=requirements,
            )
            await self._auction_and_dispatch(mission, anomaly_id=anomaly.id)

    async def _auction_and_dispatch(
        self,
        mission: MissionTask,
        *,
        anomaly_id: str | None = None,
    ) -> None:
        """Run single-executor work through the same authority/decision pipeline."""

        forced_assignments: dict[str, str] | None = None
        diverted_from_by_agent: dict[str, str | None] | None = None
        if not self._eligible_fleet(excluded_agent_ids=set(), mission=mission):
            victim = (
                self._nearest_airborne(self._snapshot_fleet(), mission)
                if self.continuous_patrol
                else None
            )
            if victim is not None:
                forced_assignments = {"EXECUTOR": victim}
                diverted_from_by_agent = {
                    victim: self._agent_mission_ids.get(victim)
                }

        proposal = await self.dispatch_execution_group(
            mission,
            anomaly_id=anomaly_id,
            plans=[
                ExecutionRolePlan(
                    role="EXECUTOR", mission=self._clone_mission(mission)
                )
            ],
            forced_assignments=forced_assignments,
            diverted_from_by_agent=diverted_from_by_agent,
        )
        await self._publish_single_allocation_projection(
            mission=mission,
            anomaly_id=anomaly_id,
            proposal=proposal,
        )

    async def _publish_single_allocation_projection(
        self,
        *,
        mission: MissionTask,
        anomaly_id: str | None,
        proposal: ExecutionGroup,
    ) -> None:
        """Keep the legacy allocation frame as a projection of MissionDecision."""

        assessments = self._group_candidate_assessments.get(proposal.id, [])
        fleet_by_id = {state.agent_id: state for state in self._snapshot_fleet()}
        eligible: list[AllocationEligibleUnit] = []
        excluded: list[AllocationExcludedUnit] = []
        reason_map = {
            "BUSY": AllocationExclusionReason.BUSY,
            "LOW_BATTERY": AllocationExclusionReason.LOW_BATTERY,
            "UNAVAILABLE": AllocationExclusionReason.UNAVAILABLE,
            "CAPABILITY_MISMATCH": AllocationExclusionReason.CAPABILITY_MISMATCH,
        }
        for assessment in assessments:
            state = fleet_by_id.get(assessment.agent_id)
            if state is None:
                continue
            exclusion = next(
                (
                    reason_map[reason]
                    for reason in assessment.exclusion_reasons
                    if reason in reason_map
                ),
                None,
            )
            if exclusion is not None:
                excluded.append(
                    AllocationExcludedUnit(
                        agent_id=state.agent_id,
                        fsm_state=state.fsm_state,
                        battery_pct=state.battery_pct,
                        capabilities=state.capabilities,
                        reason=exclusion,
                        active_mission_id=(
                            self._agent_mission_ids.get(state.agent_id)
                            or state.current_mission_id
                        ),
                    )
                )
                continue
            if assessment.score is not None:
                eligible.append(
                    AllocationEligibleUnit(
                        agent_id=state.agent_id,
                        fsm_state=state.fsm_state,
                        battery_pct=state.battery_pct,
                        capabilities=state.capabilities,
                        score=assessment.score,
                        score_breakdown=AllocationScoreBreakdown(
                            **assessment.score_breakdown
                        ),
                    )
                )

        winner = proposal.members[0] if proposal.members else None
        diversions = self._group_diversions.get(proposal.id, {})
        mode = "no_award" if winner is None else "diversion" if diversions else "auction"
        await self._publish_allocation_decision(
            mission=mission,
            anomaly_id=anomaly_id,
            mode=mode,
            eligible_units=eligible,
            excluded_units=[
                row
                for row in excluded
                if winner is None or row.agent_id != winner.agent_id
            ],
            winner_agent_id=winner.agent_id if winner is not None else None,
            winner_score=winner.score if winner is not None else None,
            diverted_from_mission_id=(
                diversions.get(winner.agent_id) if winner is not None else None
            ),
        )

    def _should_cooperative_verify(self, anomaly: Anomaly) -> bool:
        return (
            self.cooperative_verify_enabled
            and self.cooperative_verify_team_size > 1
            and anomaly.confidence >= self.cooperative_verify_min_confidence
        )

    async def _objective_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe(MISSION_OBJECTIVE_TOPIC):
            try:
                objective = MissionTask.model_validate_json(payload)
                await self.dispatch_execution_group(objective)
            except Exception as exc:
                logger.warning("rejected execution-group objective: %s", exc)

    async def _objective_approval_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe(OBJECTIVE_APPROVAL_TOPIC):
            try:
                approval = ObjectiveApprovalCommand.model_validate_json(payload)
                await self.approve_objective(approval)
            except Exception as exc:
                logger.warning("rejected objective approval: %s", exc)

    async def _authority_grant_loop(self) -> None:
        async for _topic, payload in self.bus.subscribe(MISSION_AUTHORITY_GRANT_TOPIC):
            try:
                grant = MissionAuthorityGrant.model_validate_json(payload)
                self.register_authority_grant(grant)
            except Exception as exc:
                logger.warning("rejected mission authority grant: %s", exc)

    async def prepare_execution_group(
        self,
        objective: MissionTask,
        *,
        anomaly_id: str | None = None,
        reinforces_group_id: str | None = None,
        decision_kind: MissionDecisionKind = MissionDecisionKind.LAUNCH_COMPOSITION,
        plans: list[ExecutionRolePlan] | None = None,
        excluded_agent_ids: set[str] | None = None,
        forced_assignments: dict[str, str] | None = None,
        diverted_from_by_agent: dict[str, str | None] | None = None,
        supersedes_decision_id: str | None = None,
    ) -> ExecutionGroup:
        """Recommend a composition, evaluate authority, and publish both records."""

        self._validate_objective(objective, has_explicit_plans=plans is not None)
        material = self._material_snapshot(objective)
        existing_decision_id = self._pending_proposals.get(objective.id)
        superseded_decision_id = supersedes_decision_id or existing_decision_id
        if existing_decision_id is not None:
            existing_decision = self._mission_decisions.get(existing_decision_id)
            existing_group_id = self._decision_groups.get(existing_decision_id)
            existing = (
                self._execution_groups.get(existing_group_id)
                if existing_group_id is not None
                else None
            )
            if (
                existing is not None
                and existing_decision is not None
                and self._proposal_snapshots.get(existing_decision_id) == material
                and existing_decision.decision_kind is decision_kind
            ):
                return existing
            self._pending_proposals.pop(objective.id, None)

        objective_plans = plans or self._plans_for_objective(objective)
        group = await self._prepare_group(
            objective=objective,
            plans=objective_plans,
            anomaly_id=anomaly_id,
            reinforces_group_id=reinforces_group_id,
            excluded_agent_ids=excluded_agent_ids,
            forced_assignments=forced_assignments,
            diverted_from_by_agent=diverted_from_by_agent,
        )
        decision = self._build_mission_decision(
            objective=objective,
            group=group,
            plans=objective_plans,
            decision_kind=decision_kind,
            supersedes_decision_id=superseded_decision_id,
        )
        group.decision_id = decision.decision_id
        self._objectives[objective.id] = objective
        self._mission_decisions[decision.decision_id] = decision
        self._decision_groups[decision.decision_id] = group.id
        self._objective_decisions[objective.id] = decision.decision_id
        self._proposal_snapshots[decision.decision_id] = material
        await self._publish_decision(decision)
        if decision_kind is not MissionDecisionKind.REPLACE_FAILED_EXECUTOR:
            await self._publish_group(group)
        if group.state is ExecutionGroupState.FAILED:
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            return group
        if decision.authority_verdict is MissionAuthorityVerdict.DENIED:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = "AUTHORITY_DENIED"
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            await self._publish_group(group)
            return group
        self._pending_proposals[objective.id] = decision.decision_id
        if decision.authority_verdict is MissionAuthorityVerdict.REVIEW_REQUIRED:
            self._set_objective_status(objective, ObjectiveStatus.WAITING_FOR_APPROVAL)
        return group

    async def approve_objective(
        self, approval: ObjectiveApprovalCommand
    ) -> ExecutionGroup | None:
        """Revalidate and dispatch one exact, still-current proposal."""

        applied_group_id = self._approved_decisions.get(approval.decision_id)
        if applied_group_id is not None:
            return self._execution_groups.get(applied_group_id)

        objective = self._objectives.get(approval.objective_id)
        pending_decision_id = self._pending_proposals.get(approval.objective_id)
        decision = self._mission_decisions.get(approval.decision_id)
        if (
            objective is None
            or decision is None
            or pending_decision_id != approval.decision_id
        ):
            return None
        group_id = self._decision_groups.get(decision.decision_id)
        proposal = self._execution_groups.get(group_id) if group_id is not None else None
        if proposal is None:
            return None
        if not self._actor_may_review(decision, approval.approved_by):
            return None

        action = MissionReviewAction(approval.action)
        if action is MissionReviewAction.REJECT:
            await self._record_review(decision, approval, action=action)
            self._pending_proposals.pop(objective.id, None)
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            proposal.failure_reason = "DECISION_REJECTED"
            await self._publish_group(proposal)
            return proposal
        if action is MissionReviewAction.OVERRIDE:
            return await self._override_decision(objective, decision, proposal, approval)

        if decision.authority_verdict is MissionAuthorityVerdict.DENIED:
            return None
        if self._proposal_snapshots.get(decision.decision_id) != self._material_snapshot(objective):
            self._pending_proposals.pop(objective.id, None)
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            return None
        current_grant = self._grant_for_objective(objective)
        if objective.authority_grant_id is not None and current_grant is None:
            return None
        verdict, reasons, _constraints = evaluate_mission_authority(
            objective=objective,
            decision_kind=decision.decision_kind,
            selected_agent_ids=[row.agent_id for row in decision.selected_assignments],
            grant=current_grant,
        )
        if verdict is MissionAuthorityVerdict.DENIED:
            logger.warning(
                "approval refused after authority revalidation: %s", ",".join(reasons)
            )
            return None
        if not await self._claim_prepared_group_for_dispatch(proposal):
            proposal.state = ExecutionGroupState.FAILED
            proposal.failure_reason = "PROPOSAL_STALE"
            self._pending_proposals.pop(objective.id, None)
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            await self._publish_group(proposal)
            return None

        await self._record_review(decision, approval, action=action)
        self._approved_decisions[decision.decision_id] = proposal.id
        self._pending_proposals.pop(objective.id, None)
        self._set_objective_status(objective, ObjectiveStatus.ACTIVE)
        await self._dispatch_claimed_group(proposal)
        return proposal

    async def dispatch_execution_group(
        self,
        objective: MissionTask,
        *,
        anomaly_id: str | None = None,
        plans: list[ExecutionRolePlan] | None = None,
        forced_assignments: dict[str, str] | None = None,
        diverted_from_by_agent: dict[str, str | None] | None = None,
    ) -> ExecutionGroup:
        proposal = await self.prepare_execution_group(
            objective,
            anomaly_id=anomaly_id,
            plans=plans,
            forced_assignments=forced_assignments,
            diverted_from_by_agent=diverted_from_by_agent,
        )
        if proposal.decision_id is None:
            return proposal
        decision = self._mission_decisions[proposal.decision_id]
        if decision.authority_verdict is not MissionAuthorityVerdict.AUTO_AUTHORIZED:
            return proposal
        if proposal.state is not ExecutionGroupState.FORMING:
            return proposal
        if not await self._claim_prepared_group_for_dispatch(proposal):
            proposal.state = ExecutionGroupState.FAILED
            proposal.failure_reason = "PROPOSAL_STALE"
            self._pending_proposals.pop(objective.id, None)
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            await self._publish_group(proposal)
            return proposal
        self._pending_proposals.pop(objective.id, None)
        self._set_objective_status(objective, ObjectiveStatus.ACTIVE)
        await self._dispatch_claimed_group(proposal)
        return proposal

    def _validate_objective(
        self, objective: MissionTask, *, has_explicit_plans: bool
    ) -> None:
        if not has_explicit_plans and objective.kind not in {
            COOPERATIVE_VERIFY_KIND,
            MissionKind.COVER.value,
        }:
            raise ValueError(
                "execution groups require an orchestration-only COOPERATIVE_VERIFY "
                "or COVER objective unless explicit role plans are provided"
            )
        if (objective.authority_grant_id is None) != (
            objective.authority_grant_revision is None
        ):
            raise ValueError("authority grant id and revision must be supplied together")

    def _plans_for_objective(self, objective: MissionTask) -> list[ExecutionRolePlan]:
        if objective.kind == COOPERATIVE_VERIFY_KIND:
            return self._cooperative_verify_plans(objective)
        return self._cover_plans(objective)

    @staticmethod
    def _material_snapshot(objective: MissionTask) -> str:
        payload = objective.model_dump(mode="json")
        payload.pop("status", None)
        payload.pop("ts", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _grant_for_objective(
        self, objective: MissionTask
    ) -> MissionAuthorityGrant | None:
        if (
            objective.authority_grant_id is None
            or objective.authority_grant_revision is None
        ):
            return None
        if self._latest_grant_revision.get(objective.authority_grant_id) != (
            objective.authority_grant_revision
        ):
            return None
        return self._authority_grants.get(
            (objective.authority_grant_id, objective.authority_grant_revision)
        )

    def _build_mission_decision(
        self,
        *,
        objective: MissionTask,
        group: ExecutionGroup,
        plans: list[ExecutionRolePlan],
        decision_kind: MissionDecisionKind,
        supersedes_decision_id: str | None,
    ) -> MissionDecision:
        grant = self._grant_for_objective(objective)
        hard_constraints = (
            self.hard_constraint_provider()
            if self.hard_constraint_provider is not None
            else None
        )
        hard_reasons, hard_snapshot = evaluate_mission_hard_constraints(
            objective, hard_constraints
        )
        if objective.authority_grant_id is not None and grant is None:
            verdict = MissionAuthorityVerdict.DENIED
            authority_reasons = ["GRANT_NOT_AVAILABLE"]
            authority_snapshot: dict[str, object] = {}
        else:
            verdict, authority_reasons, authority_snapshot = evaluate_mission_authority(
                objective=objective,
                decision_kind=decision_kind,
                selected_agent_ids=[member.agent_id for member in group.members],
                grant=grant,
            )
        if hard_reasons:
            verdict = MissionAuthorityVerdict.DENIED
            authority_reasons = [*hard_reasons, *authority_reasons]
        constraints_snapshot: dict[str, object] = {
            "hard": hard_snapshot,
            "delegated_authority": authority_snapshot,
        }

        role_requirements = {
            plan.role: sorted(required_capabilities(plan.mission)) for plan in plans
        }
        selected_assignments = [
            SelectedAssignment(
                agent_id=member.agent_id,
                role=member.role,
                mission_id=member.mission_id,
                supplied_capabilities=list(member.supplied_capabilities),
            )
            for member in group.members
        ]
        full_requirements_satisfied = (
            len(group.members) == group.requested_members
            and all(
                set(role_requirements.get(member.role, [])).issubset(
                    member.supplied_capabilities
                )
                for member in group.members
            )
        )
        requirements_snapshot: dict[str, object] = {
            "objective_kind": objective.kind,
            "requested_members": group.requested_members,
            "required_capabilities": sorted(required_capabilities(objective)),
            "role_requirements": role_requirements,
        }
        return MissionDecision(
            objective_id=objective.id,
            objective_revision=objective.revision,
            decision_kind=decision_kind,
            requirements_snapshot=requirements_snapshot,
            constraints_snapshot=constraints_snapshot,
            candidate_assessments=self._group_candidate_assessments.get(group.id, []),
            selected_assignments=selected_assignments,
            full_requirements_satisfied=full_requirements_satisfied,
            authority_grant_id=grant.grant_id if grant is not None else None,
            authority_grant_revision=grant.revision if grant is not None else None,
            authority_verdict=verdict,
            authority_reasons=authority_reasons,
            supersedes_decision_id=supersedes_decision_id,
        )

    def _actor_may_review(self, decision: MissionDecision, actor_id: str) -> bool:
        if decision.authority_grant_id is None:
            return True
        revision = decision.authority_grant_revision
        if revision is None:
            return False
        grant = self._authority_grants.get((decision.authority_grant_id, revision))
        if grant is None:
            return False
        return actor_id == grant.holder_id or actor_id in grant.approver_ids

    async def _record_review(
        self,
        decision: MissionDecision,
        approval: ObjectiveApprovalCommand,
        *,
        action: MissionReviewAction,
        replacement_decision_id: str | None = None,
    ) -> MissionDecisionReview:
        review = MissionDecisionReview(
            decision_id=decision.decision_id,
            objective_id=decision.objective_id,
            action=action,
            actor_id=approval.approved_by,
            replacement_decision_id=replacement_decision_id,
        )
        self._decision_reviews[review.review_id] = review
        await self.bus.publish(MISSION_DECISION_REVIEW_TOPIC, review.model_dump_json())
        return review

    async def _override_decision(
        self,
        objective: MissionTask,
        decision: MissionDecision,
        proposal: ExecutionGroup,
        approval: ObjectiveApprovalCommand,
    ) -> ExecutionGroup | None:
        """Create a superseding immutable selection, then commit that exact record."""

        assignments: dict[str, str] = {}
        for raw in approval.override_assignments:
            role = raw.get("role")
            agent_id = raw.get("agent_id")
            if not role or not agent_id or role in assignments:
                return None
            assignments[role] = agent_id
        if (
            decision.decision_kind is MissionDecisionKind.REPLACE_FAILED_EXECUTOR
            or objective.kind
            not in {COOPERATIVE_VERIFY_KIND, MissionKind.COVER.value}
        ):
            plans = [
                ExecutionRolePlan(
                    role=member.role,
                    mission=self._clone_mission(self._group_missions[member.mission_id]),
                )
                for member in proposal.members
            ]
        else:
            plans = self._plans_for_objective(objective)
        if set(assignments) != {plan.role for plan in plans}:
            return None
        if len(set(assignments.values())) != len(assignments):
            return None

        excluded: set[str] = set()
        if proposal.reinforces_group_id is not None:
            origin = self._execution_groups.get(proposal.reinforces_group_id)
            if origin is not None:
                excluded = {member.agent_id for member in origin.members}
        self._pending_proposals.pop(objective.id, None)
        replacement = await self.prepare_execution_group(
            objective,
            anomaly_id=proposal.anomaly_id,
            reinforces_group_id=proposal.reinforces_group_id,
            decision_kind=decision.decision_kind,
            plans=plans,
            excluded_agent_ids=excluded,
            forced_assignments=assignments,
            supersedes_decision_id=decision.decision_id,
        )
        if replacement.decision_id is None:
            return replacement
        replacement_decision = self._mission_decisions[replacement.decision_id]
        await self._record_review(
            decision,
            approval,
            action=MissionReviewAction.OVERRIDE,
            replacement_decision_id=replacement_decision.decision_id,
        )
        if (
            replacement.state is not ExecutionGroupState.FORMING
            or not replacement_decision.full_requirements_satisfied
            or replacement_decision.authority_verdict is MissionAuthorityVerdict.DENIED
        ):
            return replacement
        if not await self._claim_prepared_group_for_dispatch(replacement):
            replacement.state = ExecutionGroupState.FAILED
            replacement.failure_reason = "PROPOSAL_STALE"
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            await self._publish_group(replacement)
            return replacement
        self._approved_decisions[replacement_decision.decision_id] = replacement.id
        self._pending_proposals.pop(objective.id, None)
        self._set_objective_status(objective, ObjectiveStatus.ACTIVE)
        await self._dispatch_claimed_group(replacement)
        return replacement

    async def _publish_decision(self, decision: MissionDecision) -> None:
        await self.bus.publish(MISSION_DECISION_TOPIC, decision.model_dump_json())

    def _set_objective_status(
        self,
        objective: MissionTask,
        status: ObjectiveStatus,
        *,
        reason: str | None = None,
    ) -> None:
        objective.status = status
        objective.ts = datetime.now(UTC)
        self._objectives[objective.id] = objective
        frame = ObjectiveStateFrame(
            objective_id=objective.id,
            objective_revision=objective.revision,
            status=status,
            decision_id=self._objective_decisions.get(objective.id),
            reason=reason,
            ts=objective.ts,
        )
        task = asyncio.create_task(
            self.bus.publish(MISSION_OBJECTIVE_STATE_TOPIC, frame.model_dump_json())
        )
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

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
        sensors = [SensorKind(raw) for raw in objective.params.get("sensors", [])]
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
                sensors=sensors or None,
                hover_s=hover_s,
                altitude_m=base_altitude_m + altitude_step_m * idx,
                priority=objective.priority,
                deadline_s=None,
                required_capabilities=_role_requirements(objective, role),
                source=objective.source,
                authority_policy=objective.authority_policy,
                requested_by=objective.requested_by,
                authority_grant_id=objective.authority_grant_id,
                authority_grant_revision=objective.authority_grant_revision,
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
                required_capabilities=_role_requirements(
                    objective, f"COVERAGE_SLICE_{idx + 1}"
                ),
                source=objective.source,
                authority_policy=objective.authority_policy,
                requested_by=objective.requested_by,
                authority_grant_id=objective.authority_grant_id,
                authority_grant_revision=objective.authority_grant_revision,
            )
            role = f"COVERAGE_SLICE_{idx + 1}"
            child.params["execution_role"] = role
            child.params["parent_objective_id"] = objective.id
            child.params["slice_index"] = idx
            child.params["slice_count"] = fleet_size
            plans.append(ExecutionRolePlan(role=role, mission=child))
        return plans

    async def _prepare_group(
        self,
        *,
        objective: MissionTask,
        plans: list[ExecutionRolePlan],
        anomaly_id: str | None,
        reinforces_group_id: str | None = None,
        excluded_agent_ids: set[str] | None = None,
        forced_assignments: dict[str, str] | None = None,
        diverted_from_by_agent: dict[str, str | None] | None = None,
    ) -> ExecutionGroup:
        """Compose a proposal without claiming, publishing awards, or dispatching."""

        if not plans:
            raise ValueError("execution group requires at least one role")

        group = ExecutionGroup(
            objective_mission_id=objective.id,
            objective_kind=objective.kind,
            anomaly_id=anomaly_id,
            required_capabilities=sorted(required_capabilities(objective)),
            reinforces_group_id=reinforces_group_id,
            requested_members=len(plans),
        )
        assignments: list[
            tuple[ExecutionRolePlan, str, float, dict[str, float]]
        ] = []
        unfilled: list[ExecutionRolePlan] = []
        reserved: set[str] = set(excluded_agent_ids or ())
        candidate_assessments: list[CandidateAssessment] = []

        for plan in plans:
            forced_agent_id = (forced_assignments or {}).get(plan.role)
            if forced_agent_id is None:
                choice = self._select_group_candidate(
                    plan.mission, excluded_agent_ids=reserved
                )
            else:
                forced_state = next(
                    (
                        state
                        for state in self._snapshot_fleet()
                        if state.agent_id == forced_agent_id
                        and self._is_group_candidate(
                            state,
                            excluded_agent_ids=reserved,
                            mission=plan.mission,
                            allowed_airborne_agent_ids=set(
                                (diverted_from_by_agent or {}).keys()
                            ),
                        )
                    ),
                    None,
                )
                if forced_state is None:
                    choice = None
                else:
                    bid = build_bid(plan.mission, forced_state)
                    choice = (forced_agent_id, bid.score, dict(bid.reason))
            if choice is None:
                unfilled.append(plan)
                candidate_assessments.extend(
                    self._candidate_assessments(
                        plan,
                        excluded_agent_ids=reserved,
                        selected_agent_id=None,
                        allowed_airborne_agent_ids=set(
                            (diverted_from_by_agent or {}).keys()
                        ),
                    )
                )
                continue
            agent_id, score, breakdown = choice
            candidate_assessments.extend(
                self._candidate_assessments(
                    plan,
                    excluded_agent_ids=reserved,
                    selected_agent_id=agent_id,
                    allowed_airborne_agent_ids=set(
                        (diverted_from_by_agent or {}).keys()
                    ),
                )
            )
            reserved.add(agent_id)
            assignments.append((plan, agent_id, score, breakdown))

        if not assignments:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = "INSUFFICIENT_ELIGIBLE_CAPACITY"
            self._execution_groups[group.id] = group
            self._group_candidate_assessments[group.id] = candidate_assessments
            return group

        members: list[ExecutionGroupMember] = []
        templates: dict[str, MissionTask] = {}
        fleet_by_id = {state.agent_id: state for state in self._snapshot_fleet()}
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
                    supplied_capabilities=list(fleet_by_id[agent_id].capabilities),
                )
            )
            templates[plan.role] = self._clone_mission(child)
            self._group_missions[child.id] = child

        group.members = members
        self._execution_groups[group.id] = group
        self._group_candidate_assessments[group.id] = candidate_assessments
        self._group_role_templates[group.id] = templates
        if diverted_from_by_agent:
            self._group_diversions[group.id] = dict(diverted_from_by_agent)
        if reinforces_group_id is None:
            self._reinforcement_records[group.id] = _ObjectiveReinforcementRecord(
                objective=objective,
                anomaly_id=anomaly_id,
                unfilled_plans=unfilled,
            )

        return group

    async def _claim_prepared_group_for_dispatch(
        self, group: ExecutionGroup
    ) -> bool:
        """Cancel an exact patrol diversion, then revalidate and claim."""

        for agent_id, diverted_from in self._group_diversions.get(group.id, {}).items():
            if self._agent_mission_ids.get(agent_id) != diverted_from:
                return False
            task = self._agent_tasks.get(agent_id)
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception("failed to stop patrol before diversion")
                    return False
        return self._claim_prepared_group(group)

    def _claim_prepared_group(self, group: ExecutionGroup) -> bool:
        """Revalidate and claim every proposed member without an await boundary."""

        if group.state is not ExecutionGroupState.FORMING:
            return False
        if group.decision_id is None:
            return False
        decision = self._mission_decisions.get(group.decision_id)
        if decision is None:
            return False
        objective = self._objectives.get(decision.objective_id)
        if objective is None:
            return False
        if self._proposal_snapshots.get(decision.decision_id) != self._material_snapshot(
            objective
        ):
            return False
        grant = self._grant_for_objective(objective)
        if objective.authority_grant_id is not None and grant is None:
            return False
        hard_constraints = (
            self.hard_constraint_provider()
            if self.hard_constraint_provider is not None
            else None
        )
        hard_reasons, _hard_snapshot = evaluate_mission_hard_constraints(
            objective, hard_constraints
        )
        if hard_reasons:
            return False
        verdict, _reasons, _constraints = evaluate_mission_authority(
            objective=objective,
            decision_kind=decision.decision_kind,
            selected_agent_ids=[member.agent_id for member in group.members],
            grant=grant,
        )
        if verdict is MissionAuthorityVerdict.DENIED:
            return False
        reserved: set[str] = set()
        allowed_airborne = set(self._group_diversions.get(group.id, {}))
        for member in group.members:
            mission = self._group_missions.get(member.mission_id)
            if mission is None:
                return False
            eligible_ids = {
                state.agent_id
                for state in self._eligible_fleet(
                    excluded_agent_ids=reserved,
                    mission=mission,
                    allowed_airborne_agent_ids=allowed_airborne,
                )
            }
            if member.agent_id not in eligible_ids:
                return False
            reserved.add(member.agent_id)

        for member in group.members:
            self._busy.add(member.agent_id)
            self._agent_mission_ids[member.agent_id] = member.mission_id
            self._group_task_to_role[member.mission_id] = (group.id, member.role)
        group.state = ExecutionGroupState.ACTIVE
        return True

    async def _dispatch_claimed_group(self, group: ExecutionGroup) -> None:
        decision = (
            self._mission_decisions.get(group.decision_id)
            if group.decision_id is not None
            else None
        )
        if (
            decision is not None
            and decision.decision_kind is MissionDecisionKind.REPLACE_FAILED_EXECUTOR
            and group.reinforces_group_id is not None
        ):
            origin = self._execution_groups.get(group.reinforces_group_id)
            if origin is not None:
                replacement_roles = {member.role for member in group.members}
                replaced_by_role: dict[str, str] = {}
                for index, member in enumerate(origin.members):
                    if (
                        member.role in replacement_roles
                        and member.state is ExecutionGroupMemberState.FAILED
                    ):
                        replaced_by_role[member.role] = member.agent_id
                        origin.members[index] = member.model_copy(
                            update={"state": ExecutionGroupMemberState.REPLACED}
                        )
                for member in group.members:
                    origin.members.append(
                        member.model_copy(
                            update={
                                "replaces_agent_id": replaced_by_role.get(member.role)
                            }
                        )
                    )
                    self._group_task_to_role[member.mission_id] = (
                        origin.id,
                        member.role,
                    )
                origin.failure_reason = None
                origin.decision_id = decision.decision_id
                origin.composition_revision += 1
                self._decision_groups[decision.decision_id] = origin.id
                self._execution_groups.pop(group.id, None)
                await self._publish_group(origin)
        else:
            await self._publish_group(group)
        for member in group.members:
            mission = self._group_missions[member.mission_id]
            await self._publish_group_award(mission, member.agent_id, member.score)
            self._start_mission(member.agent_id, mission, is_verify=True)
            logger.info(
                "execution group %s role %s -> %s mission=%s",
                group.id,
                member.role,
                member.agent_id,
                member.mission_id,
            )

    def _eligible_fleet(
        self,
        *,
        excluded_agent_ids: set[str],
        mission: MissionTask | None = None,
        allowed_airborne_agent_ids: set[str] | None = None,
    ) -> list[FleetState]:
        eligible: list[FleetState] = []
        for state in self._snapshot_fleet():
            if self._is_group_candidate(
                state,
                excluded_agent_ids=excluded_agent_ids,
                mission=mission,
                allowed_airborne_agent_ids=allowed_airborne_agent_ids or set(),
            ):
                eligible.append(state)
        return eligible

    def _is_group_candidate(
        self,
        state: FleetState,
        *,
        excluded_agent_ids: set[str],
        mission: MissionTask | None,
        allowed_airborne_agent_ids: set[str],
    ) -> bool:
        if state.agent_id in excluded_agent_ids:
            return False
        is_bounded_diversion = state.agent_id in allowed_airborne_agent_ids
        if state.agent_id in self._verifying:
            return False
        if (
            not is_bounded_diversion
            and (state.agent_id in self._busy or state.current_mission_id is not None)
        ):
            return False
        if state.battery_pct < MIN_BATTERY_PCT:
            return False
        if not is_bounded_diversion and not is_available(state.fsm_state):
            return False
        required = required_capabilities(mission) if mission is not None else set()
        return has_capabilities(state, required)

    def _candidate_assessments(
        self,
        plan: ExecutionRolePlan,
        *,
        excluded_agent_ids: set[str],
        selected_agent_id: str | None,
        allowed_airborne_agent_ids: set[str] | None = None,
    ) -> list[CandidateAssessment]:
        """Record every candidate fact used by the deterministic selector."""

        required = required_capabilities(plan.mission)
        assessments: list[CandidateAssessment] = []
        allowed_airborne = allowed_airborne_agent_ids or set()
        for state in sorted(self._snapshot_fleet(), key=lambda item: item.agent_id):
            selected = state.agent_id == selected_agent_id
            score: float | None = None
            breakdown: dict[str, float] = {}
            if state.agent_id in excluded_agent_ids:
                reason = "RESERVED_BY_HIGHER_RANKED_ROLE"
            elif (
                state.agent_id in self._verifying
                or (
                    state.agent_id not in allowed_airborne
                    and (
                        state.agent_id in self._busy
                        or state.current_mission_id is not None
                    )
                )
            ):
                reason = "BUSY"
            elif state.battery_pct < MIN_BATTERY_PCT:
                reason = "LOW_BATTERY"
            elif (
                state.agent_id not in allowed_airborne
                and not is_available(state.fsm_state)
            ):
                reason = "UNAVAILABLE"
            elif not has_capabilities(state, required):
                reason = "CAPABILITY_MISMATCH"
            else:
                bid = build_bid(plan.mission, state)
                score = bid.score
                breakdown = dict(bid.reason)
                reason = "" if selected else "LOWER_SCORE"
            assessments.append(
                CandidateAssessment(
                    agent_id=state.agent_id,
                    role=plan.role,
                    supplied_capabilities=list(state.capabilities),
                    availability_state=state.fsm_state.value,
                    score=score,
                    score_breakdown=breakdown,
                    selected=selected,
                    exclusion_reasons=[reason] if reason else [],
                )
            )
        return assessments

    def _select_group_candidate(
        self,
        mission: MissionTask,
        *,
        excluded_agent_ids: set[str],
    ) -> tuple[str, float, dict[str, float]] | None:
        ranked: list[tuple[str, float, dict[str, float]]] = []
        for state in self._eligible_fleet(
            excluded_agent_ids=excluded_agent_ids,
            mission=mission,
        ):
            bid = build_bid(mission, state)
            ranked.append((state.agent_id, bid.score, dict(bid.reason)))
        if not ranked:
            return None
        ranked.sort(key=lambda row: (-row[1], row[0]))
        return ranked[0]

    async def _reinforcement_loop(self) -> None:
        while True:
            await asyncio.sleep(self.reinforcement_review_period_s)
            try:
                await self.review_reinforcements()
            except Exception:
                logger.exception("reinforcement review failed")

    async def review_reinforcements(self) -> list[ExecutionGroup]:
        dispatched: list[ExecutionGroup] = []
        async with self._group_lock:
            for origin_id in list(self._reinforcement_records):
                record = self._reinforcement_records[origin_id]
                origin = self._execution_groups.get(origin_id)
                if origin is None or origin.state not in RUNNING_GROUP_STATES:
                    self._reinforcement_records.pop(origin_id, None)
                    continue
                objective = self._objectives.get(origin.objective_mission_id)
                if objective is not None and objective.status in {
                    ObjectiveStatus.WAITING_FOR_APPROVAL,
                    ObjectiveStatus.SATISFIED,
                    ObjectiveStatus.FAILED,
                }:
                    continue
                if not record.unfilled_plans:
                    self._reinforcement_records.pop(origin_id, None)
                    continue
                decision = self.reinforcement_policy(
                    self._observe_objective(origin, record)
                )
                if not decision.reinforce or decision.strength < 1:
                    logger.debug(
                        "no reinforcement for group %s: %s", origin_id, decision.reason
                    )
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
            if member.state not in _LOST_MEMBER_STATES
        )
        next_mission = (
            record.unfilled_plans[0].mission if record.unfilled_plans else None
        )
        return ReinforcementObservation(
            objective_kind=origin.objective_kind,
            objective_state=origin.state,
            requested_members=origin.requested_members,
            committed_members=committed,
            eligible_agents=len(
                self._eligible_fleet(
                    excluded_agent_ids=set(),
                    mission=next_mission,
                )
            ),
            reinforcements_dispatched=len(record.reinforcement_group_ids),
            max_reinforcements=self.max_reinforcements_per_objective,
        )

    async def _dispatch_reinforcement(
        self,
        origin: ExecutionGroup,
        record: _ObjectiveReinforcementRecord,
        decision: ReinforcementDecision,
    ) -> ExecutionGroup:
        plans = [
            ExecutionRolePlan(
                role=plan.role, mission=self._clone_mission(plan.mission)
            )
            for plan in record.unfilled_plans[: decision.strength]
        ]
        group = await self.prepare_execution_group(
            record.objective,
            anomaly_id=record.anomaly_id,
            reinforces_group_id=origin.id,
            decision_kind=MissionDecisionKind.REINFORCE_CAPACITY,
            plans=plans,
        )
        mission_decision = (
            self._mission_decisions.get(group.decision_id)
            if group.decision_id is not None
            else None
        )
        if (
            group.state is ExecutionGroupState.FORMING
            and mission_decision is not None
            and mission_decision.authority_verdict
            is MissionAuthorityVerdict.AUTO_AUTHORIZED
        ):
            if await self._claim_prepared_group_for_dispatch(group):
                self._pending_proposals.pop(record.objective.id, None)
                self._set_objective_status(record.objective, ObjectiveStatus.ACTIVE)
                await self._dispatch_claimed_group(group)
            else:
                group.state = ExecutionGroupState.FAILED
                group.failure_reason = "PROPOSAL_STALE"
                await self._publish_group(group)
        record.reinforcement_group_ids.append(group.id)
        filled_roles = {member.role for member in group.members}
        record.unfilled_plans = [
            plan for plan in record.unfilled_plans if plan.role not in filled_roles
        ]
        logger.info(
            "execution group %s reinforced by %s: %d/%d roles (%s)",
            origin.id,
            group.id,
            len(group.members),
            len(plans),
            decision.reason,
        )
        return group

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
                objective = self._objectives.get(group.objective_mission_id)
                if objective is not None:
                    # Execution completion is physical evidence, not semantic proof
                    # that the objective's acceptance criteria were met. A truth
                    # evaluator may promote this to SATISFIED separately.
                    self._set_objective_status(
                        objective,
                        ObjectiveStatus.UNRESOLVED,
                        reason="EXECUTION_COMPLETE_AWAITING_SEMANTIC_EVIDENCE",
                    )
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
            objective = self._objectives.get(group.objective_mission_id)
            if objective is not None:
                self._set_objective_status(objective, ObjectiveStatus.FAILED)
            await self._publish_group(group)
            return

        template = self._group_role_templates[group.id][role]
        replacement_mission = self._clone_mission(template)
        replacement_mission.params["execution_group_id"] = group.id
        objective = self._objectives.get(group.objective_mission_id)
        if objective is None:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = f"ROLE_FAILED:{role}:OBJECTIVE_MISSING"
            await self._publish_group(group)
            return
        proposal = await self.prepare_execution_group(
            objective,
            anomaly_id=group.anomaly_id,
            reinforces_group_id=group.id,
            decision_kind=MissionDecisionKind.REPLACE_FAILED_EXECUTOR,
            plans=[ExecutionRolePlan(role=role, mission=replacement_mission)],
            excluded_agent_ids={member.agent_id for member in group.members},
        )
        if proposal.state is ExecutionGroupState.FAILED:
            group.state = ExecutionGroupState.FAILED
            group.failure_reason = f"ROLE_FAILED:{role}:NO_REPLACEMENT"
            self._set_objective_status(objective, ObjectiveStatus.UNRESOLVED)
            await self._publish_group(group)
            return
        mission_decision = (
            self._mission_decisions.get(proposal.decision_id)
            if proposal.decision_id is not None
            else None
        )
        if (
            mission_decision is not None
            and mission_decision.authority_verdict
            is MissionAuthorityVerdict.AUTO_AUTHORIZED
            and await self._claim_prepared_group_for_dispatch(proposal)
        ):
            self._pending_proposals.pop(objective.id, None)
            self._set_objective_status(objective, ObjectiveStatus.ACTIVE)
            await self._dispatch_claimed_group(proposal)
            return
        group.failure_reason = f"REASSIGNMENT_REVIEW_REQUIRED:{proposal.decision_id}"
        await self._publish_group(group)

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
            params=json.loads(json.dumps(template.params)),
            priority=template.priority,
            deadline=template.deadline,
            source=template.source,
            requested_by=template.requested_by,
            authority_grant_id=template.authority_grant_id,
            authority_grant_revision=template.authority_grant_revision,
            authority_policy=template.authority_policy,
        )


__all__ = (
    "EXECUTION_GROUP_TOPIC",
    "MISSION_AUTHORITY_GRANT_TOPIC",
    "MISSION_DECISION_REVIEW_TOPIC",
    "MISSION_DECISION_TOPIC",
    "MISSION_OBJECTIVE_STATE_TOPIC",
    "MISSION_OBJECTIVE_TOPIC",
    "OBJECTIVE_APPROVAL_TOPIC",
    "RUNNING_GROUP_STATES",
    "ExecutionGroupOrchestrator",
    "ExecutionRolePlan",
    "HardConstraintProvider",
    "ReinforcementDecision",
    "ReinforcementObservation",
    "ReinforcementPolicy",
    "shortfall_reinforcement_policy",
)
