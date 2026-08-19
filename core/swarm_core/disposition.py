"""Deterministic SwarmOS disposition geometry and decision truth.

The renderer must not decide how a swarm widens or contracts. Given an
objective point and the active role set, SwarmOS derives station geometry from
membership. The orchestration layer publishes :class:`DispositionDecision`
frames so the Console can render the decision without recreating it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from swarm_core.messages import Geo

_M_PER_DEG = 111_000.0


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class DispositionSlot:
    role: str
    geo: Geo
    east_m: float
    north_m: float


@dataclass(frozen=True)
class ObjectiveDisposition:
    center: Geo
    active_members: int
    radius_m: float
    slots: tuple[DispositionSlot, ...]


class DispositionAssignment(BaseModel):
    """One physical executor assigned to one SwarmOS-computed station slot."""

    group_id: str
    agent_id: str
    role: str
    mission_id: str
    geo: Geo


class DispositionDecision(BaseModel):
    """Published disposition truth for one logical objective."""

    objective_mission_id: str
    revision: int = Field(ge=1)
    reason: str
    center: Geo
    active_members: int = Field(ge=0)
    radius_m: float = Field(ge=0.0)
    assignments: list[DispositionAssignment] = Field(default_factory=list)
    ts: datetime = Field(default_factory=_now)


def _offset(center: Geo, east_m: float, north_m: float) -> Geo:
    dlat = north_m / _M_PER_DEG
    cos_lat = max(0.01, math.cos(math.radians(center.lat)))
    dlon = east_m / (_M_PER_DEG * cos_lat)
    return Geo(
        lat=center.lat + dlat,
        lon=center.lon + dlon,
        alt_m=center.alt_m,
    )


def compute_disposition(
    center: Geo,
    roles: list[str] | tuple[str, ...],
    *,
    base_radius_m: float = 14.0,
    radius_step_m: float = 8.0,
) -> ObjectiveDisposition:
    """Compute station geometry solely from objective center + active roles."""

    ordered = tuple(roles)
    count = len(ordered)
    if count < 1:
        return ObjectiveDisposition(
            center=center,
            active_members=0,
            radius_m=0.0,
            slots=(),
        )

    radius = base_radius_m + radius_step_m * max(0, count - 1)
    # Start north and rotate clockwise. Role order comes from SwarmOS-owned
    # composition; no aircraft id participates in geometry.
    slots: list[DispositionSlot] = []
    for index, role in enumerate(ordered):
        angle = 2.0 * math.pi * index / count
        east = radius * math.sin(angle)
        north = radius * math.cos(angle)
        slots.append(
            DispositionSlot(
                role=role,
                geo=_offset(center, east, north),
                east_m=east,
                north_m=north,
            )
        )
    return ObjectiveDisposition(
        center=center,
        active_members=count,
        radius_m=radius,
        slots=tuple(slots),
    )


__all__ = (
    "DispositionAssignment",
    "DispositionDecision",
    "DispositionSlot",
    "ObjectiveDisposition",
    "compute_disposition",
)
