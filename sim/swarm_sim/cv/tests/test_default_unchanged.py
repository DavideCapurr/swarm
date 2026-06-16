"""Phase 7.D — default-off contract.

These tests guarantee that NOTHING in the default `make test` path
changes when the `cv` extra isn't installed. They are NOT marked
`cv_baseline` — they run on every push and would fail closed if a 7.D
regression silently inverted the opt-in.

Specifically:

1. The committed YAML scenarios declare `perception.cv_enabled` per the
   7.D/7.G intent (intrusion + search: true; wildfire: false — flipped in
   7.G for the M1 demo). `cv_enabled` is *only* a build_world() branch —
   without the `[cv]` extra the import inside `build_world()` raises and
   the loader sees no side effect on parse.
2. A YAML without `cv_enabled` keeps the field default `False` —
   guarantees existing scenario YAMLs (Phase 7.A) keep instantiating a
   `MockPerception` byte-identical to the pre-7.D run.
3. The Phase 7.A determinism contract holds across the new field:
   loading the same YAML twice still produces identical ignitions /
   territory / drones.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sim.swarm_sim.perception import MockPerception
from sim.swarm_sim.scenario import PerceptionCfg, load_scenario

SCENARIO_DIR = Path(__file__).resolve().parents[3] / "scenarios"
SCENARIO_NAMES = ["wildfire_owner_land", "intrusion_owner_land", "search_owner_land"]


def _scenario_path(name: str) -> Path:
    return SCENARIO_DIR / f"{name}.yaml"


# CV live (three-month plan) freezes the per-scenario contract: intrusion +
# search run real YOLOv8 `person` detection (cv_enabled: true); wildfire stays
# cv_enabled: false ON PURPOSE — fire/smoke-CV is deferred to drone-day (COCO
# has no fire class, the fine-tuned weight is a manifest placeholder), so its
# scripted 0.62/0.88 keep driving the deterministic R1→R2 path + the 0%
# shadow-divergence gate. Real CV is exercised by `make test-cv` / `make
# cv-live` under the [cv] extra. The contract is per-scenario, not "all on".
CV_BASELINE_EXPECTED = {
    "wildfire_owner_land": False,
    "intrusion_owner_land": True,
    "search_owner_land": True,
}


@pytest.mark.parametrize("name, expected", list(CV_BASELINE_EXPECTED.items()))
def test_scenario_cv_baseline_matches_committed(name: str, expected: bool) -> None:
    """Each owner-land scenario declares the cv_enabled value 7.D/7.G intends."""
    scenario = load_scenario(_scenario_path(name))
    assert scenario.perception.cv_enabled is expected


def test_legacy_yaml_without_cv_enabled_keeps_mock(tmp_path: Path) -> None:
    """Backwards-compatible default — Phase 7.A YAMLs keep MockPerception."""
    yaml_text = (
        "id: legacy\nname: legacy\ndescription: legacy\ntick_hz: 10\n"
        "anchor: { lat: 44.7, lon: 8.03 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies: []\n"
    )
    p = tmp_path / "legacy.yaml"
    p.write_text(yaml_text)
    scenario = load_scenario(p)
    assert scenario.perception.cv_enabled is False
    world = scenario.build_world()
    assert isinstance(world.perception, MockPerception)


def test_perception_cfg_strict_rejects_unknown_field() -> None:
    """A YAML that mistypes `cv_enabled` (e.g. `cv_enable`) must fail validation."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PerceptionCfg.model_validate({"territory_radius_m": 10.0, "cv_enable": True})


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_loader_determinism_preserved(name: str) -> None:
    """Loading the YAML twice still produces the same scripted ignitions.

    The build_world() branch on cv_enabled does not change the YAML →
    Scenario projection — only what `Scenario.build_world()` returns.
    """
    a = load_scenario(_scenario_path(name))
    b = load_scenario(_scenario_path(name))
    assert a.id == b.id
    assert a.fleet == b.fleet
    assert a.anomalies == b.anomalies
    # Determinism only — the value itself is asserted per-scenario in
    # test_scenario_cv_baseline_matches_committed.
    assert a.perception.cv_enabled == b.perception.cv_enabled


def test_existing_7a_scenarios_count_matches() -> None:
    """Each committed YAML still scripts at least one anomaly (Phase 7.A guarantee)."""
    for name in SCENARIO_NAMES:
        s = load_scenario(_scenario_path(name))
        assert s.anomalies, name
