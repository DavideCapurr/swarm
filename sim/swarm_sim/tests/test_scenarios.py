"""Phase 7.A scenario loader tests.

Covers parse + validate of the three owner-land YAMLs, schema rejection of
malformed input, the smoke build_world() contract, and determinism — the
last is the contract Phase 8.B-bis modalità ombra (100+ shadow runs of the
same scenario) depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError
from swarm_core.messages import AnomalySource, SensorKind

from sim.swarm_sim.perception import MockPerception, build_evidence
from sim.swarm_sim.scenario import Scenario, load_scenario

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"
SCENARIO_NAMES = ["wildfire_owner_land", "intrusion_owner_land", "search_owner_land"]


def _scenario_path(name: str) -> Path:
    return SCENARIO_DIR / f"{name}.yaml"


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_loads(name: str) -> None:
    scenario = load_scenario(_scenario_path(name))
    assert isinstance(scenario, Scenario)
    assert scenario.id == name
    assert scenario.fleet.n_drones >= 1
    assert scenario.anomalies, "every 7.A scenario scripts at least one anomaly"


def test_scenario_rejects_unknown_field(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies: []\n"
        "extra_field: nope\n"
    )
    with pytest.raises(ValidationError):
        load_scenario(bad)


def test_scenario_rejects_bad_anomaly_kind(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies:\n"
        "  - after_s: 1\n"
        "    kind: NOT_A_REAL_KIND\n"
        "    position: { mode: offset_m, east: 0, north: 0 }\n"
        "    confidence: 0.5\n"
    )
    with pytest.raises(ValidationError):
        load_scenario(bad)


def test_scenario_rejects_negative_after_s(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies:\n"
        "  - after_s: -1\n"
        "    kind: SMOKE\n"
        "    position: { mode: offset_m, east: 0, north: 0 }\n"
        "    confidence: 0.5\n"
    )
    with pytest.raises(ValidationError):
        load_scenario(bad)


def test_scenario_rejects_confidence_above_one(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies:\n"
        "  - after_s: 1\n"
        "    kind: SMOKE\n"
        "    position: { mode: offset_m, east: 0, north: 0 }\n"
        "    confidence: 1.5\n"
    )
    with pytest.raises(ValidationError):
        load_scenario(bad)


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_build_world_smoke(name: str) -> None:
    scenario = load_scenario(_scenario_path(name))
    world = scenario.build_world()
    assert len(world.drones) == scenario.fleet.n_drones
    assert world.perception is not None
    assert len(world.perception.ignitions) == len(scenario.anomalies)
    for drone in world.drones:
        assert drone.is_docked
        assert drone.battery_pct == 100.0


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_opts_into_autonomy_baseline(name: str) -> None:
    """Phase 7.B — every owner-land scenario opts into the baseline."""

    scenario = load_scenario(_scenario_path(name))
    assert scenario.autonomy_baseline is True


def test_scenario_autonomy_baseline_defaults_to_false(tmp_path: Path) -> None:
    """Backwards-compatible default — legacy YAMLs without the flag stay off."""

    yaml_text = (
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies: []\n"
    )
    p = tmp_path / "legacy.yaml"
    p.write_text(yaml_text)
    scenario = load_scenario(p)
    assert scenario.autonomy_baseline is False


@pytest.mark.parametrize("name", SCENARIO_NAMES)
def test_scenario_is_deterministic(name: str) -> None:
    """Required by Phase 8.B-bis modalità ombra: same YAML → same World."""
    a = load_scenario(_scenario_path(name)).build_world()
    b = load_scenario(_scenario_path(name)).build_world()
    assert [d.agent_id for d in a.drones] == [d.agent_id for d in b.drones]
    assert [d.dock for d in a.drones] == [d.dock for d in b.drones]
    assert a.perception is not None and b.perception is not None
    assert a.perception.territory_center == b.perception.territory_center
    assert a.perception.territory_radius_m == b.perception.territory_radius_m
    a_ev = [(e.after_s, e.geo, e.kind, e.confidence) for e in a.perception.ignitions]
    b_ev = [(e.after_s, e.geo, e.kind, e.confidence) for e in b.perception.ignitions]
    assert a_ev == b_ev


def test_scenario_parses_source_and_signal() -> None:
    """Evidence layer: wildfire declares per-anomaly provenance + signal."""
    scenario = load_scenario(_scenario_path("wildfire_owner_land"))
    by_kind = {a.kind.value: a for a in scenario.anomalies}
    assert by_kind["SMOKE"].source == AnomalySource.DRONE_CV
    assert by_kind["SMOKE"].signal is None
    fire = by_kind["FIRE"]
    assert fire.source == AnomalySource.THERMAL_SAT
    assert fire.signal is not None
    assert fire.signal.metric == "temperature_c"
    assert fire.signal.value == 47.0
    assert fire.signal.baseline == 18.0
    assert fire.signal.unit == "°C"


def test_scenario_source_defaults_to_drone_cv(tmp_path: Path) -> None:
    """Legacy YAML without a `source` field stays drone_cv (backward-compat)."""
    yaml_text = (
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 0, lon: 0 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies:\n"
        "  - after_s: 1\n"
        "    kind: SMOKE\n"
        "    position: { mode: offset_m, east: 0, north: 0 }\n"
        "    confidence: 0.5\n"
    )
    p = tmp_path / "legacy.yaml"
    p.write_text(yaml_text)
    scenario = load_scenario(p)
    assert scenario.anomalies[0].source == AnomalySource.DRONE_CV
    assert scenario.anomalies[0].signal is None


def test_mock_perception_emits_evidence() -> None:
    """MockPerception attaches honest evidence (provenance + signal + headline)."""
    scenario = load_scenario(_scenario_path("wildfire_owner_land"))
    world = scenario.build_world()
    assert isinstance(world.perception, MockPerception)
    emitted = [world.perception.emit_for_event(ig) for ig in world.perception.ignitions]
    for a in emitted:
        assert a.evidence is not None
    by_source = {a.evidence.source: a for a in emitted if a.evidence is not None}

    thermal = by_source[AnomalySource.THERMAL_SAT]
    assert thermal.evidence is not None
    assert thermal.evidence.sensor == SensorKind.THERMAL
    assert thermal.evidence.metric == "temperature_c"
    assert thermal.evidence.value == 47.0
    assert thermal.evidence.baseline == 18.0
    assert thermal.evidence.simulated is True
    assert thermal.evidence.headline == "thermal · +29°C over baseline"

    cv = by_source[AnomalySource.DRONE_CV]
    assert cv.evidence is not None
    assert cv.evidence.sensor == SensorKind.RGB
    assert cv.evidence.metric == "object_score"
    assert cv.evidence.value == cv.confidence  # scripted confidence on the mock path


def test_build_evidence_cv_path_uses_real_label_and_score() -> None:
    """The CV path passes the model label + score through to object_score."""
    scenario = load_scenario(_scenario_path("intrusion_owner_land"))
    perception = scenario.build_world().perception
    assert perception is not None
    ig = perception.ignitions[0]
    ev = build_evidence(ig, label="person", score=0.91)
    assert ev.source == AnomalySource.DRONE_CV
    assert ev.sensor == SensorKind.RGB
    assert ev.label == "person"
    assert ev.value == 0.91
    assert ev.headline == "drone cv · person · 091%"


def test_resolve_geo_offset_m_matches_manual_calc() -> None:
    scenario = load_scenario(_scenario_path("wildfire_owner_land"))
    # First anomaly: east=40, north=25 from anchor 44.7000, 8.0300.
    geo = scenario.resolve_geo(scenario.anomalies[0].position)
    expected_lat = 44.7000 + 25.0 / 111_000.0
    expected_lon = 8.0300 + 40.0 / 111_000.0
    assert geo.lat == pytest.approx(expected_lat)
    assert geo.lon == pytest.approx(expected_lon)


def test_resolve_geo_absolute_mode(tmp_path: Path) -> None:
    yaml_text = (
        "id: x\nname: x\ndescription: x\ntick_hz: 10\n"
        "anchor: { lat: 44.7, lon: 8.03 }\n"
        "plot: { shape: rectangle, width_m: 10, height_m: 10 }\n"
        "fleet: { n_drones: 1 }\n"
        "perception: { territory_radius_m: 10 }\n"
        "anomalies:\n"
        "  - after_s: 1\n"
        "    kind: SMOKE\n"
        "    position: { mode: absolute, lat: 45.0, lon: 9.0 }\n"
        "    confidence: 0.5\n"
    )
    p = tmp_path / "abs.yaml"
    p.write_text(yaml_text)
    scenario = load_scenario(p)
    geo = scenario.resolve_geo(scenario.anomalies[0].position)
    assert geo.lat == 45.0
    assert geo.lon == 9.0


def test_load_scenario_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_scenario(tmp_path / "does-not-exist.yaml")
