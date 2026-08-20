"""Mission DSL — the vocabulary the orchestrator emits.

Each constructor returns a `MissionTask` with `kind` and structured `params`.
Adapters translate executable primitives into vendor dialects (DJI KMZ,
MAVLink mission items, Parrot FlightPlan, etc.).

`COOPERATIVE_VERIFY` is deliberately *not* a `MissionKind`: it is an
orchestration-only parent objective. Keeping it outside the executable enum
means adapters that allowlist `MissionKind` fail closed if the parent is ever
sent to them by mistake. `COVER` is the older orchestration-level kind and is
explicitly rejected by physical adapters before SwarmOS decomposes it.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum

from swarm_core.messages import Geo, MissionTask, SensorKind, Waypoint, _now

COOPERATIVE_VERIFY_KIND = "COOPERATIVE_VERIFY"


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
    """Fly to anomaly, multi-sensor capture, classify, confirm or refute."""

    deadline = _now() + timedelta(seconds=deadline_s) if deadline_s else None
    return MissionTask(
        kind=MissionKind.VERIFY.value,
        params={
            "geo": geo.model_dump(),
            "sensors": [
                s.value for s in (sensors or [SensorKind.RGB, SensorKind.THERMAL])
            ],
            "hover_s": hover_s,
            "altitude_m": altitude_m,
        },
        priority=priority,
        deadline=deadline,
    )


def COOPERATIVE_VERIFY(  # noqa: N802 — orchestration DSL verb
    *,
    geo: Geo,
    team_size: int = 3,
    roles: list[str] | None = None,
    hover_s: float = 20.0,
    base_altitude_m: float = 40.0,
    altitude_step_m: float = 15.0,
    priority: int = 80,
    minimum_capacity: int = 1,
) -> MissionTask:
    """One logical verification objective requiring multiple physical agents.

    This parent task is SwarmOS-only. `ExecutionGroupOrchestrator` centrally
    selects the members and decomposes the objective into individual VERIFY
    child missions. Physical adapters must never execute this parent directly.

    ``minimum_capacity`` is the lowest degraded strength SwarmOS may accept
    while reconciliation searches for the desired ``team_size``. Cooperative
    verification itself is not preemptible by default.
    """

    if team_size < 2:
        raise ValueError("COOPERATIVE_VERIFY team_size must be >= 2")
    if roles is not None and len(roles) > team_size:
        raise ValueError("COOPERATIVE_VERIFY roles cannot exceed team_size")
    if minimum_capacity < 1 or minimum_capacity > team_size:
        raise ValueError("minimum_capacity must be between 1 and team_size")
    return MissionTask(
        kind=COOPERATIVE_VERIFY_KIND,
        params={
            "geo": geo.model_dump(),
            "team_size": team_size,
            "roles": list(roles or []),
            "hover_s": hover_s,
            "base_altitude_m": base_altitude_m,
            "altitude_step_m": altitude_step_m,
            "minimum_capacity": minimum_capacity,
            "acceptable_degradation": minimum_capacity < team_size,
            "preemptible": False,
            "preemption_policy": "never",
        },
        priority=priority,
    )


def COVER(  # noqa: N802 — DSL verb, matches MissionKind.COVER
    *,
    area: list[Geo],
    fleet_size: int,
    rotation: bool = True,
    altitude_m: float = 60.0,
    priority: int = 10,
    minimum_capacity: int | None = None,
    preemptible: bool = False,
) -> MissionTask:
    """Multi-drone area coverage with explicit degradation policy.

    SwarmOS decomposes this parent into per-agent PATROL slices and owns every
    assignment/replacement. ``fleet_size`` is desired strength. By default the
    objective is non-preemptible and its minimum equals desired strength, which
    preserves the historical behaviour. A caller may explicitly lower
    ``minimum_capacity`` and set ``preemptible=True`` to allow a higher-priority
    objective to borrow capacity without dropping this sweep below its floor.
    """

    if fleet_size < 1:
        raise ValueError("COVER fleet_size must be >= 1")
    minimum = fleet_size if minimum_capacity is None else minimum_capacity
    if minimum < 1 or minimum > fleet_size:
        raise ValueError("minimum_capacity must be between 1 and fleet_size")

    return MissionTask(
        kind=MissionKind.COVER.value,
        params={
            "area": [g.model_dump() for g in area],
            "fleet_size": fleet_size,
            "rotation": rotation,
            "altitude_m": altitude_m,
            "minimum_capacity": minimum,
            "acceptable_degradation": minimum < fleet_size,
            "preemptible": preemptible,
            "preemption_policy": "higher_priority" if preemptible else "never",
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


def RTL_DOCK(  # noqa: N802 — DSL verb, matches MissionKind.RTL_DOCK
    *, priority: int = 5
) -> MissionTask:
    """Return to home dock. Autopilot-side failsafes can also trigger this."""

    return MissionTask(kind=MissionKind.RTL_DOCK.value, params={}, priority=priority)


# ── Helpers ───────────────────────────────────────────────────────────────────


def mission_waypoints(m: MissionTask) -> list[Waypoint]:
    """Extract waypoints from an executable mission (best-effort visualization)."""

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
