"""Central fleet-state mission allocator.

SwarmOS evaluates canonical `FleetState` centrally, computes a score for each
candidate, and selects the winner. Physical agents do not bid for work, choose
their own missions, or participate in fleet-level decision making.

`Bid` is retained as a legacy/internal candidate-score DTO because existing
interfaces and tests use that name. A `Bid` in the current runtime is created by
SwarmOS from fleet state; it is not emitted or chosen by an aircraft.

Scoring is intentionally explicit and tunable from one place. The score is:

    score = w_distance * (1 / (1 + distance_m / 1000))
          + w_battery  * (battery_pct / 100)
          + w_priority * (priority / 100)
          - w_busy     * busy_penalty

All weights are >= 0; higher score wins. Ties broken by lowest agent_id (stable).
"""

from __future__ import annotations

from dataclasses import dataclass

from swarm_core.geometry import haversine_m
from swarm_core.messages import Bid, FleetState, Geo, MissionTask
from swarm_core.missions import MissionKind


@dataclass(frozen=True)
class AllocatorWeights:
    w_distance: float = 1.0
    w_battery: float = 0.8
    w_priority: float = 0.5
    w_busy: float = 5.0  # large — usually disqualifies busy agents unless mission is urgent


def _mission_geo(mission: MissionTask) -> Geo | None:
    """Best-effort geo extraction from a MissionTask for distance scoring."""

    kind = mission.kind
    if kind in (MissionKind.VERIFY.value, MissionKind.RELAY.value):
        geo = mission.params.get("geo")
        if geo:
            return Geo(**geo)
    if kind in (MissionKind.PATROL.value, MissionKind.COVER.value):
        area = mission.params.get("area") or []
        if area:
            # Use the first point as a coarse representative.
            return Geo(**area[0])
    return None


def score_bid(
    mission: MissionTask,
    fleet_member: FleetState,
    weights: AllocatorWeights = AllocatorWeights(),
) -> tuple[float, dict[str, float]]:
    """Compute (score, reason_breakdown) for one centrally-evaluated candidate."""

    mgeo = _mission_geo(mission)
    distance_m = haversine_m(fleet_member.geo, mgeo) if mgeo else 0.0
    distance_score = weights.w_distance * (1.0 / (1.0 + distance_m / 1000.0))
    battery_score = weights.w_battery * (fleet_member.battery_pct / 100.0)
    priority_score = weights.w_priority * (mission.priority / 100.0)
    busy_penalty = weights.w_busy if fleet_member.current_mission_id else 0.0

    score = distance_score + battery_score + priority_score - busy_penalty
    reason = {
        "distance_m": distance_m,
        "distance_score": distance_score,
        "battery_pct": fleet_member.battery_pct,
        "battery_score": battery_score,
        "priority": float(mission.priority),
        "priority_score": priority_score,
        "busy_penalty": busy_penalty,
    }
    return score, reason


def build_bid(mission: MissionTask, fleet_member: FleetState) -> Bid:
    """Build SWARM's internal candidate-score record for one physical agent.

    The legacy `Bid` name does not imply agent-side negotiation: SwarmOS creates
    this record from canonical fleet state and retains sole winner authority.
    """

    score, reason = score_bid(mission, fleet_member)
    return Bid(
        mission_id=mission.id,
        agent_id=fleet_member.agent_id,
        score=score,
        reason=reason,
    )


def select_winner(bids: list[Bid]) -> Bid | None:
    """Pick the winning centrally-computed candidate. Returns None if empty.

    Tie-break: highest score; if tied, lowest agent_id (lexicographic, stable).
    """

    if not bids:
        return None
    return max(bids, key=lambda b: (b.score, -ord(b.agent_id[0]) if b.agent_id else 0, b.agent_id))


def eligible(fleet: list[FleetState], *, min_battery_pct: float = 25.0) -> list[FleetState]:
    """Filter a fleet to agents currently eligible for central evaluation."""

    from swarm_core.fsm import is_available  # local import to avoid cycles

    return [
        f for f in fleet
        if is_available(f.fsm_state) and f.battery_pct >= min_battery_pct
    ]
