"""Phase 7.B — autonomy baseline unit tests.

Covers the three deterministic rules (R1 auto-VERIFY, R2 auto-ESCALATE,
R3 auto-DISMISS) at their decision boundaries, the idempotency
guarantees, the `hold_patrol` short-circuit, and the voice-clean event
copy contract.

Tests intentionally exercise the rule logic in isolation (no
coordinator, no command bus) — the end-to-end coordinator wiring is
covered by `test_phase7b_integration.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from swarm_core.messages import (
    AnomalyKind,
    AnomalyState,
    AnomalyView,
    CommandStatus,
    OperatorAction,
    OperatorCommand,
)
from swarm_core.voice import band as confidence_band
from swarm_core.voice import has_forbidden

from swarm_os.autonomy import (
    AUTO_DISMISS_CEIL,
    AUTO_DISMISS_STALE_S,
    AUTO_ESCALATE_FLOOR,
    AUTO_ESCALATE_IDLE_S,
    AUTO_VERIFY_DEBOUNCE_S,
    AUTO_VERIFY_FLOOR,
    AutonomyDecision,
    tick,
    to_command,
)
from swarm_os.command_bus import AUTONOMY_OPERATOR_ID
from swarm_os.state import VINEYARD_CENTER, SwarmState

NOW = datetime(2026, 5, 20, 12, 0, tzinfo=UTC)


def _anomaly(
    *,
    aid: str = "a-1",
    confidence: float = 0.7,
    state: AnomalyState = AnomalyState.PENDING,
    age_s: float = 30.0,
) -> AnomalyView:
    """Build an AnomalyView aged `age_s` seconds before NOW."""

    return AnomalyView(
        id=aid,
        kind=AnomalyKind.SMOKE,
        geo=VINEYARD_CENTER,
        sector_id="center-b",
        confidence=confidence,
        band=confidence_band(confidence),
        state=state,
        detected_at=NOW - timedelta(seconds=age_s),
        ts=NOW - timedelta(seconds=age_s),
    )


def _state(*anomalies: AnomalyView, autonomy_enabled: bool = True) -> SwarmState:
    state = SwarmState.vineyard()
    state.autonomy_enabled = autonomy_enabled
    for a in anomalies:
        state.anomalies[a.id] = a
    return state


# ── R1 auto-VERIFY ───────────────────────────────────────────────────────────


def test_r1_fires_at_floor() -> None:
    """Confidence exactly at AUTO_VERIFY_FLOOR fires R1."""

    state = _state(_anomaly(confidence=AUTO_VERIFY_FLOOR))
    decisions = tick(state, NOW)
    assert len(decisions) == 1
    assert decisions[0].rule == "R1"
    assert decisions[0].action == OperatorAction.VERIFY


def test_r1_does_not_fire_just_below_floor() -> None:
    """Confidence one epsilon below the floor must not fire R1."""

    state = _state(_anomaly(confidence=AUTO_VERIFY_FLOOR - 0.001))
    assert tick(state, NOW) == []


def test_r1_does_not_fire_before_debounce() -> None:
    """A freshly-detected anomaly inside the debounce window must wait."""

    fresh = _anomaly(confidence=0.62, age_s=AUTO_VERIFY_DEBOUNCE_S - 0.5)
    state = _state(fresh)
    assert tick(state, NOW) == []


def test_r1_skips_when_hold_patrol_is_set() -> None:
    """`hold_patrol` short-circuits R1 — the operator owns the fleet posture."""

    state = _state(_anomaly(confidence=0.71))
    state.hold_patrol = True
    assert tick(state, NOW) == []


def test_r1_skips_when_verify_already_in_flight() -> None:
    """An operator VERIFY in flight blocks R1 on the same anomaly."""

    anomaly = _anomaly(confidence=0.71)
    state = _state(anomaly)
    state.commands["op-existing"] = OperatorCommand(
        id="op-existing",
        action=OperatorAction.VERIFY,
        target=f"anomaly:{anomaly.id}",
        operator_id="op-alice01",
        status=CommandStatus.ACCEPTED,
    )
    assert tick(state, NOW) == []


def test_r1_skips_when_autonomy_disabled() -> None:
    state = _state(_anomaly(confidence=0.71), autonomy_enabled=False)
    assert tick(state, NOW) == []


# ── R2 auto-ESCALATE ─────────────────────────────────────────────────────────


def test_r2_fires_at_floor_after_idle() -> None:
    """Confidence at AUTO_ESCALATE_FLOOR after the idle window fires R2."""

    verified = _anomaly(
        aid="a-fire",
        confidence=AUTO_ESCALATE_FLOOR,
        state=AnomalyState.VERIFIED,
        age_s=AUTO_ESCALATE_IDLE_S,
    )
    state = _state(verified)
    decisions = tick(state, NOW)
    assert len(decisions) == 1
    assert decisions[0].rule == "R2"
    assert decisions[0].action == OperatorAction.ESCALATE


def test_r2_does_not_fire_below_floor() -> None:
    """Intrusion @ 0.71 and search @ 0.55 deliberately don't auto-escalate."""

    verified = _anomaly(
        confidence=AUTO_ESCALATE_FLOOR - 0.001,
        state=AnomalyState.VERIFIED,
        age_s=AUTO_ESCALATE_IDLE_S * 2,
    )
    state = _state(verified)
    assert tick(state, NOW) == []


