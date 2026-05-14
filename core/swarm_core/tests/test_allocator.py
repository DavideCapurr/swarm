from __future__ import annotations

from swarm_core.allocator import (
    AllocatorWeights,
    build_bid,
    eligible,
    score_bid,
    select_winner,
)
from swarm_core.messages import AgentState, Bid, FleetState, Geo
from swarm_core.missions import RTL_DOCK, VERIFY


def _fleet_member(
    *,
    agent_id: str,
    lat: float,
    lon: float,
    battery: float = 90.0,
    state: AgentState = AgentState.DOCKED,
    mission_id: str | None = None,
) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="simulated",
        model="x500",
        fsm_state=state,
        battery_pct=battery,
        geo=Geo(lat=lat, lon=lon),
        current_mission_id=mission_id,
    )


def test_closer_agent_outscores_farther_agent_all_else_equal() -> None:
    m = VERIFY(geo=Geo(lat=45.000, lon=10.000))
    near = _fleet_member(agent_id="near", lat=45.001, lon=10.001)
    far = _fleet_member(agent_id="far", lat=45.050, lon=10.050)
    s_near, _ = score_bid(m, near)
    s_far, _ = score_bid(m, far)
    assert s_near > s_far


def test_higher_battery_outscores_lower_when_distance_equal() -> None:
    m = VERIFY(geo=Geo(lat=45.0, lon=10.0))
    a = _fleet_member(agent_id="a", lat=45.001, lon=10.0, battery=95.0)
    b = _fleet_member(agent_id="b", lat=45.001, lon=10.0, battery=60.0)
    assert score_bid(m, a)[0] > score_bid(m, b)[0]


def test_busy_agent_gets_heavy_penalty() -> None:
    m = VERIFY(geo=Geo(lat=45.0, lon=10.0))
    busy = _fleet_member(agent_id="busy", lat=45.001, lon=10.0, mission_id="m_other")
    idle = _fleet_member(agent_id="idle", lat=45.001, lon=10.0)
    s_busy, _ = score_bid(m, busy)
    s_idle, _ = score_bid(m, idle)
    assert s_idle - s_busy >= 4.0  # at least the busy penalty


def test_priority_increases_score() -> None:
    base = VERIFY(geo=Geo(lat=45.0, lon=10.0), priority=10)
    emergency = VERIFY(geo=Geo(lat=45.0, lon=10.0), priority=100)
    a = _fleet_member(agent_id="a", lat=45.0, lon=10.0)
    assert score_bid(emergency, a)[0] > score_bid(base, a)[0]


def test_select_winner_picks_highest_score() -> None:
    bids = [
        Bid(mission_id="m", agent_id="a", score=1.0),
        Bid(mission_id="m", agent_id="b", score=2.5),
        Bid(mission_id="m", agent_id="c", score=2.0),
    ]
    winner = select_winner(bids)
    assert winner is not None
    assert winner.agent_id == "b"


def test_select_winner_returns_none_when_no_bids() -> None:
    assert select_winner([]) is None


def test_build_bid_includes_reason_breakdown() -> None:
    m = VERIFY(geo=Geo(lat=45.0, lon=10.0))
    a = _fleet_member(agent_id="a", lat=45.001, lon=10.0)
    bid = build_bid(m, a)
    assert bid.agent_id == "a"
    assert bid.mission_id == m.id
    assert "distance_m" in bid.reason
    assert "battery_score" in bid.reason


def test_eligible_filters_out_busy_or_drained_agents() -> None:
    fleet = [
        _fleet_member(agent_id="ok", lat=0, lon=0, battery=80.0),
        _fleet_member(agent_id="low", lat=0, lon=0, battery=10.0),
        _fleet_member(agent_id="busy", lat=0, lon=0, state=AgentState.EN_ROUTE),
    ]
    out = eligible(fleet)
    assert [f.agent_id for f in out] == ["ok"]


def test_custom_weights_change_ranking() -> None:
    """Sanity: weights bias the result. With distance weight=0, a far agent
    with higher battery wins over a near agent with low battery."""

    m = VERIFY(geo=Geo(lat=45.0, lon=10.0))
    near_low = _fleet_member(agent_id="a", lat=45.0, lon=10.0, battery=30.0)
    far_high = _fleet_member(agent_id="b", lat=45.05, lon=10.05, battery=99.0)

    weights = AllocatorWeights(w_distance=0.0, w_battery=2.0, w_priority=0.0, w_busy=0.0)
    s_near, _ = score_bid(m, near_low, weights)
    s_far, _ = score_bid(m, far_high, weights)
    assert s_far > s_near


def test_rtl_dock_mission_works_without_geo() -> None:
    """RTL_DOCK has no geo in params — scoring must still produce a number."""

    m = RTL_DOCK()
    a = _fleet_member(agent_id="a", lat=45.0, lon=10.0)
    s, _ = score_bid(m, a)
    assert isinstance(s, float)
