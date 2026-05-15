"""Projection coordinator from raw bus messages to SwarmOS view state."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyState,
    AnomalyView,
    DockStatus,
    FleetState,
    MissionPhase,
    MissionProgress,
    MissionView,
    OperatingMode,
    Telemetry,
    UnitState,
)
from swarm_core.voice import band

from swarm_os.awareness import calculate_awareness
from swarm_os.event_detector import EventDetector
from swarm_os.fsm import compute_mode
from swarm_os.scheduler import tick as scheduler_tick
from swarm_os.sectors import refresh_visits, score_sectors, sector_for_geo
from swarm_os.state import DEFAULT_DOCK_ID, SwarmState


class SwarmCoordinator:
    """Owns state projection and WS frame generation."""

    def __init__(self, state: SwarmState) -> None:
        self.state = state
        self.events = EventDetector()

    async def apply_telemetry(self, telemetry: Telemetry) -> list[dict[str, Any]]:
        async with self.state.lock:
            now = datetime.now(UTC)
            track = self.state.tracks.setdefault(telemetry.agent_id, deque(maxlen=120))
            track.append(telemetry.geo)
            existing = self.state.units.get(telemetry.agent_id)
            unit = UnitState(
                agent_id=telemetry.agent_id,
                vendor=existing.vendor if existing else "simulated",
                model=existing.model if existing else "sim-x500",
                fsm_state=existing.fsm_state if existing else AgentState.DOCKED,
                battery_pct=telemetry.battery_pct,
                geo=telemetry.geo,
                current_mission_id=existing.current_mission_id if existing else None,
                current_sector_id=sector_for_geo(telemetry.geo, self.state.sectors),
                link_quality=telemetry.link_quality,
                heading_deg=telemetry.attitude.yaw_deg,
                altitude_agl_m=telemetry.geo.alt_m,
                dock_id=DEFAULT_DOCK_ID,
                ts=telemetry.ts,
            )
            self.state.units[unit.agent_id] = unit
            self._refresh(now)
            return self._frames("unit", unit)

    async def apply_fleet_state(self, fleet: FleetState) -> list[dict[str, Any]]:
        async with self.state.lock:
            now = datetime.now(UTC)
            existing = self.state.units.get(fleet.agent_id)
            unit = UnitState(
                agent_id=fleet.agent_id,
                vendor=fleet.vendor,
                model=fleet.model,
                fsm_state=fleet.fsm_state,
                battery_pct=fleet.battery_pct,
                geo=fleet.geo,
                current_mission_id=fleet.current_mission_id,
                current_sector_id=sector_for_geo(fleet.geo, self.state.sectors),
                link_quality=fleet.link_quality,
                heading_deg=existing.heading_deg if existing else 0.0,
                altitude_agl_m=fleet.geo.alt_m,
                dock_id=DEFAULT_DOCK_ID,
                ts=fleet.ts,
            )
            self.state.units[fleet.agent_id] = unit
            for dock_id, dock in list(self.state.docks.items()):
                docked = sum(1 for u in self.state.units.values() if u.fsm_state == AgentState.DOCKED)
                self.state.docks[dock_id] = dock.model_copy(
                    update={
                        "units_total": len(self.state.units),
                        "units_docked": docked,
                        "slots_charging": docked,
                        "slots_available": max(0, len(self.state.units) - docked),
                        "status": DockStatus.ONLINE,
                        "ts": now,
                    }
                )
            self._refresh(now)
            return self._frames("unit", unit) + [self._frame("dock", d) for d in self.state.docks.values()]

    async def apply_anomaly(self, anomaly: Anomaly) -> list[dict[str, Any]]:
        async with self.state.lock:
            now = datetime.now(UTC)
            sector_id = sector_for_geo(anomaly.geo, self.state.sectors)
            view = AnomalyView(
                id=anomaly.id,
                kind=anomaly.kind,
                geo=anomaly.geo,
                sector_id=sector_id,
                confidence=anomaly.confidence,
                band=band(anomaly.confidence),
                state=AnomalyState.VERIFIED if anomaly.verified else AnomalyState.PENDING,
                detected_at=anomaly.ts,
                detected_by=anomaly.source_agent,
                verifying_agent=self.state.verifier_id,
                ts=now,
            )
            self.state.anomalies[view.id] = view
            if sector_id and sector_id in self.state.sectors:
                sector = self.state.sectors[sector_id]
                pending = sorted({*sector.pending_anomaly_ids, view.id})
                self.state.sectors[sector_id] = sector.model_copy(
                    update={"pending_anomaly_ids": pending, "ts": now}
                )
            event = self.events.anomaly_event(view)
            if event is not None:
                self.state.append_event(event)
            self._refresh(now)
            frames = self._frames("anomaly_view", view)
            if event is not None:
                frames.append(self._frame("event", event))
            return frames

    async def apply_mission_progress(self, progress: MissionProgress) -> list[dict[str, Any]]:
        async with self.state.lock:
            now = datetime.now(UTC)
            phase = _mission_phase(progress.phase)
            existing = self.state.missions.get(progress.mission_id)
            assigned = existing.assigned_agent if existing else self.state.verifier_id
            mission = MissionView(
                id=progress.mission_id,
                kind=existing.kind if existing else "VERIFY",
                assigned_agent=assigned,
                sector_id=existing.sector_id if existing else None,
                phase=phase,
                progress_pct=progress.progress_pct,
                eta_s=progress.eta_s,
                waypoints=existing.waypoints if existing else [],
                track=list(self.state.tracks.get(assigned or "", [])),
                ts=progress.ts,
            )
            self.state.missions[mission.id] = mission
            event = self.events.mission_event(progress, assigned)
            if event is not None:
                self.state.append_event(event)
            self._refresh(now)
            frames = self._frames("mission", mission)
            if event is not None:
                frames.append(self._frame("event", event))
            return frames

    async def snapshot_frames(self) -> list[dict[str, Any]]:
        async with self.state.lock:
            return [
                self._frame("session", self.state.session),
                self._frame("awareness", self.state.awareness),
                *[self._frame("dock", dock) for dock in self.state.docks.values()],
                *[self._frame("sector", sector) for sector in self.state.sectors.values()],
                *[self._frame("unit", unit) for unit in self.state.units.values()],
                *[self._frame("mission", mission) for mission in self.state.missions.values()],
                *[self._frame("anomaly_view", anomaly) for anomaly in self.state.anomalies.values()],
                *[self._frame("event", event) for event in self.state.events],
            ]

    def _refresh(self, now: datetime) -> None:
        self.state.sectors = refresh_visits(self.state.sectors, self.state.units, now)
        self.state.sectors = score_sectors(self.state.sectors, now)
        scheduler_tick(self.state, now)
        self.state.awareness = calculate_awareness(
            sectors=self.state.sectors,
            units=self.state.units,
            anomalies=self.state.anomalies,
            now=now,
        )
        self.state.mode = compute_mode(self.state)
        if self.state.mode == OperatingMode.VERIFICATION and self.state.verifier_id is None:
            airborne = [u for u in self.state.units.values() if u.fsm_state != AgentState.DOCKED]
            candidates = airborne or list(self.state.units.values())
            self.state.verifier_id = max(candidates, key=lambda u: u.battery_pct).agent_id if candidates else None

    def _frames(self, kind: str, model: object) -> list[dict[str, Any]]:
        frames = [self._frame(kind, model), self._frame("awareness", self.state.awareness)]
        frames.extend(self._frame("sector", sector) for sector in self.state.sectors.values())
        return frames

    @staticmethod
    def _frame(kind: str, model: object) -> dict[str, Any]:
        return {"kind": kind, "data": model.model_dump(mode="json")}  # type: ignore[attr-defined]


def _mission_phase(raw: str) -> MissionPhase:
    mapping = {
        "BIDDING": MissionPhase.BIDDING,
        "EN_ROUTE": MissionPhase.EN_ROUTE,
        "ON_STATION": MissionPhase.ON_STATION,
        "RETURNING": MissionPhase.RETURNING,
        "DONE": MissionPhase.DONE,
        "FAILED": MissionPhase.FAILED,
    }
    return mapping.get(raw.upper(), MissionPhase.PENDING)
