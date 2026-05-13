"""DroneAdapter Protocol — the interoperability moat.

Every vendor adapter (DJI Cloud, MAVLink, Autel, Parrot, Skydio, …) implements
this Protocol. The orchestrator NEVER imports a concrete adapter — it works with
`DroneAdapter` instances retrieved through `AdapterRegistry`.

Discipline rules (ADR-0003):
1. Vendor-specific types NEVER leak past `adapters/<vendor>/`.
2. Mission DSL primitives must be expressible by every vendor's autopilot. If
   a primitive is unsupported, the adapter raises `UnsupportedMission`.
3. Telemetry minimum 1 Hz; video best-effort.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from swarm_core.messages import (
    CaptureResult,
    Geo,
    MissionProgress,
    MissionTask,
    SensorKind,
    Telemetry,
    Waypoint,
)


@dataclass(frozen=True)
class Capabilities:
    """What sensors and payloads this airframe carries."""

    sensors: frozenset[SensorKind] = field(default_factory=frozenset)
    has_rtk: bool = False
    has_payload_drop: bool = False
    has_obstacle_avoidance: bool = False
    max_flight_time_s: float = 1800.0
    max_speed_mps: float = 15.0
    max_altitude_m: float = 120.0


@dataclass(frozen=True)
class Failsafes:
    """Autopilot-side safety behaviors the adapter declares it will honor."""

    lost_link_rtl: bool = True
    low_battery_rtl: bool = True
    low_battery_threshold_pct: float = 20.0
    geofence_rtl: bool = True


@dataclass
class HealthReport:
    online: bool
    battery_pct: float
    link_quality: float
    last_telemetry_age_s: float | None
    notes: str = ""


@dataclass
class VideoFrame:
    """One video frame. The `payload` is opaque bytes (JPEG, H.264 NAL, …)."""

    agent_id: str
    ts_ns: int
    width: int
    height: int
    encoding: str  # "jpeg" | "h264" | "raw_rgb"
    payload: bytes


@dataclass(frozen=True)
class Polygon:
    """Closed polygon expressed as a list of geo-coordinates."""

    points: tuple[Geo, ...]


@runtime_checkable
class DroneAdapter(Protocol):
    """The contract between SWARM OS and a real (or simulated) drone."""

    # ── identity & capability ────────────────────────────────────────────────
    vendor: str
    model: str
    agent_id: str
    capabilities: Capabilities
    autopilot_failsafes: Failsafes

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def health(self) -> HealthReport: ...

    # ── safety envelope ──────────────────────────────────────────────────────
    async def set_safety(
        self,
        geofence: Polygon,
        max_alt_m: float,
        rtl_battery_pct: int,
    ) -> None: ...

    # ── mission-level autonomy ───────────────────────────────────────────────
    def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:
        """Run the mission. The async iterator yields progress until the mission
        finishes, fails, or is cancelled by `cancel_mission()`."""
        ...

    async def pause_mission(self) -> None: ...
    async def resume_mission(self) -> None: ...
    async def cancel_mission(self) -> None: ...

    async def divert(self, new_waypoint: Waypoint) -> None:
        """Mid-flight re-task: switch destination without aborting the mission."""
        ...

    async def request_capture(self, sensor: SensorKind) -> CaptureResult: ...

    # ── streams ──────────────────────────────────────────────────────────────
    def stream_telemetry(self) -> AsyncIterator[Telemetry]: ...
    def stream_video(self) -> AsyncIterator[VideoFrame]: ...


# ── Registry ──────────────────────────────────────────────────────────────────


class AdapterRegistry:
    """Keeps track of all live adapter instances by `agent_id`.

    The orchestrator uses this to look up adapters at runtime without ever
    knowing the concrete vendor class.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, DroneAdapter] = {}

    def register(self, adapter: DroneAdapter) -> None:
        if adapter.agent_id in self._by_id:
            raise ValueError(f"Adapter already registered: {adapter.agent_id}")
        self._by_id[adapter.agent_id] = adapter

    def unregister(self, agent_id: str) -> None:
        self._by_id.pop(agent_id, None)

    def get(self, agent_id: str) -> DroneAdapter:
        return self._by_id[agent_id]

    def all(self) -> list[DroneAdapter]:
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)
