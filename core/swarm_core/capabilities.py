"""Capability primitives for SwarmOS physical capacity composition.

Capabilities are SwarmOS planning concepts. They describe what capacity an
agent can provide; they do not grant agents mission authority.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

from swarm_core.messages import SensorKind


class Capability(str, Enum):
    THERMAL_OBSERVATION = "thermal_observation"
    WIDE_AREA_OBSERVATION = "wide_area_observation"
    RELAY = "relay"
    VISUAL_OBSERVATION = "visual_observation"


def has_required_capabilities(provider: set[str], required: set[str]) -> bool:
    """Return whether one provider satisfies a required capability set."""

    return required.issubset(provider)


def planning_capabilities_from_sensors(sensors: Iterable[SensorKind]) -> set[str]:
    """Project physical sensor facts into generic SwarmOS planning capacity.

    This is intentionally conservative. A sensor can prove an observation
    capability; platform-level capabilities such as relay or wide-area coverage
    require their own canonical declaration and are not guessed here.
    """

    out: set[str] = set()
    for sensor in sensors:
        if sensor is SensorKind.RGB:
            out.add(Capability.VISUAL_OBSERVATION.value)
        elif sensor is SensorKind.THERMAL:
            out.add(Capability.THERMAL_OBSERVATION.value)
    return out
