"""Operator intent validation and in-memory application."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from swarm_core.messages import (
    AnomalyState,
    CommandStatus,
    Event,
    EventKind,
    MissionPhase,
    MissionView,
    OperatingMode,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
)

from swarm_os.state import SwarmState


@dataclass(frozen=True)
class CommandResult:
    command_id: str
    status: CommandStatus
    rejected_reason: RejectedReason | None = None

    def as_response(self) -> dict[str, str | None]:
        body: dict[str, str | None] = {
            "command_id": self.command_id,
            "status": self.status.value,
        }
        if self.rejected_reason is not None:
            body["rejected_reason"] = self.rejected_reason.value
        return body


async def submit(state: SwarmState, command: OperatorCommand) -> CommandResult:
    """Validate, apply, and audit an operator intent."""

    async with state.lock:
        reason = _validate_target(state, command)
        if reason is not None:
            rejected = command.model_copy(
                update={"status": CommandStatus.REJECTED, "rejected_reason": reason}
            )
            _append_operator_event(state, rejected)
            return CommandResult(command.id, CommandStatus.REJECTED, reason)

        accepted = command.model_copy(update={"status": CommandStatus.ACCEPTED})
        _apply(state, accepted)
        _append_operator_event(state, accepted)
        return CommandResult(command.id, CommandStatus.ACCEPTED)


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
        return None if target_kind == "anomaly" and target_id in state.anomalies else RejectedReason.TARGET_NOT_FOUND
    if command.action == OperatorAction.RETURN:
        return None if target_kind == "unit" and target_id in state.units else RejectedReason.TARGET_NOT_FOUND
    return RejectedReason.POLICY_DENY


def _apply(state: SwarmState, command: OperatorCommand) -> None:
    now = datetime.now(UTC)
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
                update={"state": AnomalyState.VERIFYING, "ts": now}
            )
        state.mode = OperatingMode.VERIFICATION
    elif command.action == OperatorAction.HOLD_PATROL:
        state.mode = OperatingMode.REST
    elif command.action == OperatorAction.DISMISS:
        anomaly = state.anomalies[target_id]
        state.anomalies[target_id] = anomaly.model_copy(
            update={"state": AnomalyState.DISMISSED, "ts": now}
        )
    elif command.action == OperatorAction.RETURN:
        mission = MissionView(
            id=f"cmd-{command.id}",
            kind="RTL_DOCK",
            assigned_agent=target_id,
            phase=MissionPhase.ACCEPTED,
            progress_pct=0.0,
            ts=now,
        )
        state.missions[mission.id] = mission


def _append_operator_event(state: SwarmState, command: OperatorCommand) -> None:
    action_label = {
        OperatorAction.VERIFY: "Verify sector",
        OperatorAction.HOLD_PATROL: "Hold patrol",
        OperatorAction.DISMISS: "Dismiss anomaly",
        OperatorAction.RETURN: "Return unit",
    }.get(command.action, "Operator intent")
    state.append_event(
        Event(
            kind=EventKind.OPERATOR,
            body=f"{action_label} · {command.status.value}",
            action_label=action_label,
        )
    )
