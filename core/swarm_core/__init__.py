"""SWARM OS core domain layer — pure Python, no I/O.

This package is the canonical definition of:
- Domain messages (Telemetry, Anomaly, MissionTask, FleetState, Bid, Award).
- Mission DSL (PATROL, VERIFY, COVER, RELAY, RTL_DOCK).
- Agent finite-state machine.
- Auction-based mission allocator (Contract Net).
- Geometry primitives (waypoints, distance, coverage tiling).
"""

from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    Award,
    Bid,
    CaptureResult,
    FleetState,
    Geo,
    MissionProgress,
    MissionTask,
    SensorKind,
    Telemetry,
    Waypoint,
)
from swarm_core.missions import (
    COVER,
    PATROL,
    RELAY,
    RTL_DOCK,
    VERIFY,
    MissionKind,
)

__all__ = [
    "COVER",
    "PATROL",
    "RELAY",
    "RTL_DOCK",
    "VERIFY",
    "AgentState",
    "Anomaly",
    "AnomalyKind",
    "Award",
    "Bid",
    "CaptureResult",
    "FleetState",
    "Geo",
    "MissionKind",
    "MissionProgress",
    "MissionTask",
    "SensorKind",
    "Telemetry",
    "Waypoint",
]
