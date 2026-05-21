"""Phase 7.D — CVPerception seam test.

Asserts that `CVPerception.run()` walks the same `on_anomaly` callback
path as `MockPerception.run()`: same shape of `Anomaly` (kind + geo
from the YAML, confidence from the model), same scheduling semantics,
same idempotency. Gated by the `cv_baseline` marker.
"""

from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.cv_baseline
pytest.importorskip("ultralytics")

from swarm_core.messages import Anomaly, AnomalyKind, Geo  # noqa: E402

from sim.swarm_sim.cv.perception_cv import CVPerception, NoFixtureAvailable  # noqa: E402
from sim.swarm_sim.perception import IgnitionEvent  # noqa: E402


def _ev(after_s: float, kind: AnomalyKind) -> IgnitionEvent:
    return IgnitionEvent(
        after_s=after_s,
        geo=Geo(lat=44.7000, lon=8.0300),
        kind=kind,
        confidence=0.0,  # ignored by CVPerception — model output wins
    )


def test_cv_perception_emits_via_callback() -> None:
    captured: list[Anomaly] = []
    perception = CVPerception(
        territory_center=Geo(lat=44.7, lon=8.03),
        territory_radius_m=100.0,
        ignitions=[_ev(0.0, AnomalyKind.SMOKE), _ev(0.0, AnomalyKind.INTRUSION)],
        on_anomaly=lambda a: captured.append(a),
        scenario_id="seam-test",
    )
    asyncio.run(perception.run())
    assert len(captured) == 2
    assert {a.kind for a in captured} == {AnomalyKind.SMOKE, AnomalyKind.INTRUSION}
    for a in captured:
        assert 0.0 <= a.confidence <= 1.0
        assert a.geo.lat == 44.7000
        assert a.geo.lon == 8.0300


def test_cv_perception_picks_fixture_deterministically() -> None:
    """Same scenario_id + after_s + kind → same fixture each call."""
    perception = CVPerception(
        territory_center=Geo(lat=44.7, lon=8.03),
        territory_radius_m=100.0,
        scenario_id="determinism",
    )
    ev = _ev(10.0, AnomalyKind.SMOKE)
    a = perception._pick_fixture(ev.kind, ev.after_s)
    b = perception._pick_fixture(ev.kind, ev.after_s)
    assert a == b


def test_cv_perception_no_fixtures_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sim.swarm_sim.cv.perception_cv.list_fixtures",
        lambda kind: [],
    )
    perception = CVPerception(
        territory_center=Geo(lat=44.7, lon=8.03),
        territory_radius_m=100.0,
        ignitions=[_ev(0.0, AnomalyKind.SMOKE)],
        scenario_id="no-fixtures",
    )
    with pytest.raises(NoFixtureAvailable):
        asyncio.run(perception.run())


def test_cv_perception_run_with_no_ignitions_is_noop() -> None:
    seen: list[Anomaly] = []
    perception = CVPerception(
        territory_center=Geo(lat=44.7, lon=8.03),
        territory_radius_m=100.0,
        on_anomaly=lambda a: seen.append(a),
        scenario_id="empty",
    )
    asyncio.run(perception.run())
    assert seen == []
