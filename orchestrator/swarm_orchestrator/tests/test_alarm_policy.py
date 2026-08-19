from __future__ import annotations

from swarm_core.messages import Anomaly, AnomalyKind, Geo
from swarm_core.missions import COOPERATIVE_VERIFY_KIND, MissionKind

from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy


def _alarm(confidence: float) -> Anomaly:
    return Anomaly(
        id="alarm-fixed",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0, lon=9.0),
        confidence=confidence,
    )


def test_same_alarm_shape_changes_demand_only_from_world_state() -> None:
    policy = AlarmResponsePolicy(
        cooperative_threshold=0.80,
        high_confidence_threshold=0.93,
        max_team_size=3,
    )

    low = policy.objective_for(_alarm(0.70))
    elevated = policy.objective_for(_alarm(0.85))
    high = policy.objective_for(_alarm(0.97))

    assert low.kind == MissionKind.VERIFY.value
    assert elevated.kind == COOPERATIVE_VERIFY_KIND
    assert elevated.params["team_size"] == 2
    assert high.kind == COOPERATIVE_VERIFY_KIND
    assert high.params["team_size"] == 3
    assert high.params["minimum_capacity"] == 2
    assert high.params["alarm_id"] == "alarm-fixed"
    assert high.params["demand_reason"] == "HIGH_CONFIDENCE_MULTI_EXECUTOR"


def test_policy_never_contains_executor_identity() -> None:
    objective = AlarmResponsePolicy().objective_for(_alarm(0.97))
    serialized = objective.model_dump_json()

    assert "mav-" not in serialized
    assert "agent-" not in serialized
    assert objective.assigned_agent is None
