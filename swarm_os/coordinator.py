"""Projection coordinator from raw bus messages to SwarmOS view state.

Phase 3 makes this module the single owner of the event detector + scheduler
+ command tick. Every state mutation flows through one of the `apply_*`
methods, which take the state lock, mutate, run `_refresh`, and return the
WS frames the caller should broadcast.

`_refresh` is the truth-layer heartbeat: it recomputes sector confidence,
fires the scheduler, recomputes mode + verifier, embeds them in the
awareness frame, and asks the event detector to diff against the previous
state. Nothing in the Console ever computes any of this client-side.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from swarm_core.geometry import haversine_m
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
    OperatorCommand,
    Telemetry,
    UnitState,
)
from swarm_core.voice import band

from swarm_os.autonomy import tick as autonomy_tick
from swarm_os.autonomy import to_command as autonomy_to_command
from swarm_os.awareness import calculate_awareness
from swarm_os.command_bus import EMERGENCY_MISSION_PREFIX, CommandResult
from swarm_os.command_bus import submit as command_submit
from swarm_os.command_bus import tick as command_tick
from swarm_os.event_detector import EventDetector
from swarm_os.fsm import compute_mode
from swarm_os.safety import SafetyActionKind
from swarm_os.scheduler import tick as scheduler_tick
from swarm_os.sectors import refresh_visits, score_sectors, sector_for_geo
from swarm_os.state import DEFAULT_DOCK_ID, SwarmState

AUTO_RTL_PREFIX = "auto-rtl-"  # Phase 6.A — de-dupe auto-RTL per agent
AUTO_RTL_PRIORITY = 100  # safety always preempts


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
            new_events, autonomy_cmds = await self._refresh_async(now)
            frames = self._frames("unit", unit)
            frames.extend(self._frame("operator", cmd) for cmd in autonomy_cmds)
            frames.extend(self._frame("event", event) for event in new_events)
            return frames

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
                docked = sum(
                    1 for u in self.state.units.values() if u.fsm_state == AgentState.DOCKED
                )
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
            new_events, autonomy_cmds = await self._refresh_async(now)
            frames = self._frames("unit", unit)
            frames.extend(self._frame("dock", d) for d in self.state.docks.values())
            frames.extend(self._frame("operator", cmd) for cmd in autonomy_cmds)
            frames.extend(self._frame("event", event) for event in new_events)
            return frames

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
            new_events, autonomy_cmds = await self._refresh_async(now)
            frames = self._frames("anomaly_view", view)
            frames.extend(self._frame("operator", cmd) for cmd in autonomy_cmds)
            frames.extend(self._frame("event", event) for event in new_events)
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
            # Phase 7 (WS1a): a *completed* VERIFY mission is what promotes the
            # anomaly it was verifying VERIFYING → VERIFIED. The executed
            # mission arrives from the orchestrator under its own uuid with no
            # OperatorCommand link (the `cmd-*` bookkeeping mission never runs
            # live), so we resolve the target by VERIFYING state, not mission
            # id. Promotion happens *before* `_refresh` so the same refresh's
            # autonomy tick observes the freshly-VERIFIED anomaly — though R2
            # only fires a later tick once the idle floor elapses (ts=now).
            if phase is MissionPhase.DONE and mission.kind == "VERIFY":
                self._promote_verified_anomaly(mission, now)
            new_events, autonomy_cmds = await self._refresh_async(now)
            frames = self._frames("mission", mission)
            frames.extend(self._frame("operator", cmd) for cmd in autonomy_cmds)
            frames.extend(self._frame("event", event) for event in new_events)
            return frames

    async def apply_command(self, command: OperatorCommand) -> tuple[CommandResult, list[dict[str, Any]]]:
        """Submit an operator intent and return (result, frames-to-broadcast)."""

        result = await command_submit(self.state, command)
        async with self.state.lock:
            now = datetime.now(UTC)
            new_events, autonomy_cmds = await self._refresh_async(now)
            stored = self.state.commands.get(command.id)
            frames: list[dict[str, Any]] = []
            if stored is not None:
                frames.append(self._frame("operator", stored))
            # Autonomy decisions surfaced during the same refresh tick get
            # their own `operator` frames so the Console (Phase 7.C) sees
            # them with the AUTO eyebrow alongside the operator command.
            frames.extend(self._frame("operator", cmd) for cmd in autonomy_cmds)
            # Awareness + sector frames in case the command shifted mode.
            frames.append(self._frame("awareness", self.state.awareness))
            frames.extend(
                self._frame("sector", sector) for sector in self.state.sectors.values()
            )
            for anomaly in self.state.anomalies.values():
                frames.append(self._frame("anomaly_view", anomaly))
            for mission in self.state.missions.values():
                frames.append(self._frame("mission", mission))
            frames.extend(self._frame("event", event) for event in new_events)
        return result, frames

    async def snapshot_frames(self) -> list[dict[str, Any]]:
        async with self.state.lock:
            return [
                self._frame("session", self.state.session),
                self._frame("awareness", self.state.awareness),
                *[self._frame("dock", dock) for dock in self.state.docks.values()],
                *[self._frame("sector", sector) for sector in self.state.sectors.values()],
                *[self._frame("unit", unit) for unit in self.state.units.values()],
                *[self._frame("mission", mission) for mission in self.state.missions.values()],
                *[
                    self._frame("anomaly_view", anomaly)
                    for anomaly in self.state.anomalies.values()
                ],
                *[
                    self._frame("operator", command)
                    for command in self.state.commands.values()
                ],
                *[self._frame("stream", stream) for stream in self.state.streams.values()],
                *[self._frame("event", event) for event in self.state.events],
            ]

    # ── Internals ────────────────────────────────────────────────────────────

    def _refresh(self, now: datetime) -> tuple[list[Any], list[OperatorCommand]]:
        """Recompute every derived field server-side.

        Returns (events, autonomy_commands) so each `apply_*` can emit
        both `event` and `operator` frames for live WS push — Phase 7.C
        depends on the Console seeing autonomy decisions as they happen,
        not only on snapshot reload.
        """

        self.state.sectors = refresh_visits(self.state.sectors, self.state.units, now)
        self.state.sectors = score_sectors(self.state.sectors, now)
        new_missions = scheduler_tick(self.state, now)
        # Phase 6.A: auto-RTL precedes the command tick so the auto-RTL
        # mission is observable before any operator command lifecycle moves.
        self._apply_safety_actions(now)
        # Phase 7.B: refresh mode + verifier *before* the autonomy tick so
        # autonomy's tentative VERIFY mission can be checked against a
        # real assignee by the policy gate (battery / link / weather).
        # Without this, a fresh anomaly would dispatch through autonomy
        # with assigned_agent=None and bypass the per-unit battery floor.
        self.state.mode = compute_mode(self.state)
        self._refresh_verifier()
        # Autonomy decisions ride the same command bus + audit log as
        # operator commands. Runs after safety so an auto-RTL still wins,
        # before command_tick so the decision's lifecycle advances on the
        # same coordinator pass.
        autonomy_commands = self._apply_autonomy_decisions(now)
        command_tick(self.state, now)
        # Recompute mode + verifier so any state mutations the autonomy
        # tick triggered (anomaly state change, new mission) are
        # reflected before the awareness frame snapshot.
        self.state.mode = compute_mode(self.state)
        self._refresh_verifier()
        self._propagate_verifier_to_anomalies(now)
        self.state.awareness = calculate_awareness(
            sectors=self.state.sectors,
            units=self.state.units,
            anomalies=self.state.anomalies,
            now=now,
            mode=self.state.mode,
            verifying_agent=self.state.verifier_id,
        )
        events = self.events.update(self.state)
        for event in events:
            self.state.append_event(event)
        # New auto-scheduled missions surface implicitly via the mission frames
        # emitted by the caller — we keep the list for testability though.
        _ = new_missions
        # Read the post-submit state of each autonomy command so the
        # broadcast frame carries the lifecycle status (ACCEPTED /
        # REJECTED / COMPLETED) and not just the submitted draft.
        autonomy_post = [
            self.state.commands[c.id]
            for c in autonomy_commands
            if c.id in self.state.commands
        ]
        return events, autonomy_post

    def _apply_autonomy_decisions(self, now: datetime) -> list[OperatorCommand]:
        """Phase 7.B — translate autonomy decisions into audited commands.

        Returns the list of `OperatorCommand` records submitted this tick
        (whether accepted or rejected by the policy gate) so the caller
        can emit `operator` WS frames for live Console push (Phase 7.C).

        Each decision flows through the lock-free `submit_locked` path —
        that single call re-runs validation + the Phase 6.A policy gate
        (geofence / battery / link / weather), records the result in
        `state.commands`, and spawns the mission view — i.e. an autonomy
        decision is fully verifiable the same way an operator command is.

        Rejections (e.g. low battery on the verifier) land as REJECTED
        rows in the audit log; no fallback or retry in the 7.B baseline.
        Phase 8.C handles re-decisioning.
        """

        from swarm_os.command_bus import submit_locked

        decisions = autonomy_tick(self.state, now)
        submitted: list[OperatorCommand] = []
        for decision in decisions:
            command = autonomy_to_command(decision)
            submit_locked(self.state, command, now)
            submitted.append(command)
        return submitted

    def _apply_safety_actions(self, now: datetime) -> None:
        """Phase 6.A — translate PolicyEngine safety actions into RTL missions.

        The engine emits SafetyAction(AUTO_RTL, ...) for any airborne unit
        below the battery floor or below the link floor. Each unit gets at
        most one outstanding auto-RTL mission (deduped by `auto-rtl-<id>`).
        The action itself is appended to the audit deque so the Console can
        surface "auto-RTL forced by SwarmOS" alongside operator commands.
        """

        actions = self.state.policy.evaluate_safety_actions(self.state.units)
        for action in actions:
            if action.kind is not SafetyActionKind.AUTO_RTL:
                continue
            # Phase 6.G: a unit already carrying an active emergency RTL
            # doesn't need an additional auto-RTL — they'd race for the
            # same slot and the audit log would double-count the event.
            emergency_id = f"{EMERGENCY_MISSION_PREFIX}{action.agent_id}"
            emergency = self.state.missions.get(emergency_id)
            if emergency is not None and emergency.phase not in {
                MissionPhase.DONE,
                MissionPhase.FAILED,
            }:
                continue
            mission_id = f"{AUTO_RTL_PREFIX}{action.agent_id}"
            existing = self.state.missions.get(mission_id)
            if existing is not None and existing.phase not in {
                MissionPhase.DONE,
                MissionPhase.FAILED,
            }:
                continue
            self.state.missions[mission_id] = MissionView(
                id=mission_id,
                kind="RTL_DOCK",
                assigned_agent=action.agent_id,
                phase=MissionPhase.PENDING,
                progress_pct=0.0,
                priority=AUTO_RTL_PRIORITY,
                ts=now,
            )
            self.state.safety_actions.append(action)

    def _promote_verified_anomaly(self, mission: MissionView, now: datetime) -> None:
        """Promote the anomaly a completed VERIFY mission was verifying.

        Phase 7 (WS1a) closes the live verify-loop: R1 moves an anomaly
        PENDING → VERIFYING, the orchestrator runs the VERIFY mission, and
        *this* is where its `DONE` flips the anomaly VERIFYING → VERIFIED so
        R2 can later auto-ESCALATE.

        Guards (every state mutation must be honest — CLAUDE.md):
          * promote **only** from VERIFYING. A DISMISSED / ESCALATED /
            PENDING / already-VERIFIED anomaly is never clobbered, so a late
            or duplicate mission completion can't resurrect an anomaly the
            operator (or R3) already resolved.
          * stamp ``ts=now`` so R2's ``AUTO_ESCALATE_IDLE_S`` clock starts
            clean from the instant of verification (see ``autonomy._aged``).

        FAILED missions are handled by the caller (only ``DONE`` reaches
        here), leaving the anomaly in VERIFYING — never bounced back to
        PENDING, which would loop R1.
        """

        anomaly_id = self._anomaly_for_verify_mission(mission)
        if anomaly_id is None:
            return
        anomaly = self.state.anomalies[anomaly_id]
        if anomaly.state is not AnomalyState.VERIFYING:
            return
        self.state.anomalies[anomaly_id] = anomaly.model_copy(
            update={"state": AnomalyState.VERIFIED, "ts": now}
        )

    def _anomaly_for_verify_mission(self, mission: MissionView) -> str | None:
        """Resolve which anomaly a completed VERIFY mission verified.

        The executed mission (orchestrator uuid) carries no command link and,
        on the live path, no sector or waypoint metadata — so VERIFYING state
        is the primary key. When the mission *does* know its sector or station
        waypoint (e.g. a sector-targeted VERIFY, or the `cmd-*` bookkeeping
        mission the tests drive), narrow by sector first, then nearest geo, so
        concurrent verifications can't cross-promote. With no geo to
        disambiguate, the longest-waiting VERIFYING anomaly is the one whose
        in-flight mission completes first.
        """

        candidates = [
            (aid, anomaly)
            for aid, anomaly in self.state.anomalies.items()
            if anomaly.state is AnomalyState.VERIFYING
        ]
        if not candidates:
            return None
        if mission.sector_id is not None:
            in_sector = [
                pair for pair in candidates if pair[1].sector_id == mission.sector_id
            ]
            if in_sector:
                candidates = in_sector
        if mission.waypoints:
            target = mission.waypoints[-1]
            candidates.sort(key=lambda pair: haversine_m(pair[1].geo, target))
        else:
            candidates.sort(key=lambda pair: pair[1].ts)
        return candidates[0][0]

    async def _refresh_async(
        self, now: datetime
    ) -> tuple[list[Any], list[OperatorCommand]]:
        """Async wrapper that refreshes dock weather before `_refresh`.

        Every async `apply_*` path goes through this so the sync `_refresh`
        always sees a consistent dock weather state. The provider call is
        cached for `SiteConfig.weather_provider.refresh_interval_s`, so the
        per-frame cost is a dict comparison.
        """

        updated = await self.state.policy.refresh_dock_weather_locks(self.state.docks)
        if updated:
            self.state.docks.update(updated)
        return self._refresh(now)

    def _refresh_verifier(self) -> None:
        """Maintain a canonical verifier id when in verification/escalation."""

        if self.state.mode in {OperatingMode.VERIFICATION, OperatingMode.ESCALATION}:
            current = self.state.verifier_id
            if current is None or current not in self.state.units:
                airborne = [
                    u
                    for u in self.state.units.values()
                    if u.fsm_state
                    not in {AgentState.DOCKED, AgentState.OFFLINE, AgentState.ERROR}
                ]
                candidates = airborne or list(self.state.units.values())
                if candidates:
                    self.state.verifier_id = max(
                        candidates, key=lambda u: u.battery_pct
                    ).agent_id
        else:
            # Outside verification flow we don't pin a verifier — the awareness
            # frame correctly reports None.
            self.state.verifier_id = None

    def _propagate_verifier_to_anomalies(self, now: datetime) -> None:
        """Stamp every active anomaly with the current canonical verifier."""

        verifier = self.state.verifier_id
        for aid, anomaly in list(self.state.anomalies.items()):
            if anomaly.state not in {
                AnomalyState.PENDING,
                AnomalyState.VERIFYING,
                AnomalyState.VERIFIED,
            }:
                continue
            if anomaly.verifying_agent == verifier:
                continue
            self.state.anomalies[aid] = anomaly.model_copy(
                update={"verifying_agent": verifier, "ts": now}
            )

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
