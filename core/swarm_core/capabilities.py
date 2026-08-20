"""Capability primitives for SwarmOS physical capacity composition.

Capabilities are SwarmOS planning concepts. They describe what capacity an
agent can provide; they do not grant agents mission authority.
"""

from __future__ import annotations

from enum import Enum


class Capability(str, Enum):
    THERMAL_OBSERVATION = "thermal_observation"
    WIDE_AREA_OBSERVATION = "wide_area_observation"
    RELAY = "relay"
    VISUAL_OBSERVATION = "visual_observation"


def has_required_capabilities(provider: set[str], required: set[str]) -> bool:
    """Return whether one provider satisfies a required capability set."""

    return required.issubset(provider)
