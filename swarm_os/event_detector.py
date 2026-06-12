"""Phase 3 event detector.

The detector watches `SwarmState` and emits typed `Event` records for every
operationally significant transition. It is intentionally stateful: it caches
the previous value of each watched field and diffs on every call so that a
single transition produces one event (no duplicates).

Coverage (15 kinds from the Phase 3 roadmap):

    patrol_started, patrol_completed, sector_visited,
    anomaly_detected, anomaly_verifying, anomaly_verified,
    anomaly_dismissed, anomaly_escalated,
    operator_command_submitted, operator_command_completed,
    operator_command_rejected,
    dock_weather_lock, link_degraded, unit_battery_low,
    mission_failed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from swarm_core.messages import (
    Anomaly,
    AnomalyState,
    AnomalyView,
    CommandStatus,
    Event,
    EventKind,
    MissionPhase,
    OperatorCommand,
)
from swarm_core.voice import describe_anomaly

if TYPE_CHECKING:  # pragma: no cover
    from swarm_os.state import SwarmState

LINK_LOW_THRESHOLD = 0.35
BATTERY_LOW_THRESHOLD = 20.0

# Anomaly state → (event body, action label)
_ANOMALY_TRANSITION_COPY: dict[AnomalyState, tuple[str, str | None]] = {
    AnomalyState.PENDING: ("anomaly detected · verification queued", "Verify sector"),
    AnomalyState.VERIFYING: ("anomaly verifying · awaiting confidence", None),
    AnomalyState.VERIFIED: ("event verified · operator decision required", "Escalate"),
    AnomalyState.DISMISSED: ("anomaly dismissed · returned to patrol", None),
    AnomalyState.ESCALATED: ("event escalated · operator path engaged", None),
    AnomalyState.MARKED_KNOWN: ("anomaly marked known · suppressed", None),
}


class EventDetector:
    """Idempotent event builder driven by `SwarmState` snapshots."""

    def __init__(self) -> None:
        # Phase 1 single-shot keys still used by raw bus callers.
        self._seen: set[str] = set()
        # Phase 3 diff state.
        self._anomaly_state: dict[str, AnomalyState] = {}
        self._mission_phase: dict[str, MissionPhase] = {}
        self._sector_visitor: dict[str, str | None] = {}
        self._unit_battery_low: set[str] = set()
        self._unit_link_low: set[str] = set()
        self._dock_weather: dict[str, bool] = {}
        self._command_status: dict[str, CommandStatus] = {}

    # ── Phase 1 helpers (kept for raw bus paths) ────────────────────────────

    def raw_anomaly_event(self, anomaly: Anomaly) -> Event:
        return Event(
            kind=EventKind.ANOMALY,
            agent_id=anomaly.source_agent,
            anomaly_id=anomaly.id,
            confidence=anomaly.confidence,
            body="elevated anomaly · verification queued",
            action_label="Verify sector",
        )

    # ── Phase 3: snapshot-driven diff ───────────────────────────────────────

    def update(self, state: SwarmState) -> list[Event]:
        """Walk the current state and return events for any new transition."""

        events: list[Event] = []
        events.extend(self._diff_anomalies(state))
        events.extend(self._diff_missions(state))
        events.extend(self._diff_sectors(state))
        events.extend(self._diff_units(state))
        events.extend(self._diff_docks(state))
        events.extend(self._diff_commands(state))
        self._prune(state)
        return events

    def _prune(self, state: SwarmState) -> None:
        """Drop diff entries for entities no longer present in the state.

        Long sessions with churn (auto-mission ids, anomaly ids, command
        ids) would otherwise grow these caches without bound. An entity
        that is removed and later re-appears under the same id is treated
        as new — its first transition emits an event again, which is the
        honest reading of a re-detected entity.
        """

        self._anomaly_state = {
            k: v for k, v in self._anomaly_state.items() if k in state.anomalies
        }
        self._mission_phase = {
            k: v for k, v in self._mission_phase.items() if k in state.missions
        }
        self._sector_visitor = {
            k: v for k, v in self._sector_visitor.items() if k in state.sectors
        }
        self._unit_battery_low &= set(state.units)
        self._unit_link_low &= set(state.units)
        self._dock_weather = {
            k: v for k, v in self._dock_weather.items() if k in state.docks
        }
        self._command_status = {
            k: v for k, v in self._command_status.items() if k in state.commands
        }

    # ── Anomalies ───────────────────────────────────────────────────────────

    def _diff_anomalies(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for anomaly in state.anomalies.values():
            prev = self._anomaly_state.get(anomaly.id)
            if prev == anomaly.state:
                continue
            self._anomaly_state[anomaly.id] = anomaly.state
            out.append(_anomaly_transition_event(anomaly))
        return out

    # ── Missions ────────────────────────────────────────────────────────────

    def _diff_missions(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for mission in state.missions.values():
            prev = self._mission_phase.get(mission.id)
            if prev == mission.phase:
                continue
            self._mission_phase[mission.id] = mission.phase
            kind = (mission.kind or "").upper()
            if mission.phase == MissionPhase.EN_ROUTE and kind == "PATROL":
                out.append(
                    Event(
                        kind=EventKind.PATROL,
                        mission_id=mission.id,
                        sector_id=mission.sector_id,
                        agent_id=mission.assigned_agent,
                        body=f"patrol started · sector {mission.sector_id or '—'}",
                    )
                )
            elif mission.phase == MissionPhase.DONE and kind == "PATROL":
                out.append(
                    Event(
                        kind=EventKind.PATROL,
                        mission_id=mission.id,
                        sector_id=mission.sector_id,
                        agent_id=mission.assigned_agent,
                        body=f"patrol completed · sector {mission.sector_id or '—'}",
                    )
                )
            elif mission.phase == MissionPhase.FAILED:
                out.append(
                    Event(
                        kind=EventKind.MISSION,
                        mission_id=mission.id,
                        sector_id=mission.sector_id,
                        agent_id=mission.assigned_agent,
                        body="mission failed · routing adjusted",
                    )
                )
        return out

    # ── Sectors ─────────────────────────────────────────────────────────────

    def _diff_sectors(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for sector in state.sectors.values():
            prev = self._sector_visitor.get(sector.id)
            if prev == sector.last_visited_by:
                continue
            self._sector_visitor[sector.id] = sector.last_visited_by
            if sector.last_visited_by is None:
                continue
            out.append(
                Event(
                    kind=EventKind.SECTOR,
                    sector_id=sector.id,
                    agent_id=sector.last_visited_by,
                    body=f"sector {sector.label} visited · coverage refreshed",
                )
            )
        return out

    # ── Units (battery + link) ──────────────────────────────────────────────

    def _diff_units(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for unit in state.units.values():
            low_battery = unit.battery_pct <= BATTERY_LOW_THRESHOLD
            was_low_battery = unit.agent_id in self._unit_battery_low
            if low_battery and not was_low_battery:
                self._unit_battery_low.add(unit.agent_id)
                out.append(
                    Event(
                        kind=EventKind.SYSTEM,
                        agent_id=unit.agent_id,
                        body=f"unit {unit.agent_id} battery low · return recommended",
                        action_label="Return Unit",
                    )
                )
            elif not low_battery and was_low_battery:
                self._unit_battery_low.discard(unit.agent_id)

            low_link = unit.link_quality <= LINK_LOW_THRESHOLD
            was_low_link = unit.agent_id in self._unit_link_low
            if low_link and not was_low_link:
                self._unit_link_low.add(unit.agent_id)
                out.append(
                    Event(
                        kind=EventKind.LINK,
                        agent_id=unit.agent_id,
                        body=f"link degraded · unit {unit.agent_id}",
                    )
                )
            elif not low_link and was_low_link:
                self._unit_link_low.discard(unit.agent_id)
        return out

    # ── Docks ───────────────────────────────────────────────────────────────

    def _diff_docks(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for dock in state.docks.values():
            prev = self._dock_weather.get(dock.dock_id, False)
            if prev == dock.weather_lock:
                continue
            self._dock_weather[dock.dock_id] = dock.weather_lock
            if dock.weather_lock:
                out.append(
                    Event(
                        kind=EventKind.DOCK,
                        dock_id=dock.dock_id,
                        body=f"dock {dock.dock_id} weather lock · launches held",
                    )
                )
            else:
                out.append(
                    Event(
                        kind=EventKind.DOCK,
                        dock_id=dock.dock_id,
                        body=f"dock {dock.dock_id} weather lock cleared",
                    )
                )
        return out

    # ── Operator commands ───────────────────────────────────────────────────

    def _diff_commands(self, state: SwarmState) -> list[Event]:
        out: list[Event] = []
        for command in state.commands.values():
            prev = self._command_status.get(command.id)
            if prev == command.status:
                continue
            self._command_status[command.id] = command.status
            event = _command_event(command, prev)
            if event is not None:
                out.append(event)
        return out


def _anomaly_transition_event(anomaly: AnomalyView) -> Event:
    body, action = _ANOMALY_TRANSITION_COPY.get(
        anomaly.state, ("anomaly state changed", None)
    )
    if anomaly.state == AnomalyState.PENDING:
        # Use the confidence-bound voice helper to render the body when the
        # anomaly first appears, mirroring the Phase 1 behaviour.
        body = describe_anomaly(anomaly)
    return Event(
        kind=EventKind.ANOMALY,
        sector_id=anomaly.sector_id,
        agent_id=anomaly.detected_by,
        anomaly_id=anomaly.id,
        confidence=anomaly.confidence,
        body=body,
        action_label=action,
    )


_AUTONOMY_BODY_FOR_ACTION: dict[str, str] = {
    "verify": "autonomy verify dispatched",
    "escalate": "autonomy escalate dispatched",
    "dismiss": "autonomy dismiss dispatched",
}


def _command_event(command: OperatorCommand, prev: CommandStatus | None) -> Event | None:
    is_autonomy = command.source == "autonomy"
    if is_autonomy:
        # Phase 7.C — autonomy bodies are confidence-bound. The Console
        # renders the AUTO eyebrow off `source`, so the body stays compact.
        base = _AUTONOMY_BODY_FOR_ACTION.get(
            command.action.value, f"autonomy {command.action.value} dispatched"
        )
        rule_suffix = f" · {command.rule}" if command.rule else ""
        body_for_status = {
            CommandStatus.SUBMITTED: f"{base}{rule_suffix}",
            CommandStatus.ACCEPTED: f"{base}{rule_suffix}",
            CommandStatus.IN_FLIGHT: f"{base}{rule_suffix}",
            CommandStatus.COMPLETED: f"autonomy {command.action.value} completed{rule_suffix}",
            CommandStatus.TIMED_OUT: f"autonomy {command.action.value} timed out{rule_suffix}",
        }
    else:
        body_for_status = {
            CommandStatus.SUBMITTED: f"operator intent submitted · {command.action.value}",
            CommandStatus.ACCEPTED: f"operator intent accepted · {command.action.value}",
            CommandStatus.IN_FLIGHT: f"operator intent in flight · {command.action.value}",
            CommandStatus.COMPLETED: f"operator intent completed · {command.action.value}",
            CommandStatus.TIMED_OUT: f"operator intent timed out · {command.action.value}",
        }
    if command.status == CommandStatus.REJECTED:
        reason = command.rejected_reason.value if command.rejected_reason else "policy_deny"
        prefix = "autonomy" if is_autonomy else "operator intent"
        rule_suffix = (
            f" · {command.rule}" if is_autonomy and command.rule else ""
        )
        body: str = (
            f"{prefix} rejected · {command.action.value} · {reason}{rule_suffix}"
        )
    else:
        body_opt = body_for_status.get(command.status)
        if body_opt is None:
            return None
        body = body_opt
    # Skip purely internal echoes — when a freshly created command starts at
    # SUBMITTED *and* immediately advances on the same tick we surface only
    # the terminal-for-this-tick state.
    if prev is None and command.status == CommandStatus.SUBMITTED:
        return None
    return Event(
        kind=EventKind.OPERATOR,
        agent_id=None,
        mission_id=command.mission_id,
        body=body,
        action_label=None,
        source=command.source,
    )
