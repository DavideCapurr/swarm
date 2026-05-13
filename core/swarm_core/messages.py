"""Domain messages exchanged across the SWARM OS bus.

All messages are Pydantic v2 models. They are transport-agnostic: today they ride
on Redis pub/sub via JSON; tomorrow they could ride on NATS, MQTT, or be mapped to
ROS2 `.msg` definitions. The shape stays.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


# ── Primitives ─────────────────────────────────────────────────────────────────


class Geo(BaseModel):
    """WGS84 geo-coordinate. Altitude in meters AGL (above ground level)."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    alt_m: float = 0.0


class Waypoint(BaseModel):
    """A point a drone is asked to reach, with optional hover and speed hints."""

    geo: Geo
    hover_s: float = 0.0
    speed_mps: float | None = None


class Attitude(BaseModel):
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0


# ── Enums ──────────────────────────────────────────────────────────────────────


class AgentState(str, Enum):
    """FSM states for a drone seen from SWARM OS (not the autopilot's internal states)."""

    DOCKED = "DOCKED"
    TAKEOFF = "TAKEOFF"
    EN_ROUTE = "EN_ROUTE"
    ON_STATION = "ON_STATION"
    RTL = "RTL"
    LANDING = "LANDING"
    DOCKING = "DOCKING"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class AnomalyKind(str, Enum):
    SMOKE = "SMOKE"
    FIRE = "FIRE"
    HEAT_SPOT = "HEAT_SPOT"
    INTRUSION = "INTRUSION"
    UNKNOWN = "UNKNOWN"


class SensorKind(str, Enum):
    RGB = "RGB"
    THERMAL = "THERMAL"
    MULTISPECTRAL = "MULTISPECTRAL"
    LIDAR = "LIDAR"


# ── Messages ───────────────────────────────────────────────────────────────────


class Telemetry(BaseModel):
    """High-rate position/status from a single agent."""

    model_config = ConfigDict(frozen=True)

    agent_id: str
    ts: datetime = Field(default_factory=_now)
    geo: Geo
    attitude: Attitude = Field(default_factory=Attitude)
    velocity_mps: float = 0.0
    battery_pct: float = Field(100.0, ge=0.0, le=100.0)
    link_quality: float = Field(1.0, ge=0.0, le=1.0)


class Anomaly(BaseModel):
    """A potential event detected somewhere in the territory."""

    id: str = Field(default_factory=_new_id)
    kind: AnomalyKind
    geo: Geo
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    source_agent: str | None = None
    ts: datetime = Field(default_factory=_now)
    verified: bool = False


class MissionTask(BaseModel):
    """A unit of work the orchestrator dispatches to an agent."""

    id: str = Field(default_factory=_new_id)
    kind: str  # one of MissionKind values — see swarm_core.missions
    params: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0  # higher wins ties; emergency missions use 100+
    assigned_agent: str | None = None
    deadline: datetime | None = None
    ts: datetime = Field(default_factory=_now)


class MissionProgress(BaseModel):
    """Heartbeat from an adapter while a mission executes."""

    mission_id: str
    phase: str  # "BIDDING" | "EN_ROUTE" | "ON_STATION" | "RETURNING" | "DONE" | "FAILED"
    progress_pct: float = Field(0.0, ge=0.0, le=100.0)
    eta_s: float | None = None
    captured_artifacts: list[str] = Field(default_factory=list)
    error: str | None = None
    ts: datetime = Field(default_factory=_now)


class FleetState(BaseModel):
    """Aggregated view of a single agent — published by the orchestrator."""

    agent_id: str
    vendor: str
    model: str
    fsm_state: AgentState
    battery_pct: float
    geo: Geo
    current_mission_id: str | None = None
    link_quality: float = 1.0
    ts: datetime = Field(default_factory=_now)


class Bid(BaseModel):
    """An agent's bid for a mission. Higher score = better fit."""

    mission_id: str
    agent_id: str
    score: float
    reason: dict[str, float] = Field(default_factory=dict)  # explains the score
    ts: datetime = Field(default_factory=_now)


class Award(BaseModel):
    """Orchestrator's auction result."""

    mission_id: str
    winner_agent_id: str
    score: float
    ts: datetime = Field(default_factory=_now)


class CaptureResult(BaseModel):
    """The result of `request_capture(sensor)` against an adapter."""

    sensor: SensorKind
    uri: str  # local path, S3 URI, or stream id
    geo: Geo
    ts: datetime = Field(default_factory=_now)
    classification: AnomalyKind | None = None
    confidence: float | None = None
