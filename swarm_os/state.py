"""Authoritative in-memory SwarmOS state for Phase 1+."""

from __future__ import annotations

import asyncio
import os
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
from swarm_core.streams import StreamDescriptor

from swarm_os.policy import PolicyEngine
from swarm_os.safety import LocalStubWeatherProvider, SafetyAction
from swarm_os.sectors import default_sector_grid
from swarm_os.sites import DEFAULT_SITE_ID, SiteConfig, load_site_config

DEFAULT_DOCK_ID = "dock-langhe-01"
DEFAULT_SESSION_LABEL = "session 014"
VINEYARD_CENTER = Geo(lat=44.7000, lon=8.0300, alt_m=0.0)
SITE_ID_ENV = "SWARM_SITE_ID"  # Phase 6.B — boot-time site selector


def _default_policy() -> PolicyEngine:
    """Wire the built-in vineyard-01 site config + stub weather provider.

    Production deploys override `SwarmState.policy` after construction to
    bind a real `SiteConfig` + real `WeatherProvider`; see
    `docs/ops/drone-day-checklist.md` §2.A.
    """

    return PolicyEngine(load_site_config(), LocalStubWeatherProvider())


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
    streams: dict[str, StreamDescriptor] = field(default_factory=dict)
    awareness: AwarenessBreakdown = field(
        default_factory=lambda: AwarenessBreakdown(score=0.0, risk_state=RiskState.REST)
    )
    mode: OperatingMode = OperatingMode.REST
    verifier_id: str | None = None
    hold_patrol: bool = False
    session: Session = field(default_factory=lambda: Session(label=DEFAULT_SESSION_LABEL))
    # Phase 6.A: server-owned safety policy. The coordinator queries it on
    # every refresh; rejected commands and auto-RTL actions both flow back
    # through state.safety_actions (audit) and state.missions (execution).
    policy: PolicyEngine = field(default_factory=_default_policy)
    safety_actions: deque[SafetyAction] = field(
        default_factory=lambda: deque(maxlen=200)
    )
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @classmethod
    def vineyard(cls) -> SwarmState:
        """Legacy entry point. Reads `SWARM_SITE_ID` (default vineyard-01)
        from the environment and delegates to `from_site_config`. Kept so
        modules + tests that already call `SwarmState.vineyard()` keep
        working unchanged."""

        site_id = os.getenv(SITE_ID_ENV, DEFAULT_SITE_ID)
        return cls.from_site_config(load_site_config(site_id))

    @classmethod
    def from_site_config(cls, site_config: SiteConfig) -> SwarmState:
        """Build a SwarmState bound to a specific site.

        Session.site_id, the policy engine, the sector grid, and the docks
        all derive from `site_config`. Existing hardcoded vineyard
        topology is preserved when the config uses the same center +
        single primary dock, so Phase 1..5 tests continue to pass.
        """

        state = cls()
        state.session = Session(
            label=DEFAULT_SESSION_LABEL,
            site_id=site_config.site_id,
        )
        state.policy = PolicyEngine(site_config, LocalStubWeatherProvider())
        state.sectors = {
            s.id: s for s in default_sector_grid(site_config.center)
        }
        # If the config carries docks, materialize them; otherwise fall back
        # to the legacy single-dock topology for backward compatibility.
        dock_entries = site_config.docks or []
        if dock_entries:
            for entry in dock_entries:
                state.docks[entry.dock_id] = DockState(
                    dock_id=entry.dock_id,
                    status=DockStatus.ONLINE,
                    power_status=PowerStatus.ONLINE,
                    units_total=3 if entry.primary else 0,
                    units_docked=3 if entry.primary else 0,
                    slots_available=0,
                    slots_charging=3 if entry.primary else 0,
                    primary=entry.primary,
                )
        else:
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
