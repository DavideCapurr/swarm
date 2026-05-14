from __future__ import annotations

import pytest

from swarm_core.fsm import Event, IllegalTransition, apply, is_available, is_terminal
from swarm_core.messages import AgentState


def test_happy_path_full_cycle() -> None:
    s = AgentState.DOCKED
    s = apply(s, Event.AWARD_RECEIVED)
    assert s is AgentState.TAKEOFF
    s = apply(s, Event.TAKEOFF_COMPLETE)
    assert s is AgentState.EN_ROUTE
    s = apply(s, Event.WAYPOINT_REACHED)
    assert s is AgentState.ON_STATION
    s = apply(s, Event.MISSION_COMPLETE)
    assert s is AgentState.RTL
    s = apply(s, Event.WAYPOINT_REACHED)
    assert s is AgentState.LANDING
    s = apply(s, Event.LANDED)
    assert s is AgentState.DOCKING
    s = apply(s, Event.DOCKED)
    assert s is AgentState.DOCKED


def test_low_battery_from_en_route_goes_rtl() -> None:
    assert apply(AgentState.EN_ROUTE, Event.LOW_BATTERY) is AgentState.RTL


def test_low_battery_from_on_station_goes_rtl() -> None:
    assert apply(AgentState.ON_STATION, Event.LOW_BATTERY) is AgentState.RTL


def test_divert_mid_flight_stays_en_route() -> None:
    assert apply(AgentState.EN_ROUTE, Event.DIVERT) is AgentState.EN_ROUTE
    assert apply(AgentState.ON_STATION, Event.DIVERT) is AgentState.EN_ROUTE


def test_lost_link_from_en_route_goes_rtl() -> None:
    assert apply(AgentState.EN_ROUTE, Event.LOST_LINK) is AgentState.RTL


def test_error_from_any_state() -> None:
    for state in AgentState:
        assert apply(state, Event.ERROR) is AgentState.ERROR


def test_error_recovers_to_docked() -> None:
    assert apply(AgentState.ERROR, Event.RECOVER) is AgentState.DOCKED


def test_illegal_transition_raises() -> None:
    with pytest.raises(IllegalTransition):
        apply(AgentState.DOCKED, Event.WAYPOINT_REACHED)
    with pytest.raises(IllegalTransition):
        apply(AgentState.LANDING, Event.AWARD_RECEIVED)


def test_is_available_only_docked() -> None:
    assert is_available(AgentState.DOCKED)
    for state in AgentState:
        if state is not AgentState.DOCKED:
            assert not is_available(state)


def test_is_terminal() -> None:
    assert is_terminal(AgentState.DOCKED)
    assert is_terminal(AgentState.OFFLINE)
    assert not is_terminal(AgentState.EN_ROUTE)
