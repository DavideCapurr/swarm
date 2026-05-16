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


# ── Console-facing aggregates (Phase 0+) ───────────────────────────────────────
#
# These types are the view contract between SwarmOS and the Console (frontend).
# They are *projections* of the adapter/bus-level messages above into a single
# denormalized shape per topic. SwarmOS owns the projection; adapters never
# emit these directly. PDF §6 documents the field list.
#
# New models in this section use strict mode (extra="forbid") so callers
# cannot smuggle extra keys past the validator. The older models above keep
# their permissive shape to avoid breaking the adapter ecosystem.

_STRICT = ConfigDict(extra="forbid", strict=False, frozen=False)


class OperatingMode(str, Enum):
    """High-level SwarmOS mode driving rail order, map overlays, and ActionRail."""

    REST = "rest"
    PATROL = "patrol"
    VERIFICATION = "verification"
    ESCALATION = "escalation"
    MAINTENANCE = "maintenance"


class RiskBand(str, Enum):
    """Sector / fleet risk classification. No red — escalation stays amber."""

    LOW = "low"
    ELEVATED = "elevated"
    HIGH = "high"


class ConfidenceBand(str, Enum):
    """Anomaly confidence bands matching voice.py wording."""

    LOW_CONFIDENCE = "low-confidence"
    ELEVATED = "elevated"
    VERIFIED = "verified"


class DockStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class PowerStatus(str, Enum):
    ONLINE = "online"
    DEGRADED = "degraded"
    OFFLINE = "offline"


class SectorState(str, Enum):
    IDLE = "idle"
    COVERED = "covered"
    STALE = "stale"
    BLIND = "blind"
    ANOMALY = "anomaly"


class RiskState(str, Enum):
    """Coarse risk posture for `AwarenessBreakdown.risk_state`."""

    REST = "rest"
    AWARE = "aware"
    ELEVATED = "elevated"


class AnomalyState(str, Enum):
    PENDING = "pending"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"
    MARKED_KNOWN = "marked_known"


class MissionPhase(str, Enum):
    PENDING = "pending"
    BIDDING = "bidding"
    ACCEPTED = "accepted"
    EN_ROUTE = "en_route"
    ON_STATION = "on_station"
    RETURNING = "returning"
    DONE = "done"
    FAILED = "failed"


class EventKind(str, Enum):
    PATROL = "patrol"
    ANOMALY = "anomaly"
    VERIFY = "verify"
    OPERATOR = "operator"
    DOCK = "dock"
    LINK = "link"
    SECTOR = "sector"
    MISSION = "mission"
    SYSTEM = "system"


class OperatorAction(str, Enum):
    """The 8 operator intents from PDF §5.7. Step 1 wires verify/hold/dismiss/return."""

    VERIFY = "verify"
    HOLD_PATROL = "hold_patrol"
    DISMISS = "dismiss"
    RETURN = "return"
    INCREASE_SCAN_FREQ = "increase_scan_freq"
    MARK_KNOWN = "mark_known"
    ESCALATE = "escalate"
    EXPORT_REPORT = "export_report"


class CommandStatus(str, Enum):
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"


class RejectedReason(str, Enum):
    """Closed enum — never echoes user-supplied strings into the audit log."""

    TARGET_NOT_FOUND = "target_not_found"
    INVALID_TARGET_KIND = "invalid_target_kind"
    UNAUTHORIZED = "unauthorized"
    OUTSIDE_GEOFENCE = "outside_geofence"
    BATTERY_TOO_LOW = "battery_too_low"
    LINK_TOO_WEAK = "link_too_weak"
    WEATHER_LOCK = "weather_lock"
    MISSION_CONFLICT = "mission_conflict"
    POLICY_DENY = "policy_deny"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


class Session(BaseModel):
    """Operational session identifier. Server-issued, immutable."""

    model_config = _STRICT
    id: str = Field(default_factory=_new_id)
    label: str  # e.g., "session 014"
    site_id: str = "vineyard-01"
    started_at: datetime = Field(default_factory=_now)
    ts: datetime = Field(default_factory=_now)


class UnitState(BaseModel):
    """Console-facing view of one unit, projected from FleetState + Telemetry."""

    model_config = _STRICT
    agent_id: str
    vendor: str
    model: str
    fsm_state: AgentState
    battery_pct: float = Field(..., ge=0.0, le=100.0)
    geo: Geo
    current_mission_id: str | None = None
    current_sector_id: str | None = None
    link_quality: float = Field(1.0, ge=0.0, le=1.0)
    heading_deg: float = 0.0
    altitude_agl_m: float = 0.0
    dock_id: str | None = None
    ts: datetime = Field(default_factory=_now)


