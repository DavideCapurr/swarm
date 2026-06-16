"""Phase 8.B-bis — shadow mode: baseline oracle + divergence report.

Three things this milestone must prove:

  1. The human-baseline oracle (`BaselineOracle`) decides on the *observable*
     signal only — kind, confidence, lifecycle state, hold_patrol — in PDF
     voice bands, with the documented per-scenario intent. No ground-truth
     peeking, so the same policy transfers out of the sim.
  2. The shadow harness (`shadow_step` + `ShadowDecisionLog` +
     `DivergenceReport`) pairs candidate-vs-baseline verdicts per anomaly and
     bounds the divergence at the Phase 8 ``< 5%`` gate — a gate with teeth
     (it must *fail* above 5%, not just pass below).
  3. On the real three scenarios the deterministic engine matches the
     oracle: overall divergence 0% (readiness rule 6 — exercise the real
     decider + real configs + real scenario YAMLs, not a stub).
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
    ConfidenceBand,
)
from swarm_core.voice import band as confidence_band
from swarm_core.voice import has_forbidden

from swarm_os.autonomy import AnomalyDisposition, AutonomyVerdict, decide_all
from swarm_os.shadow import (
    GATE_DIVERGENCE,
    DivergenceReport,
    ShadowDecisionLog,
    ShadowEntry,
    engine_decider,
    oracle_decider,
    shadow_step,
)
from swarm_os.shadow_oracle import (
    BaselineOracle,
    OracleConfig,
    OracleProfile,
    load_oracle_config,
)
from swarm_os.state import VINEYARD_CENTER, SwarmState

NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


def _anomaly(
    *,
    aid: str = "a-1",
    kind: AnomalyKind = AnomalyKind.SMOKE,
    confidence: float = 0.7,
    state: AnomalyState = AnomalyState.PENDING,
    age_s: float = 1_000_000.0,
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


def _state(*anomalies: AnomalyView, hold_patrol: bool = False) -> SwarmState:
    state = SwarmState.vineyard()
    state.hold_patrol = hold_patrol
    for a in anomalies:
        state.anomalies[a.id] = a
    return state


def _verdict(oracle: BaselineOracle, anomaly: AnomalyView, **state_kw: bool) -> AutonomyVerdict:
    state = _state(anomaly, **state_kw)
    dispositions = oracle.decide_all(state, NOW)
    assert len(dispositions) == 1
    return dispositions[0].verdict


# ── Oracle dispositions, per scenario, on the observable signal ──────────────


def test_oracle_one_disposition_per_anomaly() -> None:
    oracle = BaselineOracle()
    state = _state(
        _anomaly(aid="a", confidence=0.7),
        _anomaly(aid="b", confidence=0.1),
        _anomaly(aid="c", confidence=0.4),
    )
    dispositions = oracle.decide_all(state, NOW)
    assert {d.anomaly_id for d in dispositions} == {"a", "b", "c"}
    assert all(isinstance(d, AnomalyDisposition) and d.rule is None for d in dispositions)


def test_wildfire_oracle_verifies_elevated_smoke_and_escalates_verified_fire() -> None:
    oracle = BaselineOracle()
    # SMOKE 0.62 (elevated) PENDING -> VERIFY; VERIFIED 0.62 (elevated) -> hold.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.SMOKE, confidence=0.62))
        is AutonomyVerdict.VERIFY
    )
    assert (
        _verdict(
            oracle,
            _anomaly(kind=AnomalyKind.SMOKE, confidence=0.62, state=AnomalyState.VERIFIED),
        )
        is AutonomyVerdict.WAIT
    )
    # FIRE 0.88 (verified band) PENDING -> VERIFY; VERIFIED -> ESCALATE.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.FIRE, confidence=0.88))
        is AutonomyVerdict.VERIFY
    )
    assert (
        _verdict(
            oracle,
            _anomaly(kind=AnomalyKind.FIRE, confidence=0.88, state=AnomalyState.VERIFIED),
        )
        is AutonomyVerdict.ESCALATE
    )


def test_intrusion_oracle_reserves_escalation_for_operator() -> None:
    oracle = BaselineOracle()
    intrusion_verified = _anomaly(
        kind=AnomalyKind.INTRUSION, confidence=0.95, state=AnomalyState.VERIFIED
    )
    # Even a verified-band 0.95 intrusion is NOT auto-escalated — delegated.
    assert _verdict(oracle, intrusion_verified) is AutonomyVerdict.WAIT
    # But an elevated PENDING intrusion is verified.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.INTRUSION, confidence=0.71))
        is AutonomyVerdict.VERIFY
    )


def test_search_oracle_verifies_faint_heat_spot() -> None:
    """Search verifies a low-confidence heat-spot (life-safety) where wildfire
    would only hold — the per-scenario divergence in the oracle itself."""

    oracle = BaselineOracle()
    # 0.55 HEAT_SPOT is low-confidence band, yet search VERIFIES it.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.HEAT_SPOT, confidence=0.55))
        is AutonomyVerdict.VERIFY
    )
    # The same 0.55 as wildfire SMOKE (verify_band elevated) only holds.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.SMOKE, confidence=0.55))
        is AutonomyVerdict.WAIT
    )
    # A truly faint heat-spot below the search dismiss floor (0.15) dismisses.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.HEAT_SPOT, confidence=0.10))
        is AutonomyVerdict.DISMISS
    )


def test_oracle_dead_band_and_dismiss_for_wildfire() -> None:
    oracle = BaselineOracle()
    # 0.40 SMOKE: above dismiss floor 0.30, below elevated band -> WAIT.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.SMOKE, confidence=0.40))
        is AutonomyVerdict.WAIT
    )
    # 0.20 SMOKE: below dismiss floor 0.30 -> DISMISS.
    assert (
        _verdict(oracle, _anomaly(kind=AnomalyKind.SMOKE, confidence=0.20))
        is AutonomyVerdict.DISMISS
    )


def test_oracle_unknown_kind_uses_default_profile() -> None:
    oracle = BaselineOracle()
    state = _state(_anomaly(kind=AnomalyKind.UNKNOWN, confidence=0.7))
    disposition = oracle.decide_all(state, NOW)[0]
    assert disposition.profile == "default"
    assert disposition.verdict is AutonomyVerdict.VERIFY  # elevated band, default


def test_oracle_hold_patrol_and_terminal_states_wait() -> None:
    oracle = BaselineOracle()
    assert (
        _verdict(oracle, _anomaly(confidence=0.9), hold_patrol=True)
        is AutonomyVerdict.WAIT
    )
    for terminal in (
        AnomalyState.VERIFYING,
        AnomalyState.DISMISSED,
        AnomalyState.ESCALATED,
        AnomalyState.MARKED_KNOWN,
    ):
        assert (
            _verdict(oracle, _anomaly(confidence=0.95, state=terminal))
            is AutonomyVerdict.WAIT
        )


def test_oracle_decides_regardless_of_autonomy_enabled() -> None:
    """A shadow reference decides even when the live engine is disarmed."""

    oracle = BaselineOracle()
    state = _state(_anomaly(kind=AnomalyKind.SMOKE, confidence=0.62))
    state.set_autonomy_enabled(False)
    assert oracle.decide_all(state, NOW)[0].verdict is AutonomyVerdict.VERIFY


def test_all_oracle_reasons_are_voice_clean() -> None:
    oracle = BaselineOracle()
    state = _state(
        _anomaly(aid="verify", kind=AnomalyKind.SMOKE, confidence=0.62),
        _anomaly(aid="dead", kind=AnomalyKind.SMOKE, confidence=0.40),
        _anomaly(aid="dismiss", kind=AnomalyKind.SMOKE, confidence=0.10),
        _anomaly(
            aid="escalate",
            kind=AnomalyKind.FIRE,
            confidence=0.90,
            state=AnomalyState.VERIFIED,
        ),
        _anomaly(
            aid="delegated",
            kind=AnomalyKind.INTRUSION,
            confidence=0.95,
            state=AnomalyState.VERIFIED,
        ),
        _anomaly(aid="terminal", confidence=0.9, state=AnomalyState.ESCALATED),
    )
    for d in oracle.decide_all(state, NOW):
        assert not has_forbidden(d.reason), f"voice violation: {d.reason!r}"
    # And the hold-patrol branch.
    held = oracle.decide_all(_state(_anomaly(confidence=0.9), hold_patrol=True), NOW)
    assert not has_forbidden(held[0].reason)


# ── Oracle config loader ─────────────────────────────────────────────────────


def test_committed_yaml_matches_builtin_oracle() -> None:
    from swarm_os.shadow_oracle import DEFAULT_BASELINE_PATH, _builtin_oracle_config

    assert DEFAULT_BASELINE_PATH.is_file()
    assert load_oracle_config() == _builtin_oracle_config()


def test_oracle_loader_falls_back_when_file_absent(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from swarm_os.shadow_oracle import _builtin_oracle_config

    missing = tmp_path / "nope.yaml"
    assert load_oracle_config(config_path=missing) == _builtin_oracle_config()


def test_oracle_loader_round_trips_yaml(tmp_path) -> None:  # type: ignore[no-untyped-def]
    raw = {
        "default": {"verify_band": "elevated", "dismiss_below": 0.3},
        "profiles": {"x": {"verify_band": "low-confidence", "dismiss_below": 0.1}},
        "kind_to_profile": {"HEAT_SPOT": "x"},
    }
    path = tmp_path / "autonomy_baseline.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_oracle_config(config_path=path)
    assert config.profile_for(AnomalyKind.HEAT_SPOT).verify_band is ConfidenceBand.LOW_CONFIDENCE
    assert config.profile_name_for(AnomalyKind.HEAT_SPOT) == "x"
    assert config.profile_name_for(AnomalyKind.SMOKE) == "default"


def test_oracle_dismiss_floor_cannot_swallow_verify_band() -> None:
    # dismiss_below above the elevated band floor (0.60) would auto-dismiss
    # anomalies the same profile verifies — rejected.
    with pytest.raises(ValidationError):
        OracleProfile(verify_band=ConfidenceBand.ELEVATED, dismiss_below=0.70)
    # The low-confidence (search) regime is the deliberate exception.
    OracleProfile(verify_band=ConfidenceBand.LOW_CONFIDENCE, dismiss_below=0.50)


def test_oracle_routing_to_undefined_profile_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OracleConfig(
            profiles={"a": OracleProfile()},
            kind_to_profile={AnomalyKind.SMOKE: "ghost"},
        )


def test_oracle_unknown_yaml_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        OracleProfile.model_validate({"verify_band": "elevated", "typo": 1})


# ── Shadow harness mechanics ─────────────────────────────────────────────────


def test_shadow_step_pairs_candidate_and_baseline_by_anomaly() -> None:
    state = _state(
        _anomaly(aid="hot", kind=AnomalyKind.FIRE, confidence=0.88),
        _anomaly(aid="dead", kind=AnomalyKind.SMOKE, confidence=0.40),
    )
    entries = shadow_step(
        state, NOW, candidate=engine_decider(), baseline=oracle_decider()
    )
    by_id = {e.anomaly_id: e for e in entries}
    assert set(by_id) == {"hot", "dead"}
    # FIRE 0.88: engine R1 VERIFY, oracle elevated/verified VERIFY -> agree.
    assert by_id["hot"].candidate is AutonomyVerdict.VERIFY
    assert by_id["hot"].baseline is AutonomyVerdict.VERIFY
    assert by_id["hot"].agreed
    # 0.40 SMOKE: engine dead band WAIT, oracle dead band WAIT -> agree.
    assert by_id["dead"].agreed


def test_shadow_step_flags_unevaluated_anomaly_as_divergence() -> None:
    """A decider that omits an anomaly diverges (paired against WAIT)."""

    def silent(state: SwarmState, now: datetime) -> list[AnomalyDisposition]:
        return []

    state = _state(_anomaly(aid="x", kind=AnomalyKind.FIRE, confidence=0.88))
    entries = shadow_step(state, NOW, candidate=silent, baseline=oracle_decider())
    assert len(entries) == 1
    assert entries[0].candidate is AutonomyVerdict.WAIT  # silent -> WAIT placeholder
    assert entries[0].baseline is AutonomyVerdict.VERIFY
    assert not entries[0].agreed
    assert entries[0].transition == "wait→verify"


def test_shadow_entry_transition_label() -> None:
    entry = ShadowEntry(
        anomaly_id="a",
        profile="wildfire",
        candidate=AutonomyVerdict.VERIFY,
        baseline=AutonomyVerdict.WAIT,
        candidate_reason="c",
        baseline_reason="b",
    )
    assert not entry.agreed
    assert entry.transition == "verify→wait"


# ── Divergence report + the gate has teeth ───────────────────────────────────


def _entries(diverged: int, total: int, *, profile: str = "wildfire") -> list[ShadowEntry]:
    out: list[ShadowEntry] = []
    for i in range(total):
        divergent = i < diverged
        out.append(
            ShadowEntry(
                anomaly_id=f"a-{i}",
                profile=profile,
                candidate=AutonomyVerdict.VERIFY,
                baseline=AutonomyVerdict.WAIT if divergent else AutonomyVerdict.VERIFY,
                candidate_reason="c",
                baseline_reason="b",
            )
        )
    return out


def test_divergence_report_below_gate_passes() -> None:
    log = ShadowDecisionLog()
    log.extend(_entries(4, 100))  # 4% < 5%
    report = log.report()
    assert report.total == 100
    assert report.diverged == 4
    assert report.divergence_rate == pytest.approx(0.04)
    assert report.within_gate


def test_divergence_report_at_or_above_gate_fails() -> None:
    # The plan reads "< 5%", so exactly 5% must FAIL.
    at_gate = ShadowDecisionLog()
    at_gate.extend(_entries(5, 100))
    assert at_gate.report().divergence_rate == pytest.approx(0.05)
    assert not at_gate.report().within_gate

    above = ShadowDecisionLog()
    above.extend(_entries(6, 100))
    assert not above.report().within_gate


def test_divergence_report_breaks_down_by_profile_and_transition() -> None:
    log = ShadowDecisionLog()
    log.extend(_entries(2, 10, profile="wildfire"))
    log.extend(_entries(0, 10, profile="search"))
    report = log.report()
    assert report.by_profile["wildfire"] == {"total": 10, "diverged": 2}
    assert report.by_profile["search"] == {"total": 10, "diverged": 0}
    assert report.by_transition == {"verify→wait": 2}
    summary = report.summary()
    assert summary["by_profile"]["wildfire"]["divergence_rate"] == pytest.approx(0.2)


def test_empty_log_is_within_gate() -> None:
    report = ShadowDecisionLog().report()
    assert report.total == 0
    assert report.divergence_rate == 0.0
    assert report.within_gate


def test_gate_constant_is_five_percent() -> None:
    assert GATE_DIVERGENCE == 0.05
    assert DivergenceReport(total=0, diverged=0, by_profile={}, by_transition={}).gate == 0.05


# ── The real gate: engine matches the oracle on the 3 scenarios ──────────────


def test_engine_matches_oracle_on_real_scenarios_deterministic() -> None:
    """Readiness rule 6 — exercise the real decider + real configs + real
    scenario YAMLs end to end. Deterministic (no jitter) divergence is 0%."""

    from scripts.shadow_divergence import run_shadow_bench

    payload = run_shadow_bench(runs=3, jitter_sigma=0.0, seed=0)
    overall = payload["overall"]
    assert overall["total"] > 0
    assert overall["divergence_rate"] == 0.0
    assert overall["within_gate"] is True
    # All three autonomy scenarios are covered.
    assert set(payload["scenarios"]) == {
        "wildfire_owner_land",
        "intrusion_owner_land",
        "search_owner_land",
    }


def test_engine_oracle_agree_per_scenario_decision_point() -> None:
    """The canonical scripted anomaly of each scenario: engine verdict ==
    oracle verdict at both the PENDING and (if verified) VERIFIED point."""

    engine = engine_decider()
    oracle = oracle_decider()
    cases = [
        (AnomalyKind.SMOKE, 0.62),
        (AnomalyKind.FIRE, 0.88),
        (AnomalyKind.INTRUSION, 0.71),
        (AnomalyKind.HEAT_SPOT, 0.55),
    ]
    for kind, conf in cases:
        for anomaly_state in (AnomalyState.PENDING, AnomalyState.VERIFIED):
            state = _state(_anomaly(kind=kind, confidence=conf, state=anomaly_state))
            [entry] = shadow_step(state, NOW, candidate=engine, baseline=oracle)
            assert entry.agreed, (
                f"{kind.value}@{conf} {anomaly_state.value}: "
                f"engine={entry.candidate.value} oracle={entry.baseline.value}"
            )


def test_engine_decider_matches_decide_all() -> None:
    """The Decider adapter is a thin wrapper over the production function."""

    state = _state(_anomaly(kind=AnomalyKind.FIRE, confidence=0.88))
    via_adapter = [(d.anomaly_id, d.verdict) for d in engine_decider()(state, NOW)]
    via_direct = [(d.anomaly_id, d.verdict) for d in decide_all(state, NOW)]
    assert via_adapter == via_direct
