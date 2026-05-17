"""High-level SwarmOS operating mode rules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from swarm_core.messages import AgentState, AnomalyState, OperatingMode


class _StateLike(Protocol):
    @property
    def units(self) -> Mapping[str, Any]: ...

    @property
    def docks(self) -> Mapping[str, Any]: ...

    @property
    def anomalies(self) -> Mapping[str, Any]: ...


def compute_mode(state: _StateLike) -> OperatingMode:
    """Pure mode computation from the current state snapshot."""

    units = list(state.units.values())
    docks = list(state.docks.values())
    anomalies = list(state.anomalies.values())

    dock_attention = False
    for dock in docks:
        status = getattr(dock, "status", None)
        status_value = getattr(status, "value", None)
        if status_value in {"degraded", "offline", "maintenance"}:
            dock_attention = True
            break

    if any(
        getattr(unit, "fsm_state", None) in {AgentState.OFFLINE, AgentState.ERROR}
        or float(getattr(unit, "battery_pct", 100.0)) < 20.0
        or float(getattr(unit, "link_quality", 1.0)) < 0.35
        for unit in units
    ) or dock_attention:
        return OperatingMode.MAINTENANCE

    if any(getattr(anomaly, "state", None) == AnomalyState.VERIFIED for anomaly in anomalies):
        return OperatingMode.ESCALATION

    if any(
        getattr(anomaly, "state", None) in {AnomalyState.PENDING, AnomalyState.VERIFYING}
        for anomaly in anomalies
    ):
        return OperatingMode.VERIFICATION

    if any(getattr(unit, "fsm_state", None) != AgentState.DOCKED for unit in units):
        return OperatingMode.PATROL

    return OperatingMode.REST
