"""Central fleet-state mission allocator.

SwarmOS evaluates canonical FleetState centrally, computes a score for each
candidate, and selects the winner. Physical agents do not bid for work, choose
their own missions, or participate in fleet-level decision making.
"""

from __future__ import annotations

from dataclasses import dataclass

from swarm_core.capabilities import has_required_capabilities
from swarm_core.geometry import haversine_m
from swarm_core.messages import Bid, FleetState, Geo, MissionTask
from swarm_core.missions import MissionKind


@dataclass(frozen=True)
class AllocatorWeights:
    w_distance: float = 1.0
    w_battery: float = 0.8
    w_priority: float = 0.5
    w_busy: float = 5.0


def _mission_geo(mission: MissionTask) -> Geo | None:
    kind = mission.kind
    if kind in (MissionKind.VERIFY.value, MissionKind.RELAY.value):
        geo = mission.params.get("geo")
        if geo:
            return Geo(**geo)
    if kind in (MissionKind.PATROL.value, MissionKind.COVER.value):
        area = mission.params.get("area") or []
        if area:
            return Geo(**area[0])
    return None


def required_capabilities(mission: MissionTask) -> set[str]:
    """Read objective capability requirements from SwarmOS mission state."""

    return set(mission.params.get("required_capabilities", []))


def has_capabilities(fleet_member: FleetState, required: set[str]) -> bool:
    """Capability eligibility is decided centrally from canonical state."""

    if not required:
        return True
    return has_required_capabilities(set(fleet_member.capabilities), required)


def score_bid(
    mission: MissionTask,
    fleet_member: FleetState,
    weights: AllocatorWeights = AllocatorWeights(),
) -> tuple[float, dict[str, float]]:
    mgeo = _mission_geo(mission)
    distance_m = haversine_m(fleet_member.geo, mgeo) if mgeo else 0.0
    distance_score = weights.w_distance * (1.0 / (1.0 + distance_m / 1000.0))
    battery_score = weights.w_battery * (fleet_member.battery_pct / 100.0)
    priority_score = weights.w_priority * (mission.priority / 100.0)
    busy_penalty = weights.w_busy if fleet_member.current_mission_id else 0.0

    score = distance_score + battery_score + priority_score - busy_penalty
    return score, {
        "distance_m": distance_m,
        "distance_score": distance_score,
        "battery_pct": fleet_member.battery_pct,
        "battery_score": battery_score,
        "priority": float(mission.priority),
        "priority_score": priority_score,
        "busy_penalty": busy_penalty,
    }


def build_bid(mission: MissionTask, fleet_member: FleetState) -> Bid:
    score, reason = score_bid(mission, fleet_member)
    return Bid(
        mission_id=mission.id,
        agent_id=fleet_member.agent_id,
        score=score,
        reason=reason,
    )


def select_winner(bids: list[Bid]) -> Bid | None:
    if not bids:
        return None
    return max(bids, key=lambda b: (b.score, b.agent_id))


def eligible(
    fleet: list[FleetState],
    *,
    min_battery_pct: float = 25.0,
    mission: MissionTask | None = None,
) -> list[FleetState]:
    """Filter fleet by availability, battery and objective capability needs."""

    from swarm_core.fsm import is_available

    required = required_capabilities(mission) if mission else set()

    return [
        f
        for f in fleet
        if is_available(f.fsm_state)
        and f.battery_pct >= min_battery_pct
        and f.current_mission_id is None
        and has_capabilities(f, required)
    ]
