"""CV live — end-to-end contract (three-month plan, Track B).

The contract that closes CV live:

    sim/scenarios/{intrusion,search}_owner_land.yaml   (cv_enabled: true)
    → CVPerception fires through the same on_anomaly path
    → Anomaly.confidence is the REAL YOLOv8 `person` score on a committed
      CC0 fixture, not the scripted YAML number

and the honest counter-case:

    sim/scenarios/wildfire_owner_land.yaml             (cv_enabled: false)
    → MockPerception keeps the scripted confidence (fire/smoke-CV deferred
      to drone-day; COCO has no fire class)

Gated by `cv_baseline` + `importorskip("ultralytics")` so the default
`make test` (no `[cv]` extra) skips this file. Run via `make test-cv`.
The default-off contract is covered by `test_default_unchanged.py`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = pytest.mark.cv_baseline
pytest.importorskip("ultralytics")

from swarm_core.messages import Anomaly, AnomalySource  # noqa: E402

from sim.swarm_sim.cv.perception_cv import CVPerception  # noqa: E402
from sim.swarm_sim.perception import MockPerception  # noqa: E402
from sim.swarm_sim.scenario import load_scenario  # noqa: E402

SCENARIO_DIR = Path(__file__).resolve().parents[3] / "scenarios"

# Floor below which a "real" person score would mean the fixture or the
# model path regressed (the committed CC0 frames all score > 0.80; see
# fixtures/LICENSES.md). The scripted YAML values these replace were
# 0.71 (intrusion) and 0.55 (search).
MIN_REAL_SCORE = 0.25


@pytest.mark.parametrize("name", ["intrusion_owner_land", "search_owner_land"])
def test_cv_live_scenario_emits_real_person_score(name: str) -> None:
    scenario = load_scenario(SCENARIO_DIR / f"{name}.yaml")
    assert scenario.perception.cv_enabled is True
    world = scenario.build_world()
    assert isinstance(world.perception, CVPerception)

    captured: list[Anomaly] = []
    world.perception.on_anomaly = captured.append
    # Collapse the schedule so the run is immediate (no real-time sleep).
    for ev in world.perception.ignitions:
        ev.after_s = 0.0
    asyncio.run(world.perception.run())

    assert len(captured) == len(scenario.anomalies)
    for actual, scripted in zip(captured, scenario.anomalies, strict=True):
        assert actual.kind == scripted.kind
        expected_geo = scenario.resolve_geo(scripted.position)
        assert actual.geo.lat == pytest.approx(expected_geo.lat)
        assert actual.geo.lon == pytest.approx(expected_geo.lon)
        # The score is the real model output, not the scripted YAML number.
        assert actual.confidence >= MIN_REAL_SCORE
        assert actual.confidence != pytest.approx(scripted.confidence)
        assert actual.evidence is not None
        assert actual.evidence.source == AnomalySource.DRONE_CV
        assert actual.evidence.label == "person"
        assert actual.evidence.value == pytest.approx(actual.confidence)


def test_cv_live_is_deterministic_same_process() -> None:
    """Same scenario built twice → identical real score (8.B-bis precondition)."""
    runs = []
    for _ in range(2):
        scenario = load_scenario(SCENARIO_DIR / "intrusion_owner_land.yaml")
        perception = scenario.build_world().perception
        assert isinstance(perception, CVPerception)
        ev = perception.ignitions[0]
        ev.after_s = 0.0
        runs.append(perception.detect_and_emit(ev).confidence)
    assert runs[0] == runs[1]


def test_wildfire_stays_scripted_cv_deferred() -> None:
    """Wildfire is cv_enabled:false on purpose — fire/smoke-CV is drone-day."""
    scenario = load_scenario(SCENARIO_DIR / "wildfire_owner_land.yaml")
    assert scenario.perception.cv_enabled is False
    world = scenario.build_world()
    assert isinstance(world.perception, MockPerception)
    by_kind = {a.kind.value: a for a in scenario.anomalies}
    # The scripted numbers survive untouched (drive the deterministic R1→R2
    # path + the 0% shadow-divergence gate); no YOLO runs here.
    assert by_kind["SMOKE"].confidence == pytest.approx(0.62)
    assert by_kind["FIRE"].confidence == pytest.approx(0.88)
    assert by_kind["FIRE"].source == AnomalySource.THERMAL_SAT
