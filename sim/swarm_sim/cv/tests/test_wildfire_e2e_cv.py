"""Phase 7.D — wildfire scenario end-to-end via CV.

This is the contract test that closes 7.D:

    sim/scenarios/wildfire_owner_land.yaml
    + perception.cv_enabled: true
    → CVPerception fires through the same on_anomaly path
    → bus delivers Anomaly with model-derived confidence

The MockPerception baseline (`cv_enabled: false`) is exercised by
`test_default_unchanged.py`; that one is NOT marked `cv_baseline` and
runs on every push to confirm the opt-out path is byte-identical.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = pytest.mark.cv_baseline
pytest.importorskip("ultralytics")

from swarm_core.messages import Anomaly  # noqa: E402

from sim.swarm_sim.cv.perception_cv import CVPerception  # noqa: E402
from sim.swarm_sim.scenario import load_scenario  # noqa: E402

SCENARIO = Path(__file__).resolve().parents[3] / "scenarios" / "wildfire_owner_land.yaml"


def test_wildfire_cv_pipeline() -> None:
    scenario = load_scenario(SCENARIO)
    assert scenario.perception.cv_enabled is True
    world = scenario.build_world()
    assert isinstance(world.perception, CVPerception)
    # Replace the schedule with after_s=0 so the test runs in <1s.
    world.perception.ignitions = [
        ev.__class__(after_s=0.0, geo=ev.geo, kind=ev.kind, confidence=ev.confidence)
        for ev in world.perception.ignitions
    ]
    captured: list[Anomaly] = []
    world.perception.on_anomaly = lambda a: captured.append(a)
    asyncio.run(world.perception.run())
    assert len(captured) == len(scenario.anomalies)
    # Geo + kind come from the YAML; the confidence comes from the model.
    for actual, scripted in zip(captured, scenario.anomalies, strict=True):
        assert actual.kind == scripted.kind
        expected_geo = scenario.resolve_geo(scripted.position)
        assert actual.geo.lat == pytest.approx(expected_geo.lat)
        assert actual.geo.lon == pytest.approx(expected_geo.lon)
        assert 0.0 <= actual.confidence <= 1.0
