"""Phase 7.D — default-off contract.

These tests guarantee that NOTHING in the default `make test` path
changes when the `cv` extra isn't installed. They are NOT marked
`cv_baseline` — they run on every push and would fail closed if a 7.D
regression silently inverted the opt-in.

Specifically:

1. The committed YAML scenarios declare `perception.cv_enabled` per the
   7.D/7.G intent (intrusion + search: true; wildfire: false — flipped in
   7.G for the M1 demo). `cv_enabled` only decides which `Perception`
   `build_world()` returns — building the world never imports `torch`/
   `ultralytics` itself, so it stays cheap and succeeds without the `[cv]`
   extra even for a `cv_enabled: true` scenario (see
   `test_scenarios.test_build_world_smoke`). The runtime is only required
   once something actually drives `CVPerception.run()` — see point 4.
2. A YAML without `cv_enabled` keeps the field default `False` —
   guarantees existing scenario YAMLs (Phase 7.A) keep instantiating a
   `MockPerception` byte-identical to the pre-7.D run.
3. The Phase 7.A determinism contract holds across the new field:
   loading the same YAML twice still produces identical ignitions /
   territory / drones.
4. `CVPerception.run()` fails fast and loud with `CVRuntimeUnavailable` —
   before the first scripted `after_s` sleep — when `ultralytics`/`torch`
   aren't importable, instead of only discovering the gap deep inside the
   first `detect_and_emit()` call. Root-cause fix for a real incident: the
   sim runner schedules `run()` as a fire-and-forget asyncio task, so a
   deferred failure there used to die with no log line at all (see
   `runner._log_task_failure` for the matching task-supervision fix).
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from sim.swarm_sim.cv.detector import CVRuntimeUnavailable
from sim.swarm_sim.cv.perception_cv import CVPerception
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


def test_cv_perception_run_fails_fast_without_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CVPerception.run()` must fail loud, not hang silent, without the `cv` extra.

    Regression test for a real incident: with the `cv` extra not installed,
    running `intrusion_owner_land.yaml` produced zero anomalies with no
    error at all, because `CVRuntimeUnavailable` only surfaced ~15s in
    (the scripted `after_s`), deep inside a fire-and-forget asyncio task
    whose exception nothing ever retrieved.

    This drives the real end-to-end path — `load_scenario(...).build_world()`
    then `.perception.run()`, exactly as `runner._publish_anomalies` does —
    with the runtime-import seam forced to fail the way it does when
    `ultralytics`/`torch` genuinely aren't installed. It asserts both that
    the exception actually propagates out of `run()` (no longer silent) and
    that it does so before the scripted 15s sleep (no longer slow to
    surface).
    """

    def _raise() -> None:
        raise CVRuntimeUnavailable(
            "ultralytics/torch not installed — run `make setup-cv` "
            "(opt-in extra; default `make setup` deliberately skips it)"
        )

    monkeypatch.setattr("sim.swarm_sim.cv.detector._load_runtime", _raise)

    scenario = load_scenario(_scenario_path("intrusion_owner_land"))
    world = scenario.build_world()  # must still succeed without the cv extra
    assert isinstance(world.perception, CVPerception)
    assert world.perception.ignitions[0].after_s == pytest.approx(15.0)

    started = time.monotonic()
    with pytest.raises(CVRuntimeUnavailable, match="make setup-cv"):
        asyncio.run(world.perception.run())
    elapsed = time.monotonic() - started

    assert elapsed < 1.0, "run() must fail before the scripted after_s sleep, not after it"


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