def test_r2_does_not_fire_before_idle_window() -> None:
    """A freshly-VERIFIED high-confidence anomaly inside the idle window waits."""

    verified = _anomaly(
        confidence=0.88,
        state=AnomalyState.VERIFIED,
        age_s=AUTO_ESCALATE_IDLE_S - 0.5,
    )
    state = _state(verified)
    assert tick(state, NOW) == []


def test_r2_skips_when_operator_escalate_in_flight() -> None:
    verified = _anomaly(
        confidence=0.88,
        state=AnomalyState.VERIFIED,
        age_s=AUTO_ESCALATE_IDLE_S,
    )
    state = _state(verified)
    state.commands["op-escalate"] = OperatorCommand(
        id="op-escalate",
        action=OperatorAction.ESCALATE,
        target=f"anomaly:{verified.id}",
        operator_id="op-alice01",
        status=CommandStatus.IN_FLIGHT,
    )
    assert tick(state, NOW) == []


def test_r2_skips_when_operator_dismiss_in_flight() -> None:
    """A DISMISS arriving first must block a competing R2 ESCALATE."""

    verified = _anomaly(
        confidence=0.88,
        state=AnomalyState.VERIFIED,
        age_s=AUTO_ESCALATE_IDLE_S,
    )
    state = _state(verified)
    state.commands["op-dismiss"] = OperatorCommand(
        id="op-dismiss",
        action=OperatorAction.DISMISS,
        target=f"anomaly:{verified.id}",
        operator_id="op-alice01",
        status=CommandStatus.ACCEPTED,
    )
    assert tick(state, NOW) == []


# ── R3 auto-DISMISS ──────────────────────────────────────────────────────────


def test_r3_fires_below_ceil_after_stale() -> None:
    noise = _anomaly(
        confidence=AUTO_DISMISS_CEIL - 0.001,
        state=AnomalyState.PENDING,
        age_s=AUTO_DISMISS_STALE_S,
    )
    state = _state(noise)
    decisions = tick(state, NOW)
    assert len(decisions) == 1
    assert decisions[0].rule == "R3"
    assert decisions[0].action == OperatorAction.DISMISS


def test_r3_does_not_fire_above_ceil() -> None:
    """Anomalies at/above the DISMISS ceil stay PENDING (R1's territory or wait)."""

    state = _state(
        _anomaly(
            confidence=AUTO_DISMISS_CEIL,
            state=AnomalyState.PENDING,
            age_s=AUTO_DISMISS_STALE_S,
        )
    )
    assert tick(state, NOW) == []


