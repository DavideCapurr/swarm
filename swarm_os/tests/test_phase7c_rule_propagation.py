"""Phase 7.C — autonomy rule propagation onto OperatorCommand.

`swarm_os.autonomy.to_command()` is the single point where an
`AutonomyDecision` becomes an `OperatorCommand`. The Console reads
`command.rule` to render `AUTO · R1` / `AUTO · R2` / `AUTO · R3` —
parsing the rule out of the body string would be brittle, so the
plan persists it as a structured field.
"""

from __future__ import annotations

from swarm_core.messages import OperatorAction, OperatorCommand

from swarm_os.autonomy import AutonomyDecision, to_command


def test_to_command_stamps_rule_per_decision() -> None:
    """Every AutonomyDecision rule label flows onto the emitted command."""

    cases = [
        ("R1", OperatorAction.VERIFY, 0.62),
        ("R2", OperatorAction.ESCALATE, 0.88),
        ("R3", OperatorAction.DISMISS, 0.15),
    ]
    for rule, action, confidence in cases:
        decision = AutonomyDecision(
            anomaly_id="a-1",
            action=action,
            rule=rule,
            confidence=confidence,
        )
        cmd = to_command(decision)
        assert cmd.source == "autonomy"
        assert cmd.rule == rule
        assert cmd.action == action
        assert cmd.target == "anomaly:a-1"


def test_operator_command_keeps_rule_none() -> None:
    """An operator-built OperatorCommand has rule=None (Pydantic default)."""

    cmd = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="anomaly:a-1",
        operator_id="op-test",
    )
    assert cmd.source == "operator"
    assert cmd.rule is None
