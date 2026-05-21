"""Phase 7.C — Event.source projection from OperatorCommand.source.

The event detector's `_command_event` reads ``command.source`` and:

* switches the body copy ("operator intent submitted · verify" vs.
  "autonomy verify dispatched · R1");
* stamps ``Event.source`` to match the command.

Voice grep on every emitted body returns zero hits against
``FORBIDDEN_WORDS`` per ``CLAUDE.md`` §design system.
"""

from __future__ import annotations

from datetime import UTC, datetime

from swarm_core.messages import (
    CommandStatus,
    EventKind,
    OperatorAction,
    OperatorCommand,
)
from swarm_core.voice import has_forbidden

from swarm_os.event_detector import _command_event


def _autonomy_cmd(
    *,
    action: OperatorAction = OperatorAction.VERIFY,
    rule: str | None = "R1",
    status: CommandStatus = CommandStatus.ACCEPTED,
) -> OperatorCommand:
    return OperatorCommand(
        action=action,
        target="anomaly:a-1",
        operator_id="swarmos-autonomy",
        source="autonomy",
        rule=rule,
        status=status,
        accepted_at=datetime.now(UTC),
        ts=datetime.now(UTC),
    )


def _operator_cmd(
    *,
    action: OperatorAction = OperatorAction.VERIFY,
    status: CommandStatus = CommandStatus.ACCEPTED,
) -> OperatorCommand:
    return OperatorCommand(
        action=action,
        target="anomaly:a-1",
        operator_id="op-test",
        source="operator",
        status=status,
        accepted_at=datetime.now(UTC),
        ts=datetime.now(UTC),
    )


def test_autonomy_command_emits_source_autonomy_body() -> None:
    cmd = _autonomy_cmd(action=OperatorAction.VERIFY, rule="R1")
    event = _command_event(cmd, prev=CommandStatus.SUBMITTED)
    assert event is not None
    assert event.kind == EventKind.OPERATOR
    assert event.source == "autonomy"
    assert event.body == "autonomy verify dispatched · R1"


def test_operator_command_keeps_legacy_body() -> None:
    cmd = _operator_cmd(action=OperatorAction.VERIFY)
    event = _command_event(cmd, prev=CommandStatus.SUBMITTED)
    assert event is not None
    assert event.source == "operator"
    assert event.body == "operator intent accepted · verify"


def test_voice_grep_on_new_autonomy_copy() -> None:
    """Every body string for autonomy events stays inside the voice band."""

    actions_rules = [
        (OperatorAction.VERIFY, "R1"),
        (OperatorAction.ESCALATE, "R2"),
        (OperatorAction.DISMISS, "R3"),
    ]
    statuses = [
        CommandStatus.SUBMITTED,
        CommandStatus.ACCEPTED,
        CommandStatus.IN_FLIGHT,
        CommandStatus.COMPLETED,
        CommandStatus.TIMED_OUT,
        CommandStatus.REJECTED,
    ]
    seen_bodies: set[str] = set()
    for action, rule in actions_rules:
        for status in statuses:
            cmd = _autonomy_cmd(action=action, rule=rule, status=status)
            # prev != None so the SUBMITTED row also emits an event.
            event = _command_event(cmd, prev=CommandStatus.SUBMITTED)
            if event is None:
                continue
            seen_bodies.add(event.body)
            assert not has_forbidden(event.body), event.body
    assert any("· R1" in b for b in seen_bodies)
    assert any("· R2" in b for b in seen_bodies)
    assert any("· R3" in b for b in seen_bodies)


def test_emergency_stop_stays_operator_source() -> None:
    """A commander EMERGENCY_RTL_ALL is operator-issued, not autonomy."""

    cmd = OperatorCommand(
        action=OperatorAction.EMERGENCY_RTL_ALL,
        target="fleet:all",
        operator_id="op-cmdr",
        source="operator",
        status=CommandStatus.ACCEPTED,
        accepted_at=datetime.now(UTC),
        ts=datetime.now(UTC),
    )
    event = _command_event(cmd, prev=CommandStatus.SUBMITTED)
    assert event is not None
    assert event.source == "operator"
    assert "operator intent accepted" in event.body
