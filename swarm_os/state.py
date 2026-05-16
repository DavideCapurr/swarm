"""Authoritative in-memory SwarmOS state for Phase 1."""

from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime

from swarm_core.messages import (
    AnomalyView,
    AwarenessBreakdown,
    DockState,
    DockStatus,
    Event,
    Geo,
    MissionView,
    OperatingMode,
    OperatorCommand,
    PowerStatus,
    RiskState,
    Sector,
    Session,
    UnitState,
)

from swarm_os.sectors import default_sector_grid

DEFAULT_DOCK_ID = "dock-langhe-01"
DEFAULT_SESSION_LABEL = "session 014"
VINEYARD_CENTER = Geo(lat=44.7000, lon=8.0300, alt_m=0.0)


def now_utc() -> datetime:
    return datetime.now(UTC)


@dataclass
class SwarmState:
    """Live state projected from simulator/orchestrator messages."""

    units: dict[str, UnitState] = field(default_factory=dict)
    docks: dict[str, DockState] = field(default_factory=dict)
    sectors: dict[str, Sector] = field(default_factory=dict)
    missions: dict[str, MissionView] = field(default_factory=dict)
    anomalies: dict[str, AnomalyView] = field(default_factory=dict)
    tracks: dict[str, deque[Geo]] = field(default_factory=dict)
    events: deque[Event] = field(default_factory=lambda: deque(maxlen=500))
    commands: dict[str, OperatorCommand] = field(default_factory=dict)
    awareness: AwarenessBreakdown = field(
        default_factory=lambda: AwarenessBreakdown(score=0.0, risk_state=RiskState.REST)
    )
    mode: OperatingMode = OperatingMode.REST
    verifier_id: str | None = None
    hold_patrol: bool = False
    session: Session = field(default_factory=lambda: Session(label=DEFAULT_SESSION_LABEL))
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    def vineyard(cls) -> SwarmState:
        state = cls()
        state.sectors = {s.id: s for s in default_sector_grid(VINEYARD_CENTER)}
        state.docks[DEFAULT_DOCK_ID] = DockState(
            dock_id=DEFAULT_DOCK_ID,
            status=DockStatus.ONLINE,
            power_status=PowerStatus.ONLINE,
            units_total=3,
            units_docked=3,
            slots_available=0,
            slots_charging=3,
            primary=True,
        )
        return state

    def append_event(self, event: Event) -> None:
        self.events.append(event)


SWARM_STATE = SwarmState.vineyard()
