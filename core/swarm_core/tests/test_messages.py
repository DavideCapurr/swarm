from __future__ import annotations

import json

import pytest

from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    Geo,
    MissionTask,
    SensorKind,
    Telemetry,
)


def test_geo_validates_bounds() -> None:
    Geo(lat=45.0, lon=10.0)
    with pytest.raises(ValueError):
        Geo(lat=91.0, lon=10.0)
    with pytest.raises(ValueError):
        Geo(lat=0.0, lon=-181.0)


def test_telemetry_is_frozen() -> None:
    from pydantic import ValidationError

    t = Telemetry(agent_id="d1", geo=Geo(lat=45.0, lon=10.0))
    with pytest.raises(ValidationError):
        t.battery_pct = 50  # type: ignore[misc]


def test_telemetry_roundtrip_json() -> None:
    t = Telemetry(agent_id="d1", geo=Geo(lat=45.0, lon=10.0, alt_m=50.0), battery_pct=88.0)
    encoded = t.model_dump_json()
    decoded = Telemetry.model_validate(json.loads(encoded))
    assert decoded == t


def test_anomaly_defaults() -> None:
    a = Anomaly(kind=AnomalyKind.SMOKE, geo=Geo(lat=45.0, lon=10.0))
    assert a.confidence == 0.0
    assert a.verified is False
    assert a.id  # auto-generated


def test_mission_task_id_unique() -> None:
    a = MissionTask(kind="VERIFY", params={"foo": 1})
    b = MissionTask(kind="VERIFY", params={"foo": 1})
    assert a.id != b.id


def test_agent_state_values() -> None:
    assert AgentState.DOCKED.value == "DOCKED"
    assert AgentState("RTL") is AgentState.RTL


def test_sensor_kind_enum() -> None:
    assert SensorKind.THERMAL.value == "THERMAL"
