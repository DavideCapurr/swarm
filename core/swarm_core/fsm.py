"""Agent finite-state machine — SWARM-side view of a drone's lifecycle.

This FSM does NOT replace the vendor autopilot's internal state machine. It is
how the orchestrator reasons about what an agent is doing right now and what
transitions are legal in response to events (mission award, anomaly, low battery,
lost link, mid-flight divert).

The FSM is pure: it operates on `AgentState` enums and `Event` payloads. The
adapter is responsible for actually flying the drone; the FSM tells the
orchestrator and dashboard *what state we believe we are in*.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from swarm_core.messages import AgentState


class Event(str, Enum):
    AWARD_RECEIVED = "AWARD_RECEIVED"
    TAKEOFF_COMPLETE = "TAKEOFF_COMPLETE"
    WAYPOINT_REACHED = "WAYPOINT_REACHED"
    MISSION_COMPLETE = "MISSION_COMPLETE"
    DIVERT = "DIVERT"
    RTL_REQUESTED = "RTL_REQUESTED"
    LOW_BATTERY = "LOW_BATTERY"
    LOST_LINK = "LOST_LINK"
    LANDED = "LANDED"
    DOCKED = "DOCKED"
    ERROR = "ERROR"
    RECOVER = "RECOVER"


@dataclass(frozen=True)
class Transition:
    src: AgentState
    event: Event
    dst: AgentState


# Authoritative transition table. Anything not listed here is an illegal transition.
_TRANSITIONS: tuple[Transition, ...] = (
    Transition(AgentState.DOCKED, Event.AWARD_RECEIVED, AgentState.TAKEOFF),
    Transition(AgentState.TAKEOFF, Event.TAKEOFF_COMPLETE, AgentState.EN_ROUTE),
    Transition(AgentState.EN_ROUTE, Event.WAYPOINT_REACHED, AgentState.ON_STATION),
    Transition(AgentState.EN_ROUTE, Event.DIVERT, AgentState.EN_ROUTE),
    Transition(AgentState.EN_ROUTE, Event.RTL_REQUESTED, AgentState.RTL),
    Transition(AgentState.EN_ROUTE, Event.LOW_BATTERY, AgentState.RTL),
    Transition(AgentState.EN_ROUTE, Event.LOST_LINK, AgentState.RTL),
    Transition(AgentState.ON_STATION, Event.MISSION_COMPLETE, AgentState.RTL),
    Transition(AgentState.ON_STATION, Event.DIVERT, AgentState.EN_ROUTE),
    Transition(AgentState.ON_STATION, Event.RTL_REQUESTED, AgentState.RTL),
    Transition(AgentState.ON_STATION, Event.LOW_BATTERY, AgentState.RTL),
    Transition(AgentState.RTL, Event.WAYPOINT_REACHED, AgentState.LANDING),
    Transition(AgentState.LANDING, Event.LANDED, AgentState.DOCKING),
    Transition(AgentState.DOCKING, Event.DOCKED, AgentState.DOCKED),
    # Error pathway from any state — handled below in `apply()`.
    Transition(AgentState.ERROR, Event.RECOVER, AgentState.DOCKED),
)


_TRANSITION_INDEX: dict[tuple[AgentState, Event], AgentState] = {
    (t.src, t.event): t.dst for t in _TRANSITIONS
}


class IllegalTransition(Exception):
    """Raised when an event is not valid from the current state."""


def apply(state: AgentState, event: Event) -> AgentState:
    """Compute the next state. Raises `IllegalTransition` if the event is not allowed.

    ERROR transitions: from ANY non-DOCKED state, an `ERROR` event moves to ERROR.
    From DOCKED an ERROR is also valid (offline dock).
    """

    if event is Event.ERROR:
        return AgentState.ERROR
    key = (state, event)
    if key not in _TRANSITION_INDEX:
        raise IllegalTransition(f"{event.value} from {state.value}")
    return _TRANSITION_INDEX[key]


def is_terminal(state: AgentState) -> bool:
    """A state is terminal w.r.t. a mission lifecycle when the agent is back at the dock."""

    return state in (AgentState.DOCKED, AgentState.OFFLINE)


def is_available(state: AgentState) -> bool:
    """True if the agent can bid for a new mission."""

    return state is AgentState.DOCKED
