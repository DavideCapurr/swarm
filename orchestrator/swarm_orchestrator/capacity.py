"""Deterministic SwarmOS capacity planning.

This is the policy boundary between objective demand and physical executors.
The planner consumes canonical fleet state plus SwarmOS-owned mission
commitments and returns ranked capacity.  It never dispatches aircraft itself.

Policy, deliberately simple:

* idle eligible capacity is always consumed before committed capacity;
* committed capacity is considered only when its objective is explicitly
  preemptible and the new objective has strictly higher priority;
* a donor objective is never reduced below its declared minimum capacity;
* within each source class, the existing central allocator score chooses the
  best executor, with deterministic agent-id tie breaking.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum

from swarm_core.allocator import build_bid
from swarm_core.fsm import is_available
from swarm_core.messages import AgentState, FleetState, MissionTask
from swarm_core.objectives import ObjectiveDemand, demand_for_mission


class CapacitySource(str, Enum):
    IDLE = "idle"
    PREEMPTIBLE = "preemptible"


@dataclass(frozen=True)
class CapacityChoice:
    agent_id: str
    source: CapacitySource
    score: float
    score_breakdown: dict[str, float]
    diverted_from_mission_id: str | None = None
    diverted_from_objective_id: str | None = None


@dataclass(frozen=True)
class CapacitySnapshot:
    idle: tuple[CapacityChoice, ...]
    preemptible: tuple[CapacityChoice, ...]

    @property
    def all(self) -> tuple[CapacityChoice, ...]:
        return self.idle + self.preemptible


_PREEMPTIBLE_STATES = frozenset(
    {AgentState.TAKEOFF, AgentState.EN_ROUTE, AgentState.ON_STATION}
)


def objective_key(mission: MissionTask) -> str:
    return str(mission.params.get("parent_objective_id") or mission.id)


def _active_counts(
    active_missions: dict[str, MissionTask], planned_preemptions: set[str]
) -> Counter[str]:
    return Counter(
        objective_key(mission)
        for agent_id, mission in active_missions.items()
        if agent_id not in planned_preemptions
    )


def _can_preempt(
    *,
    request: MissionTask,
    donor: MissionTask,
    donor_demand: ObjectiveDemand,
    active_count: int,
) -> bool:
    if not donor_demand.preemptible:
        return False
    if donor_demand.preemption_policy != "higher_priority":
        return False
    if request.priority <= donor_demand.priority:
        return False
    if active_count - 1 < donor_demand.minimum_capacity:
        return False
    return True


def evaluate_capacity(
    request: MissionTask,
    fleet: list[FleetState],
    *,
    active_missions: dict[str, MissionTask],
    excluded_agent_ids: set[str] | None = None,
    planned_preemptions: set[str] | None = None,
    min_battery_pct: float = 25.0,
) -> CapacitySnapshot:
    """Classify and rank idle plus safely-preemptible capacity.

    ``planned_preemptions`` is important for multi-agent composition: after one
    donor executor has been tentatively selected, the next selection sees that
    loss when enforcing the donor objective's minimum-capacity floor.
    """

    excluded = excluded_agent_ids or set()
    planned = planned_preemptions or set()
    active_counts = _active_counts(active_missions, planned)
    idle: list[CapacityChoice] = []
    preemptible: list[CapacityChoice] = []

    for state in fleet:
        if state.agent_id in excluded or state.agent_id in planned:
            continue
        if state.battery_pct < min_battery_pct:
            continue

        committed = active_missions.get(state.agent_id)
        if committed is None:
            # A vendor-reported mission that SwarmOS does not own is fail-closed:
            # we cannot prove its preemption policy or donor floor.
            if state.current_mission_id is not None:
                continue
            if not is_available(state.fsm_state):
                continue
            bid = build_bid(request, state)
            idle.append(
                CapacityChoice(
                    agent_id=state.agent_id,
                    source=CapacitySource.IDLE,
                    score=bid.score,
                    score_breakdown=dict(bid.reason),
                )
            )
            continue

        if state.fsm_state not in _PREEMPTIBLE_STATES:
            continue
        donor_demand = demand_for_mission(committed)
        donor_key = objective_key(committed)
        if not _can_preempt(
            request=request,
            donor=committed,
            donor_demand=donor_demand,
            active_count=active_counts[donor_key],
        ):
            continue

        # Score the physical fit exactly as the existing allocator does, but do
        # not inject its generic BUSY penalty: eligibility was decided explicitly
        # above by objective policy and donor-floor impact.
        scored_state = state.model_copy(update={"current_mission_id": None})
        bid = build_bid(request, scored_state)
        preemptible.append(
            CapacityChoice(
                agent_id=state.agent_id,
                source=CapacitySource.PREEMPTIBLE,
                score=bid.score,
                score_breakdown=dict(bid.reason),
                diverted_from_mission_id=committed.id,
                diverted_from_objective_id=donor_key,
            )
        )

    idle.sort(key=lambda choice: (-choice.score, choice.agent_id))
    preemptible.sort(key=lambda choice: (-choice.score, choice.agent_id))
    return CapacitySnapshot(tuple(idle), tuple(preemptible))


def choose_capacity(
    request: MissionTask,
    fleet: list[FleetState],
    *,
    active_missions: dict[str, MissionTask],
    excluded_agent_ids: set[str] | None = None,
    planned_preemptions: set[str] | None = None,
    min_battery_pct: float = 25.0,
) -> CapacityChoice | None:
    """Choose one executor, preferring idle capacity over preemption."""

    snapshot = evaluate_capacity(
        request,
        fleet,
        active_missions=active_missions,
        excluded_agent_ids=excluded_agent_ids,
        planned_preemptions=planned_preemptions,
        min_battery_pct=min_battery_pct,
    )
    if snapshot.idle:
        return snapshot.idle[0]
    if snapshot.preemptible:
        return snapshot.preemptible[0]
    return None


__all__ = (
    "CapacityChoice",
    "CapacitySnapshot",
    "CapacitySource",
    "choose_capacity",
    "evaluate_capacity",
    "objective_key",
)
