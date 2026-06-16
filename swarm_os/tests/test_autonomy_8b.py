"""Phase 8.B — full decision set (+ WAIT) and per-scenario thresholds.

Covers what Phase 8.B adds on top of the Phase 7.B baseline
(`test_autonomy.py`):

  * `decide_all` returns exactly one disposition per anomaly, with an
    explicit WAIT verdict on every non-firing case (the dead band, the
    debounce/idle/stale windows, an in-flight command, hold_patrol, and
    every non-actionable anomaly state).
  * Per-scenario thresholds resolve by `AnomalyKind` — intrusion holds a
    higher escalate bar, search a lower dismiss ceiling — without changing
    the wildfire tuning the Phase 7.B suite pins.
  * The `AutonomyConfig` / `AutonomyProfile` loader: YAML round-trip,
    built-in fallback, kind→profile routing, and the band/routing guards.
  * Every disposition `reason` is voice-clean.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
import yaml
from pydantic import ValidationError
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
    AnomalyDisposition,
    AutonomyVerdict,
    decide_all,
    tick,
)
from swarm_os.autonomy_config import (
    AutonomyConfig,
    AutonomyProfile,
    load_autonomy_config,
)
from swarm_os.state import VINEYARD_CENTER, SwarmState

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _anomaly(
    *,
    aid: str = "a-1",
    kind: AnomalyKind = AnomalyKind.SMOKE,
    confidence: float = 0.7,
    state: AnomalyState = AnomalyState.PENDING,
    age_s: float = 30.0,
) -> AnomalyView:
    return AnomalyView(
        id=aid,
        kind=kind,
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


def _only(dispositions: list[AnomalyDisposition], aid: str) -> AnomalyDisposition:
    matches = [d for d in dispositions if d.anomaly_id == aid]
    assert len(matches) == 1, f"expected exactly one disposition for {aid}"
    return matches[0]


# ── decide_all: one disposition per anomaly, WAIT is explicit ────────────────


def test_decide_all_emits_one_disposition_per_anomaly() -> None:
    state = _state(
        _anomaly(aid="a-verify", confidence=0.62),
        _anomaly(aid="a-wait", confidence=0.40),  # wildfire dead band
        _anomaly(aid="a-dismiss", confidence=0.10),
    )
    dispositions = decide_all(state, NOW)
    assert {d.anomaly_id for d in dispositions} == {"a-verify", "a-wait", "a-dismiss"}
    assert len(dispositions) == 3


def test_dead_band_is_explicit_wait() -> None:
    """0.40 SMOKE sits in wildfire's [0.30, 0.50) band → WAIT, no rule."""

    state = _state(_anomaly(confidence=0.40))
    disposition = _only(decide_all(state, NOW), "a-1")
    assert disposition.verdict is AutonomyVerdict.WAIT
    assert disposition.rule is None
    assert disposition.profile == "wildfire"


def test_debounce_window_is_wait_then_verify() -> None:
    """Inside the debounce window → WAIT; past it → VERIFY (R1)."""

    fresh = _anomaly(confidence=0.62, age_s=AUTO_VERIFY_DEBOUNCE_S - 0.5)
    waiting = _only(decide_all(_state(fresh), NOW), "a-1")
    assert waiting.verdict is AutonomyVerdict.WAIT
    assert "debounce" in waiting.reason

    aged = _anomaly(confidence=0.62, age_s=AUTO_VERIFY_DEBOUNCE_S + 0.5)
    firing = _only(decide_all(_state(aged), NOW), "a-1")
    assert firing.verdict is AutonomyVerdict.VERIFY
    assert firing.rule == "R1"


def test_hold_patrol_yields_wait_disposition() -> None:
    state = _state(_anomaly(confidence=0.71))
    state.hold_patrol = True
    disposition = _only(decide_all(state, NOW), "a-1")
    assert disposition.verdict is AutonomyVerdict.WAIT
    assert disposition.reason == "patrol held by operator"


def test_in_flight_verify_yields_wait_disposition() -> None:
    anomaly = _anomaly(confidence=0.71)
    state = _state(anomaly)
    state.commands["op-existing"] = OperatorCommand(
        id="op-existing",
        action=OperatorAction.VERIFY,
        target=f"anomaly:{anomaly.id}",
        operator_id="op-alice01",
        status=CommandStatus.ACCEPTED,
    )
    disposition = _only(decide_all(state, NOW), "a-1")
    assert disposition.verdict is AutonomyVerdict.WAIT
    assert disposition.reason == "verification already in flight"