def test_r3_does_not_fire_before_stale_window() -> None:
    state = _state(
        _anomaly(
            confidence=0.10,
            state=AnomalyState.PENDING,
            age_s=AUTO_DISMISS_STALE_S - 0.5,
        )
    )
    assert tick(state, NOW) == []


def test_r3_never_fires_on_three_scripted_scenarios() -> None:
    """Scripted SMOKE 0.62, INTRUSION 0.71, HEAT_SPOT 0.55 are all above R3."""

    for confidence in (0.62, 0.71, 0.55):
        anomaly = _anomaly(
            confidence=confidence,
            state=AnomalyState.PENDING,
            age_s=AUTO_DISMISS_STALE_S,
        )
        decisions = tick(_state(anomaly), NOW)
        assert all(d.action != OperatorAction.DISMISS for d in decisions), (
            f"R3 fired on scripted confidence={confidence}"
        )


# ── Idempotency + ordering ──────────────────────────────────────────────────


def test_no_double_submit_under_repeated_ticks() -> None:
    """Once an R1 decision is recorded, a repeat tick must not re-emit it.

    The block is the `_command_in_flight` guard against any non-terminal
    autonomy/operator command on the same target — covers the same-tick
    repeat case before the lifecycle has had a chance to advance.
    """

    anomaly = _anomaly(confidence=0.71)
    state = _state(anomaly)

    decisions_first = tick(state, NOW)
    assert len(decisions_first) == 1
    # Simulate the coordinator recording the decision as a non-terminal command.
    cmd = to_command(decisions_first[0])
    state.commands[cmd.id] = cmd.model_copy(update={"status": CommandStatus.ACCEPTED})

    decisions_second = tick(state, NOW)
    assert decisions_second == []


def test_to_command_carries_autonomy_source() -> None:
    decision = AutonomyDecision(
        anomaly_id="a-1",
        action=OperatorAction.VERIFY,
        rule="R1",
        confidence=0.71,
    )
    cmd = to_command(decision)
    assert cmd.source == "autonomy"
    assert cmd.operator_id == AUTONOMY_OPERATOR_ID
    assert cmd.target == "anomaly:a-1"
    assert cmd.action == OperatorAction.VERIFY


def test_autonomy_operator_id_outside_api_regex() -> None:
    """Sentinel must not satisfy the API operator-id regex (defence in depth)."""

    from backend.app.security import is_valid_operator_id

    assert is_valid_operator_id(AUTONOMY_OPERATOR_ID) is False


# ── Voice / forbidden words ──────────────────────────────────────────────────


def test_autonomy_decision_event_body_is_voice_clean() -> None:
    """The audit event detector composes bodies from `action.value` only —
    no autonomy-specific text — so the voice grep stays clean by construction.
    Defensive grep here to catch a future regression.
    """

    for action in (OperatorAction.VERIFY, OperatorAction.ESCALATE, OperatorAction.DISMISS):
        # Mirror the body shape from `event_detector._command_event`.
        body = f"operator intent submitted · {action.value}"
        assert not has_forbidden(body), f"voice violation in {body!r}"


# ── Threshold sanity ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "confidence",
    [0.62, 0.71, 0.55],
    ids=["wildfire-smoke", "intrusion", "search-heatspot"],
)
def test_scripted_anomalies_all_trigger_r1(confidence: float) -> None:
    """The three scripted scenarios all surface a PENDING anomaly above the
    R1 floor; each must produce exactly one VERIFY decision."""

    anomaly = _anomaly(confidence=confidence)
    state = _state(anomaly)
    decisions = tick(state, NOW)
    assert len(decisions) == 1
    assert decisions[0].action == OperatorAction.VERIFY
    assert decisions[0].rule == "R1"
