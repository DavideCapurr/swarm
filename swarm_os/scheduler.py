"""Phase 3 patrol scheduler.

Two responsibilities:

1. Refresh dock `next_patrol_at` metadata so the Console rail can render the
   next dispatch window from a truth frame (no client derive).
2. Stamp automatic re-patrol missions when a sector's coverage decays past
   the cadence threshold. This is what removes "manual missions" from the
   product loop — the operator only ever sees auto-scheduled patrols plus
   their own intent-spawned VERIFY / RTL missions.

Anti-overreach: scheduler stays pure-Python and in-memory. No timers, no
queues, no external dispatch — Phase 4 wires persistence, Phase 5 routes the
mission to a real adapter. Today we just stamp `MissionView` records.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol

from swarm_core.messages import (
    AgentState,
    DockState,
    MissionPhase,
    MissionView,
    OperatingMode,
    Sector,
    SectorState,
    UnitState,
)

from swarm_os.policy import PolicyEngine

PATROL_INTERVAL_S = 300
SECTOR_REPATROL_CONFIDENCE = 0.35  # at/under this we schedule a fresh patrol
AUTO_PATROL_PREFIX = "auto-"  # mission id prefix so we can de-dupe per sector
AUTO_PATROL_PRIORITY = 10  # Phase 6.A.5 — scheduler-auto patrol lowest priority


class _StateLike(Protocol):
    docks: dict[str, DockState]
    sectors: dict[str, Sector]
    missions: dict[str, MissionView]
    units: dict[str, UnitState]
    mode: OperatingMode
    hold_patrol: bool
    policy: PolicyEngine


def next_patrol_at(dock: DockState, now: datetime) -> datetime:
    if dock.next_patrol_at and dock.next_patrol_at > now:
        return dock.next_patrol_at
    return now + timedelta(seconds=PATROL_INTERVAL_S)


def tick(state: _StateLike, now: datetime) -> list[MissionView]:
    """Refresh dock schedules and stamp auto re-patrol missions.

    Returns the list of newly-created missions so the coordinator can emit
    their frames and patrol_started events.
    """

    for dock_id, dock in list(state.docks.items()):
        state.docks[dock_id] = dock.model_copy(
            update={
                "next_patrol_at": next_patrol_at(dock, now),
                "ts": now,
            }
        )

    return _schedule_repatrols(state, now)


def _schedule_repatrols(state: _StateLike, now: datetime) -> list[MissionView]:
    """Create one PATROL mission per stale/blind sector without an active one."""

    if state.hold_patrol or state.mode == OperatingMode.MAINTENANCE:
        return []

    busy_sectors: set[str] = set()
    for mission in state.missions.values():
        if mission.sector_id and mission.phase not in {
            MissionPhase.DONE,
            MissionPhase.FAILED,
        }:
            busy_sectors.add(mission.sector_id)

    candidates = [
        sector
        for sector in state.sectors.values()
        if sector.id not in busy_sectors
        and sector.state in {SectorState.STALE, SectorState.BLIND}
        and sector.confidence <= SECTOR_REPATROL_CONFIDENCE
    ]
    if not candidates:
        return []

    airborne = sorted(
        (
            u
            for u in state.units.values()
            if u.fsm_state
            not in {AgentState.OFFLINE, AgentState.ERROR, AgentState.DOCKED}
        ),
        key=lambda u: u.battery_pct,
        reverse=True,
    )
    docked = sorted(
        (u for u in state.units.values() if u.fsm_state == AgentState.DOCKED),
        key=lambda u: u.battery_pct,
        reverse=True,
    )
    pool = airborne + docked

    created: list[MissionView] = []
    # Order by lowest confidence first so the most-stale sector gets the
    # freshest unit.
    candidates.sort(key=lambda s: s.confidence)
    for idx, sector in enumerate(candidates):
        mission_id = f"{AUTO_PATROL_PREFIX}{sector.id}-{int(now.timestamp())}"
        if mission_id in state.missions:
            continue
        assignee = pool[idx].agent_id if idx < len(pool) else None
        mission = MissionView(
            id=mission_id,
            kind="PATROL",
            assigned_agent=assignee,
            sector_id=sector.id,
            phase=MissionPhase.PENDING,
            progress_pct=0.0,
            waypoints=[sector.centroid],
            priority=AUTO_PATROL_PRIORITY,
            ts=now,
        )
        # Phase 6.A: gate auto-PATROL through the policy engine. A geofence
        # mismatch, weather lock, or assignee under-threshold drops the
        # mission so the operator timeline never shows phantom dispatches.
        decision = state.policy.validate_mission(
            mission, units=state.units, docks=state.docks
        )
        if not decision.allowed:
            continue
        state.missions[mission_id] = mission
        created.append(mission)
    return created
