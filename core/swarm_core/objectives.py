"""Reusable objective demand for SwarmOS capacity planning.

Mission constructors remain the public DSL.  This module turns those mission
objects into an explicit capacity contract consumed by the orchestrator.  The
contract is intentionally small: deterministic policy is enough to prove that
SwarmOS, rather than a replay timeline, decides when capacity is sufficient,
when degradation is acceptable, and whether committed work may be preempted.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from swarm_core.messages import MissionTask
from swarm_core.missions import COOPERATIVE_VERIFY_KIND, MissionKind


class ObjectiveDemand(BaseModel):
    """Capacity requirements and policy for one mission-level objective."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    roles: tuple[str, ...] = ()
    minimum_capacity: int = Field(..., ge=1)
    desired_capacity: int = Field(..., ge=1)
    priority: int
    acceptable_degradation: bool = False
    preemptible: bool = False
    preemption_policy: Literal["never", "higher_priority"] = "never"


def demand_for_mission(mission: MissionTask) -> ObjectiveDemand:
    """Derive a reusable demand contract from the existing mission DSL.

    Child missions created by an ``ExecutionGroup`` carry the parent objective's
    capacity metadata in ``params``.  That lets the capacity planner reason about
    already-committed executors without needing demo-specific knowledge or a
    second shadow registry of objectives.
    """

    params = mission.params
    explicit_min = params.get("objective_minimum_capacity")
    explicit_desired = params.get("objective_desired_capacity")
    explicit_preemptible = params.get("objective_preemptible")
    explicit_degradation = params.get("objective_acceptable_degradation")
    explicit_policy = params.get("objective_preemption_policy")

    if mission.kind == COOPERATIVE_VERIFY_KIND:
        desired = max(2, int(params.get("team_size", 3)))
        roles = tuple(str(role) for role in params.get("roles", []))
        minimum = int(params.get("minimum_capacity", desired))
    elif mission.kind == MissionKind.COVER.value:
        desired = max(1, int(params.get("fleet_size", 1)))
        minimum = int(params.get("minimum_capacity", desired))
        roles = ()
    else:
        desired = int(explicit_desired or 1)
        minimum = int(explicit_min or 1)
        roles = ()

    if explicit_desired is not None:
        desired = int(explicit_desired)
    if explicit_min is not None:
        minimum = int(explicit_min)

    desired = max(1, desired)
    minimum = max(1, min(minimum, desired))
    acceptable_degradation = bool(
        explicit_degradation
        if explicit_degradation is not None
        else params.get("acceptable_degradation", minimum < desired)
    )
    preemptible = bool(
        explicit_preemptible
        if explicit_preemptible is not None
        else params.get("preemptible", False)
    )
    policy = str(
        explicit_policy
        if explicit_policy is not None
        else params.get("preemption_policy", "higher_priority" if preemptible else "never")
    )
    if policy not in {"never", "higher_priority"}:
        policy = "never"

    return ObjectiveDemand(
        roles=roles,
        minimum_capacity=minimum,
        desired_capacity=desired,
        priority=mission.priority,
        acceptable_degradation=acceptable_degradation,
        preemptible=preemptible,
        preemption_policy=policy,  # type: ignore[arg-type]
    )


def stamp_objective_demand(child: MissionTask, parent: MissionTask) -> MissionTask:
    """Copy parent demand metadata onto an executable child mission."""

    demand = demand_for_mission(parent)
    child.params.update(
        {
            "parent_objective_id": parent.id,
            "objective_minimum_capacity": demand.minimum_capacity,
            "objective_desired_capacity": demand.desired_capacity,
            "objective_preemptible": demand.preemptible,
            "objective_acceptable_degradation": demand.acceptable_degradation,
            "objective_preemption_policy": demand.preemption_policy,
        }
    )
    return child


__all__ = ("ObjectiveDemand", "demand_for_mission", "stamp_objective_demand")
