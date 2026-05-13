"""Mission DSL — the vocabulary the orchestrator emits.

Each constructor returns a `MissionTask` with `kind` set to the corresponding
`MissionKind` value and `params` populated with the structured arguments. Adapters
translate these into vendor dialects (DJI KMZ Waypoint Mission, MAVLink
`MISSION_ITEM_INT` sequence, Parrot Olympe `FlightPlan`, etc.).

If a primitive is not natively supported by a vendor, the adapter MUST either:
  1. raise `UnsupportedMission`, OR
  2. decompose it via primitives all vendors support — but NEVER bake
     vendor-specific logic into the orchestrator.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

from swarm_core.messages import Geo, MissionTask, SensorKind, Waypoint, _now


class MissionKind(str, Enum):
    PATROL = "PATROL"
    VERIFY = "VERIFY"
    COVER = "COVER"
    RELAY = "RELAY"
    RTL_DOCK = "RTL_DOCK"


class UnsupportedMission(Exception):
    """Raised by an adapter when the vendor cannot execute a given mission shape."""


# ── Constructors ──────────────────────────────────────────────────────────────


def PATROL(  # noqa: N802 — DSL verb, matches MissionKind.PATROL
    *,
    area: list[Geo],
    cadence_s: float = 1800.0,
    sensors: list[SensorKind] | None = None,
    altitude_m: float = 60.0,
    priority: int = 1,
) -> MissionTask:
    """Scheduled territorial scan over the given polygon."""

    return MissionTask(
        kind=MissionKind.PATROL.value,
        params={
            "area": [g.model_dump() for g in area],
            "cadence_s": cadence_s,
            "sensors": [s.value for s in (sensors or [SensorKind.RGB])],
            "altitude_m": altitude_m,
        },
        priority=priority,
    )


def VERIFY(  # noqa: N802 — DSL verb, matches MissionKind.VERIFY
    *,
    geo: Geo,
    sensors: list[SensorKind] | None = None,
    hover_s: float = 20.0,
    altitude_m: float = 40.0,
    priority: int = 50,
    deadline_s: float | None = 300.0,
) -> MissionTask:
    """Fly to anomaly, multi-sensor capture, classify, confirm or refute.

    High default priority (50) so VERIFY preempts ordinary PATROL.
    """

    deadline = _now() + timedelta(seconds=deadline_s) if deadline_s else None
    return MissionTask(
        kind=MissionKind.VERIFY.value,
        params={
            "geo": geo.model_dump(),
            "sensors": [s.value for s in (sensors or [SensorKind.RGB, SensorKind.THERMAL])],
            "hover_s": hover_s,
            "altitude_m": altitude_m,
        },
        priority=priority,
        deadline=deadline,
    )


def COVER(  # noqa: N802 — DSL verb, matches MissionKind.COVER
    *,
    area: list[Geo],
    fleet_size: int,
    rotation: bool = True,
    altitude_m: float = 60.0,
    priority: int = 10,
) -> MissionTask:
    """Multi-drone area coverage with battery-aware rotation.

    The orchestrator decomposes this into per-agent PATROL slices.
    """

    return MissionTask(
        kind=MissionKind.COVER.value,
        params={
            "area": [g.model_dump() for g in area],
            "fleet_size": fleet_size,
            "rotation": rotation,
            "altitude_m": altitude_m,
        },
        priority=priority,
    )


def RELAY(  # noqa: N802 — DSL verb, matches MissionKind.RELAY
    *,
    geo: Geo,
    altitude_m: float = 80.0,
    duration_s: float = 600.0,
    priority: int = 20,
) -> MissionTask:
    """One drone holds a hover at altitude to act as a comms / observation relay."""

    return MissionTask(
        kind=MissionKind.RELAY.value,
        params={
            "geo": geo.model_dump(),
            "altitude_m": altitude_m,
            "duration_s": duration_s,
        },
        priority=priority,
    )


def RTL_DOCK(*, priority: int = 5) -> MissionTask:  # noqa: N802 — DSL verb, matches MissionKind.RTL_DOCK
    """Return to home dock. Autopilot-side failsafes can also trigger this."""

    return MissionTask(kind=MissionKind.RTL_DOCK.value, params={}, priority=priority)


# ── Helpers ───────────────────────────────────────────────────────────────────


def mission_waypoints(m: MissionTask) -> list[Waypoint]:
    """Extract waypoints from a mission's params (best-effort, for visualization)."""

    kind = m.kind
    if kind == MissionKind.VERIFY.value:
        return [
            Waypoint(
                geo=Geo(**m.params["geo"]),
                hover_s=float(m.params.get("hover_s", 0.0)),
            )
        ]
    if kind == MissionKind.RELAY.value:
        return [
            Waypoint(
                geo=Geo(**m.params["geo"]),
                hover_s=float(m.params.get("duration_s", 0.0)),
            )
        ]
    if kind in (MissionKind.PATROL.value, MissionKind.COVER.value):
        return [Waypoint(geo=Geo(**g)) for g in m.params.get("area", [])]
    return []
