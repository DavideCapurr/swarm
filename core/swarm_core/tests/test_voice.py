"""Voice audit tests.

These pin the rule: no forbidden token may appear in any copy returned by
`describe_*` helpers, regardless of the input's confidence/kind/state.
"""

from __future__ import annotations

import itertools

import pytest

from swarm_core import voice
from swarm_core.messages import (
    AnomalyKind,
    AnomalyState,
    AnomalyView,
    ConfidenceBand,
    Geo,
    OperatingMode,
    RiskBand,
    Sector,
    SectorState,
)


def _g() -> Geo:
    return Geo(lat=44.7, lon=8.0)


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [
        (0.0, ConfidenceBand.LOW_CONFIDENCE),
        (0.59, ConfidenceBand.LOW_CONFIDENCE),
        (0.60, ConfidenceBand.ELEVATED),
        (0.84, ConfidenceBand.ELEVATED),
        (0.85, ConfidenceBand.VERIFIED),
        (1.0, ConfidenceBand.VERIFIED),
    ],
)
def test_band_boundaries(confidence: float, expected: ConfidenceBand) -> None:
    assert voice.band(confidence) == expected


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0])
def test_band_rejects_out_of_range(bad: float) -> None:
    with pytest.raises(ValueError):
        voice.band(bad)


def test_describe_anomaly_includes_confidence_pct() -> None:
    a = AnomalyView(
        id="a-1",
        kind=AnomalyKind.SMOKE,
        geo=_g(),
        sector_id="north-a",
        confidence=0.42,
        band=ConfidenceBand.LOW_CONFIDENCE,
        state=AnomalyState.PENDING,
    )
    s = voice.describe_anomaly(a)
    assert "low-confidence" in s
    assert "042%" in s
    assert "north-a" in s


def test_voice_audit_across_full_cartesian() -> None:
    """No copy may contain a FORBIDDEN_WORDS token, across (band x kind x state)."""
    bands = list(ConfidenceBand)
    kinds = list(AnomalyKind)
    states = list(AnomalyState)
    for band, kind, state in itertools.product(bands, kinds, states):
        a = AnomalyView(
            id="x",
            kind=kind,
            geo=_g(),
            sector_id="s",
            confidence=0.5 if band == ConfidenceBand.LOW_CONFIDENCE else (0.7 if band == ConfidenceBand.ELEVATED else 0.95),
            band=band,
            state=state,
        )
        copy = voice.describe_anomaly(a)
        assert voice.has_forbidden(copy) is None, f"forbidden in: {copy!r}"


def test_describe_sector_per_state() -> None:
    poly = [Geo(lat=0, lon=0), Geo(lat=0, lon=1), Geo(lat=1, lon=1)]
    for state in SectorState:
        s = Sector(
            id="s1",
            label="north-a",
            polygon=poly,
            centroid=Geo(lat=0.5, lon=0.5),
            state=state,
            confidence=0.83,
            risk_band=RiskBand.ELEVATED,
        )
        copy = voice.describe_sector(s)
        assert voice.has_forbidden(copy) is None, f"forbidden in: {copy!r}"
        assert "north-a" in copy


def test_describe_mode_covers_all_modes() -> None:
    for mode in OperatingMode:
        copy = voice.describe_mode(mode)
        assert copy  # non-empty
        assert voice.has_forbidden(copy) is None


def test_assert_no_forbidden_raises_on_intruder() -> None:
    voice.assert_no_forbidden("low-confidence anomaly · confidence 042%")
    with pytest.raises(ValueError):
        voice.assert_no_forbidden("Intruder detected near dock-1")
    with pytest.raises(ValueError):
        voice.assert_no_forbidden("red-alert · scramble all units")


def test_has_forbidden_returns_token() -> None:
    assert voice.has_forbidden("an alarm sounded") == "alarm"
    assert voice.has_forbidden("perfectly normal copy") is None


def test_forbidden_words_contains_pdf_required_tokens() -> None:
    """The Phase 0 contract pins these explicit tokens."""
    pdf_required = {"Intruder", "Manual", "fly drone", "alarm", "red-alert", "red state"}
    forbidden = set(voice.FORBIDDEN_WORDS)
    missing = pdf_required - forbidden
    assert not missing, f"voice.FORBIDDEN_WORDS missing: {missing}"