@pytest.mark.parametrize(
    "state_value",
    [
        AnomalyState.VERIFYING,
        AnomalyState.DISMISSED,
        AnomalyState.ESCALATED,
        AnomalyState.MARKED_KNOWN,
    ],
)
def test_non_actionable_states_are_wait(state_value: AnomalyState) -> None:
    anomaly = _anomaly(confidence=0.95, state=state_value)
    disposition = _only(decide_all(_state(anomaly), NOW), "a-1")
    assert disposition.verdict is AutonomyVerdict.WAIT
    assert disposition.rule is None


def test_decide_all_ignores_autonomy_enabled_flag() -> None:
    """decide_all is pure decision logic — it decides even when the
    boot-time autonomy gate is off (the Phase 8.B-bis shadow contract)."""

    anomaly = _anomaly(confidence=0.62)
    state = _state(anomaly, autonomy_enabled=False)
    disposition = _only(decide_all(state, NOW), "a-1")
    assert disposition.verdict is AutonomyVerdict.VERIFY


# ── tick: actionable adapter still gated + WAIT-filtered ─────────────────────


def test_tick_drops_wait_and_keeps_actionable() -> None:
    state = _state(
        _anomaly(aid="a-verify", confidence=0.62),
        _anomaly(aid="a-wait", confidence=0.40),
    )
    decisions = tick(state, NOW)
    assert len(decisions) == 1
    assert decisions[0].anomaly_id == "a-verify"
    assert decisions[0].action == OperatorAction.VERIFY
    assert decisions[0].rule == "R1"


def test_tick_respects_autonomy_disabled() -> None:
    state = _state(_anomaly(confidence=0.62), autonomy_enabled=False)
    assert tick(state, NOW) == []


# ── Per-scenario thresholds resolve by AnomalyKind ──────────────────────────


def test_intrusion_holds_higher_escalate_bar() -> None:
    """A VERIFIED 0.82 INTRUSION stays WAIT (intrusion escalate floor 0.85),
    whereas the same 0.82 as a wildfire FIRE escalates (floor 0.80)."""

    intrusion = _anomaly(
        aid="a-intr",
        kind=AnomalyKind.INTRUSION,
        confidence=0.82,
        state=AnomalyState.VERIFIED,
        age_s=60.0,
    )
    d_intr = _only(decide_all(_state(intrusion), NOW), "a-intr")
    assert d_intr.profile == "intrusion"
    assert d_intr.verdict is AutonomyVerdict.WAIT

    fire = _anomaly(
        aid="a-fire",
        kind=AnomalyKind.FIRE,
        confidence=0.82,
        state=AnomalyState.VERIFIED,
        age_s=60.0,
    )
    d_fire = _only(decide_all(_state(fire), NOW), "a-fire")
    assert d_fire.profile == "wildfire"
    assert d_fire.verdict is AutonomyVerdict.ESCALATE


def test_search_holds_lower_dismiss_ceiling() -> None:
    """A faint 0.25 HEAT_SPOT survives in search (dismiss ceil 0.20) — it
    sits in the dead band — but a 0.25 SMOKE auto-dismisses in wildfire
    (dismiss ceil 0.30) once stale."""

    heat = _anomaly(
        aid="a-heat",
        kind=AnomalyKind.HEAT_SPOT,
        confidence=0.25,
        age_s=120.0,
    )
    d_heat = _only(decide_all(_state(heat), NOW), "a-heat")
    assert d_heat.profile == "search"
    assert d_heat.verdict is AutonomyVerdict.WAIT

    smoke = _anomaly(aid="a-smoke", kind=AnomalyKind.SMOKE, confidence=0.25, age_s=120.0)
    d_smoke = _only(decide_all(_state(smoke), NOW), "a-smoke")
    assert d_smoke.profile == "wildfire"
    assert d_smoke.verdict is AutonomyVerdict.DISMISS


def test_unknown_kind_uses_default_profile() -> None:
    anomaly = _anomaly(kind=AnomalyKind.UNKNOWN, confidence=0.62)
    disposition = _only(decide_all(_state(anomaly), NOW), "a-1")
    assert disposition.profile == "default"
    assert disposition.verdict is AutonomyVerdict.VERIFY


