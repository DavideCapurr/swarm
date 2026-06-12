"""Operator intent validation, lifecycle, and audit storage.

Phase 3 grows the bus to a full command lifecycle:

    submitted → accepted → in_flight → completed | rejected | timed_out

`submit()` is pure mutation: it validates the intent, mutates `state.commands`
+ side-effect state (missions, anomalies, hold-patrol flag), and returns a
`CommandResult`. It does not append `Event`s — the `EventDetector` picks up
the new status from the commands dict on the next coordinator refresh.

`tick()` advances `ACCEPTED` commands to `IN_FLIGHT` once their linked
mission leaves PENDING, and from `IN_FLIGHT` to `COMPLETED` / `TIMED_OUT`
based on the linked mission's terminal phase or a wall-clock deadline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from swarm_core.messages import (
    AgentState,
    AnomalyState,
    CommandStatus,
    MissionPhase,
    MissionView,
    OperatingMode,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
)

from swarm_os.state import SwarmState

ACCEPTED_TIMEOUT_S = 30.0  # accepted but not yet in flight → timed_out
IN_FLIGHT_TIMEOUT_S = 180.0  # in flight without a terminal mission phase → timed_out
OPERATOR_VERIFY_PRIORITY = 50  # Phase 6.A.5 — operator commands above auto-PATROL
OPERATOR_RETURN_PRIORITY = 80  # but below auto-RTL (100)
# Phase 6.G — fleet-wide emergency RTL outranks every other mission so the
# command bus / scheduler cannot starve it.
EMERGENCY_RTL_PRIORITY = 200
EMERGENCY_FLEET_TARGET = "fleet:all"
EMERGENCY_MISSION_PREFIX = "emergency-rtl-"
# Phase 7.B — autonomy decisions sit between auto-PATROL (10) and operator
# VERIFY (50), so an operator intent cleanly preempts any in-flight autonomy
# mission at every level. The synthetic operator-id is intentionally outside
# the API operator-id regex (`^op-[a-z0-9]{4,32}$`) so a forged HTTP body
# cannot reach the autonomy lane — autonomy must inject via the in-process
# `command_submit()` path.
AUTONOMY_PRIORITY = 40
AUTONOMY_OPERATOR_ID = "swarmos-autonomy"
# FSM states for units that are *not* candidates for emergency RTL: already
# safely on the ground or unreachable. Everything else gets an RTL queued.
_GROUNDED_STATES = frozenset(
    {AgentState.DOCKED, AgentState.OFFLINE, AgentState.ERROR}
)


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    status: CommandStatus
    rejected_reason: RejectedReason | None = None
    mission_id: str | None = None

    def as_response(self) -> dict[str, str | None]:
        body: dict[str, str | None] = {
            "command_id": self.command_id,
            "status": self.status.value,
        }
        if self.rejected_reason is not None:
            body["rejected_reason"] = self.rejected_reason.value
        if self.mission_id is not None:
            body["mission_id"] = self.mission_id
        return body


async def submit(state: SwarmState, command: OperatorCommand) -> CommandResult:
    """Validate, apply, and store an operator intent (acquires state.lock)."""

    async with state.lock:
        return submit_locked(state, command, datetime.now(UTC))


def submit_locked(
    state: SwarmState, command: OperatorCommand, now: datetime
) -> CommandResult:
    """Lock-free variant for in-process callers that already hold `state.lock`.

    Phase 7.B uses this from the coordinator's `_refresh_async` so autonomy
    decisions land in the audit log without re-entering the lock (asyncio
    locks are non-reentrant). Same semantics as `submit()` otherwise — same
    validation, same policy gate, same audit record.
    """

    reason = _validate_target(state, command)
    if reason is None and command.action != OperatorAction.EMERGENCY_RTL_ALL:
        # Phase 6.A: policy gate. Build the would-be mission and let the
        # engine reject for geofence / battery / link / weather reasons
        # before we mutate state. HOLD_PATROL / DISMISS return None here
        # — they create no mission and have no policy surface.
        #
        # Phase 6.G: EMERGENCY_RTL_ALL deliberately skips this gate. An
        # emergency stop must dispatch RTL even when battery is low or
        # the link is degraded — the alternative is letting the unit
        # stay airborne in exactly the conditions that triggered the
        # emergency. The audit event records the bypass (§2.G).
        tentative = _tentative_mission(state, command, now)
        if tentative is not None:
            decision = state.policy.validate_mission(
                tentative, units=state.units, docks=state.docks
            )
            if not decision.allowed and decision.reason is not None:
                reason = decision.reason
    if reason is not None:
        rejected = command.model_copy(
            update={
                "status": CommandStatus.REJECTED,
                "rejected_reason": reason,
                "completed_at": now,
                "ts": now,
            }
        )
        state.commands[rejected.id] = rejected
        return CommandResult(command.id, CommandStatus.REJECTED, reason)

    mission_id = _apply(state, command, now)
    # Commands without an external mission (hold-patrol, dismiss) finish
    # the instant they are applied — there is nothing to wait on.
    if mission_id is None:
        accepted = command.model_copy(
            update={
                "status": CommandStatus.COMPLETED,
                "accepted_at": now,
                "in_flight_at": now,
                "completed_at": now,
                "ts": now,
            }
        )
    else:
        accepted = command.model_copy(
            update={
                "status": CommandStatus.ACCEPTED,
                "accepted_at": now,
                "mission_id": mission_id,
                "ts": now,
            }
        )
    state.commands[accepted.id] = accepted
    return CommandResult(command.id, accepted.status, mission_id=mission_id)


def tick(state: SwarmState, now: datetime) -> None:
    """Progress every non-terminal command. Pure mutation, no events."""

    for command_id, command in list(state.commands.items()):
        if command.status in {
            CommandStatus.COMPLETED,
            CommandStatus.REJECTED,
            CommandStatus.TIMED_OUT,
        }:
            continue

        mission = (
            state.missions.get(command.mission_id) if command.mission_id else None
        )

        if command.status == CommandStatus.ACCEPTED:
            if mission is not None and mission.phase not in {
                MissionPhase.PENDING,
                MissionPhase.BIDDING,
                MissionPhase.ACCEPTED,
            }:
                state.commands[command_id] = command.model_copy(
                    update={
                        "status": CommandStatus.IN_FLIGHT,
                        "in_flight_at": now,
                        "ts": now,
                    }
                )
                continue
            if command.accepted_at and (now - command.accepted_at).total_seconds() > ACCEPTED_TIMEOUT_S:
                state.commands[command_id] = command.model_copy(
                    update={
                        "status": CommandStatus.TIMED_OUT,
                        "completed_at": now,
                        "ts": now,
                    }
                )
            continue

        if command.status == CommandStatus.IN_FLIGHT:
            if mission is not None and mission.phase == MissionPhase.DONE:
                state.commands[command_id] = command.model_copy(
                    update={
                        "status": CommandStatus.COMPLETED,
                        "completed_at": now,
                        "ts": now,
                    }
                )
                continue
            if mission is not None and mission.phase == MissionPhase.FAILED:
                state.commands[command_id] = command.model_copy(
                    update={
                        "status": CommandStatus.TIMED_OUT,
                        "completed_at": now,
                        "ts": now,
                    }
                )
                continue
            if command.in_flight_at and (now - command.in_flight_at).total_seconds() > IN_FLIGHT_TIMEOUT_S:
                state.commands[command_id] = command.model_copy(
                    update={
                        "status": CommandStatus.TIMED_OUT,
                        "completed_at": now,
                        "ts": now,
                    }
                )


# ── Validation ────────────────────────────────────────────────────────────────


def _validate_target(state: SwarmState, command: OperatorCommand) -> RejectedReason | None:
    try:
        target_kind, target_id = command.target.split(":", 1)
    except ValueError:
        return RejectedReason.INVALID_TARGET_KIND

    if command.action == OperatorAction.VERIFY:
        if target_kind == "sector" and target_id in state.sectors:
            return None
        if target_kind == "anomaly" and target_id in state.anomalies:
            return None
        return RejectedReason.TARGET_NOT_FOUND
    if command.action == OperatorAction.HOLD_PATROL:
        return None if target_kind == "session" else RejectedReason.INVALID_TARGET_KIND
    if command.action == OperatorAction.DISMISS:
        return (
            None
            if target_kind == "anomaly" and target_id in state.anomalies
            else RejectedReason.TARGET_NOT_FOUND
        )
    if command.action == OperatorAction.ESCALATE:
        # Phase 7.B — escalation is a state transition on an existing
        # anomaly. No mission spawned (downstream notifications are Phase 12).
        return (
            None
            if target_kind == "anomaly" and target_id in state.anomalies
            else RejectedReason.TARGET_NOT_FOUND
        )
    if command.action == OperatorAction.RETURN:
        return (
            None
            if target_kind == "unit" and target_id in state.units
            else RejectedReason.TARGET_NOT_FOUND
        )
    if command.action == OperatorAction.EMERGENCY_RTL_ALL:
        # Hard-coded fleet-wide target. Anything else is a malformed call —
        # the audit log must never carry an attacker-chosen target string.
        if target_kind == "fleet" and target_id == "all":
            return None
        return RejectedReason.INVALID_TARGET_KIND
    return RejectedReason.POLICY_DENY


# ── Apply (state mutation) ────────────────────────────────────────────────────


def _apply(
    state: SwarmState, command: OperatorCommand, now: datetime
) -> str | None:
    """Mutate `state` for an accepted command. Returns mission id if created."""

    target_kind, target_id = command.target.split(":", 1)

    if command.action == OperatorAction.VERIFY:
        # Phase 7.B — autonomy VERIFY missions sit at AUTONOMY_PRIORITY (40),
        # below operator VERIFY (50) so an operator intent cleanly preempts.
        priority = (
            AUTONOMY_PRIORITY
            if command.source == "autonomy"
            else OPERATOR_VERIFY_PRIORITY
        )
        mission = MissionView(
            id=f"cmd-{command.id}",
            kind="VERIFY",
            sector_id=target_id if target_kind == "sector" else None,
            assigned_agent=state.verifier_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
            priority=priority,
            ts=now,
        )
        state.missions[mission.id] = mission
        if target_kind == "anomaly":
            anomaly = state.anomalies[target_id]
            state.anomalies[target_id] = anomaly.model_copy(
                update={
                    "state": AnomalyState.VERIFYING,
                    "verifying_agent": state.verifier_id,
                    "ts": now,
                }
            )
        state.mode = OperatingMode.VERIFICATION
        return mission.id

    if command.action == OperatorAction.HOLD_PATROL:
        state.hold_patrol = True
        state.mode = OperatingMode.REST
        return None

    if command.action == OperatorAction.DISMISS:
        anomaly = state.anomalies[target_id]
        state.anomalies[target_id] = anomaly.model_copy(
            update={"state": AnomalyState.DISMISSED, "ts": now}
        )
        return None

    if command.action == OperatorAction.ESCALATE:
        anomaly = state.anomalies[target_id]
        state.anomalies[target_id] = anomaly.model_copy(
            update={"state": AnomalyState.ESCALATED, "ts": now}
        )
        return None

    if command.action == OperatorAction.RETURN:
        mission = MissionView(
            id=f"cmd-{command.id}",
            kind="RTL_DOCK",
            assigned_agent=target_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
            ts=now,
        )
        state.missions[mission.id] = mission
        return mission.id

    if command.action == OperatorAction.EMERGENCY_RTL_ALL:
        _apply_emergency_rtl_all(state, command, now)
        return None

    return None


def _apply_emergency_rtl_all(
    state: SwarmState, command: OperatorCommand, now: datetime
) -> None:
    """Queue an RTL mission for every airborne unit, all at once.

    Idempotency: each unit gets at most one outstanding emergency mission
    (deduped by ``emergency-rtl-<agent_id>``). Existing emergency missions
    that have already reached a terminal phase are replaced so a second
    emergency stop on the same boot still works.

    Side-effects beyond the missions dict:
      * ``state.hold_patrol`` is forced on so the scheduler can't queue
        new patrols while the fleet is recovering.
      * ``state.emergency_active_at`` records the trigger timestamp.
      * Any *non-emergency, non-terminal* mission assigned to an airborne
        unit is force-failed so the new emergency RTL is the only thing
        bidding for that unit's attention.
    """

    state.hold_patrol = True
    state.emergency_active_at = now
    for unit_id, unit in list(state.units.items()):
        if unit.fsm_state in _GROUNDED_STATES:
            continue
        mission_id = f"{EMERGENCY_MISSION_PREFIX}{unit_id}"
        existing = state.missions.get(mission_id)
        if existing is not None and existing.phase not in {
            MissionPhase.DONE,
            MissionPhase.FAILED,
        }:
            continue
        # Cancel any other non-terminal mission this unit was assigned to.
        for other_id, other in list(state.missions.items()):
            if other.assigned_agent != unit_id or other_id == mission_id:
                continue
            if other.kind.upper() == "RTL_DOCK":
                continue
            if other.phase in {MissionPhase.DONE, MissionPhase.FAILED}:
                continue
            state.missions[other_id] = other.model_copy(
                update={"phase": MissionPhase.FAILED, "ts": now}
            )
        state.missions[mission_id] = MissionView(
            id=mission_id,
            kind="RTL_DOCK",
            assigned_agent=unit_id,
            phase=MissionPhase.PENDING,
            progress_pct=0.0,
            priority=EMERGENCY_RTL_PRIORITY,
            ts=now,
        )


# ── Convenience: wall-clock deadline helpers (used by tests) ──────────────────


def overdue_at(now: datetime) -> datetime:
    """Return a timestamp far enough in the past to trip the IN_FLIGHT timeout."""

    return now - timedelta(seconds=IN_FLIGHT_TIMEOUT_S + 1)


# ── Phase 6.A — tentative mission builder for the policy gate ────────────────


def _tentative_mission(
    state: SwarmState, command: OperatorCommand, now: datetime
) -> MissionView | None:
    """Build the MissionView that `_apply` *would* create, without mutating.

    Returned to the policy engine for geofence/battery/link/weather checks.
    Actions that don't create a mission (HOLD_PATROL, DISMISS, etc.) return
    None — they're not subject to policy validation at submit time.
    """

    target_kind, target_id = command.target.split(":", 1)
    if command.action == OperatorAction.VERIFY:
        # Geofence surface for the policy gate: sector targets contribute
        # their centroid, anomaly targets contribute the detection geo —
        # without it an anomaly VERIFY would carry no waypoints and slip
        # past the geofence check entirely.
        waypoints = []
        if target_kind == "sector":
            sector = state.sectors.get(target_id)
            if sector is not None:
                waypoints = [sector.centroid]
        elif target_kind == "anomaly":
            anomaly = state.anomalies.get(target_id)
            if anomaly is not None:
                waypoints = [anomaly.geo]
        priority = (
            AUTONOMY_PRIORITY
            if command.source == "autonomy"
            else OPERATOR_VERIFY_PRIORITY
        )
        return MissionView(
            id=f"cmd-{command.id}",
            kind="VERIFY",
            sector_id=target_id if target_kind == "sector" else None,
            assigned_agent=state.verifier_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
            waypoints=waypoints,
            priority=priority,
            ts=now,
        )
    if command.action == OperatorAction.RETURN:
        return MissionView(
            id=f"cmd-{command.id}",
            kind="RTL_DOCK",
            assigned_agent=target_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
            priority=OPERATOR_RETURN_PRIORITY,
            ts=now,
        )
    return None