class DockState(BaseModel):
    """Aggregated dock health + weather + scheduling state."""

    model_config = _STRICT
    dock_id: str
    status: DockStatus
    units_docked: int = Field(0, ge=0)
    units_total: int = Field(0, ge=0)
    slots_available: int = Field(0, ge=0)
    slots_charging: int = Field(0, ge=0)
    power_status: PowerStatus = PowerStatus.ONLINE
    weather_lock: bool = False
    wind_mps: float | None = None
    visibility_km: float | None = None
    temp_c: float | None = None
    next_patrol_at: datetime | None = None
    # Phase 3: server marks the canonical dock the Console reads — no more
    # client-side `pickPrimaryDock` heuristic.
    primary: bool = False
    ts: datetime = Field(default_factory=_now)


class Sector(BaseModel):
    """A polygon of territory under awareness, with coverage + risk metadata."""

    model_config = _STRICT
    id: str
    label: str
    polygon: list[Geo] = Field(..., min_length=3)
    centroid: Geo
    state: SectorState = SectorState.IDLE
    last_visited_at: datetime | None = None
    last_visited_by: str | None = None
    pending_anomaly_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    risk_band: RiskBand = RiskBand.LOW
    ts: datetime = Field(default_factory=_now)


class AwarenessBreakdown(BaseModel):
    """Server-computed territorial awareness score + factor decomposition.

    Phase 3 carries the operating mode and active verifier here so the Console
    has a single truth frame for top-level state — replacing the Phase 2
    client-side `deriveOperatingMode` / `deriveVerifier` heuristics.
    """

    model_config = _STRICT
    score: float = Field(..., ge=0.0, le=100.0)
    factors: dict[str, float] = Field(default_factory=dict)
    blind_spot_sectors: list[str] = Field(default_factory=list)
    stale_sectors: list[str] = Field(default_factory=list)
    risk_state: RiskState = RiskState.REST
    mode: OperatingMode = OperatingMode.REST
    verifying_agent: str | None = None
    ts: datetime = Field(default_factory=_now)


class MissionView(BaseModel):
    """Console-facing projection of an in-flight or scheduled mission."""

    model_config = _STRICT
    id: str
    kind: str  # MissionKind value — keep as str for forward-compat with vendor-specific kinds
    assigned_agent: str | None = None
    sector_id: str | None = None
    phase: MissionPhase = MissionPhase.PENDING
    progress_pct: float = Field(0.0, ge=0.0, le=100.0)
    eta_s: float | None = None
    waypoints: list[Geo] = Field(default_factory=list)
    track: list[Geo] = Field(default_factory=list)  # recent observed positions
    ts: datetime = Field(default_factory=_now)


class AnomalyView(BaseModel):
    """Console-facing anomaly with verification state machine."""

    model_config = _STRICT
    id: str
    kind: AnomalyKind
    geo: Geo
    sector_id: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    band: ConfidenceBand
    state: AnomalyState = AnomalyState.PENDING
    detected_at: datetime = Field(default_factory=_now)
    detected_by: str | None = None
    verifying_agent: str | None = None
    ts: datetime = Field(default_factory=_now)


class Event(BaseModel):
    """Typed timeline entry for the Console EventFeed."""

    model_config = _STRICT
    id: str = Field(default_factory=_new_id)
    kind: EventKind
    ts: datetime = Field(default_factory=_now)
    sector_id: str | None = None
    agent_id: str | None = None
    mission_id: str | None = None
    anomaly_id: str | None = None
    dock_id: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    body: str = ""  # Confidence-bound copy — never user-controlled
    action_label: str | None = None


class OperatorCommand(BaseModel):
    """The audit record for an operator intent submitted via the Console.

    Phase 3 extends the lifecycle with `accepted_at` + `in_flight_at` so the
    Console can render a timeline of every command. The status machine flows
    `submitted → accepted → in_flight → completed | rejected | timed_out`.
    """

    model_config = _STRICT
    id: str = Field(default_factory=_new_id)
    action: OperatorAction
    target: str  # opaque to the model; the command_bus validates by kind:identifier
    operator_id: str
    submitted_at: datetime = Field(default_factory=_now)
    accepted_at: datetime | None = None
    in_flight_at: datetime | None = None
    status: CommandStatus = CommandStatus.SUBMITTED
    rejected_reason: RejectedReason | None = None
    completed_at: datetime | None = None
    mission_id: str | None = None  # the mission the command spawned, if any
    ts: datetime = Field(default_factory=_now)