def test_config_override_changes_verdict() -> None:
    """Passing an explicit config overrides the process default."""

    strict = AutonomyConfig(default=AutonomyProfile(verify_floor=0.90))
    anomaly = _anomaly(kind=AnomalyKind.UNKNOWN, confidence=0.62)
    disposition = _only(decide_all(_state(anomaly), NOW, config=strict), "a-1")
    assert disposition.verdict is AutonomyVerdict.WAIT


# ── Back-compat: module constants == built-in default profile ───────────────


def test_module_constants_match_builtin_default_profile() -> None:
    """The Phase 7.B constants must equal the config `default` profile so the
    legacy imports and the YAML stay a single source of truth."""

    default = load_autonomy_config().default
    assert default.verify_floor == AUTO_VERIFY_FLOOR
    assert default.verify_debounce_s == AUTO_VERIFY_DEBOUNCE_S
    assert default.escalate_floor == AUTO_ESCALATE_FLOOR
    assert default.escalate_idle_s == AUTO_ESCALATE_IDLE_S
    assert default.dismiss_ceil == AUTO_DISMISS_CEIL
    assert default.dismiss_stale_s == AUTO_DISMISS_STALE_S


def test_committed_yaml_matches_builtin_default() -> None:
    """The shipped `infra/config/autonomy.yaml` must mirror the in-code
    fallback so file-present and file-absent boots are identical."""

    from swarm_os.autonomy_config import DEFAULT_CONFIG_PATH, _builtin_autonomy_config

    assert DEFAULT_CONFIG_PATH.is_file()
    assert load_autonomy_config() == _builtin_autonomy_config()


# ── Config loader: YAML round-trip + validation guards ──────────────────────


def test_loader_round_trips_yaml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = {
        "default": {"verify_floor": 0.5},
        "profiles": {"wildfire": {"verify_floor": 0.4, "escalate_floor": 0.7}},
        "kind_to_profile": {"SMOKE": "wildfire"},
    }
    path = tmp_path / "autonomy.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_autonomy_config(config_path=path)
    assert config.profile_for(AnomalyKind.SMOKE).verify_floor == 0.4
    assert config.profile_name_for(AnomalyKind.SMOKE) == "wildfire"
    # An unmapped kind falls back to default.
    assert config.profile_name_for(AnomalyKind.INTRUSION) == "default"


def test_loader_falls_back_when_file_absent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from swarm_os.autonomy_config import _builtin_autonomy_config

    missing = tmp_path / "does-not-exist.yaml"
    assert load_autonomy_config(config_path=missing) == _builtin_autonomy_config()


def test_inverted_band_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AutonomyProfile(verify_floor=0.40, dismiss_ceil=0.50)


def test_routing_to_undefined_profile_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AutonomyConfig(
            profiles={"wildfire": AutonomyProfile()},
            kind_to_profile={AnomalyKind.INTRUSION: "ghost"},
        )


def test_unknown_yaml_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AutonomyProfile.model_validate({"verify_floor": 0.5, "typo_field": 1})


# ── Voice: every disposition reason is voice-clean ──────────────────────────


def test_all_disposition_reasons_are_voice_clean() -> None:
    """Drive every verdict branch and assert no forbidden voice token."""

    state = _state(
        _anomaly(aid="r1", kind=AnomalyKind.SMOKE, confidence=0.62),
        _anomaly(aid="dead", kind=AnomalyKind.SMOKE, confidence=0.40),
        _anomaly(aid="r3", kind=AnomalyKind.SMOKE, confidence=0.10, age_s=120.0),
        _anomaly(
            aid="r2",
            kind=AnomalyKind.FIRE,
            confidence=0.88,
            state=AnomalyState.VERIFIED,
            age_s=60.0,
        ),
        _anomaly(
            aid="below",
            kind=AnomalyKind.HEAT_SPOT,
            confidence=0.55,
            state=AnomalyState.VERIFIED,
            age_s=60.0,
        ),
        _anomaly(aid="term", confidence=0.9, state=AnomalyState.ESCALATED),
    )
    for disposition in decide_all(state, NOW):
        assert not has_forbidden(disposition.reason), (
            f"voice violation in reason: {disposition.reason!r}"
        )
