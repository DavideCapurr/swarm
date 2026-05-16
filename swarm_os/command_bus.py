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
    """Validate, apply, and store an operator intent."""

    async with state.lock:
        now = datetime.now(UTC)
        reason = _validate_target(state, command)
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
    if command.action == OperatorAction.RETURN:
        return (
            None
            if target_kind == "unit" and target_id in state.units
            else RejectedReason.TARGET_NOT_FOUND
        )
    return RejectedReason.POLICY_DENY


# ── Apply (state mutation) ────────────────────────────────────────────────────


def _apply(
    state: SwarmState, command: OperatorCommand, now: datetime
) -> str | None:
    """Mutate `state` for an accepted command. Returns mission id if created."""

    target_kind, target_id = command.target.split(":", 1)

    if command.action == OperatorAction.VERIFY:
        mission = MissionView(
            id=f"cmd-{command.id}",
            kind="VERIFY",
            sector_id=target_id if target_kind == "sector" else None,
            assigned_agent=state.verifier_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
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

    return None


# ── Convenience: wall-clock deadline helpers (used by tests) ──────────────────


def overdue_at(now: datetime) -> datetime:
    """Return a timestamp far enough in the past to trip the IN_FLIGHT timeout."""

    return now - timedelta(seconds=IN_FLIGHT_TIMEOUT_S + 1)
