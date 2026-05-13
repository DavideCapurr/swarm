from __future__ import annotations

from swarm_core.messages import Geo, SensorKind
from swarm_core.missions import (
    COVER,
    PATROL,
    RELAY,
    RTL_DOCK,
    VERIFY,
    MissionKind,
    mission_waypoints,
)


def test_verify_constructs_high_priority_mission_with_deadline() -> None:
    m = VERIFY(geo=Geo(lat=45.0, lon=10.0))
    assert m.kind == MissionKind.VERIFY.value
    assert m.priority >= 50  # VERIFY preempts ordinary PATROL by default
    assert m.deadline is not None
    assert m.params["sensors"] == [SensorKind.RGB.value, SensorKind.THERMAL.value]


def test_patrol_uses_provided_sensors_and_altitude() -> None:
    area = [Geo(lat=45.0, lon=10.0), Geo(lat=45.001, lon=10.001), Geo(lat=45.0, lon=10.002)]
    m = PATROL(area=area, sensors=[SensorKind.RGB], altitude_m=80.0, cadence_s=900)
    assert m.kind == MissionKind.PATROL.value
    assert m.params["altitude_m"] == 80.0
    assert m.params["cadence_s"] == 900
    assert m.params["sensors"] == ["RGB"]


def test_cover_carries_fleet_size_and_rotation() -> None:
    area = [Geo(lat=45.0, lon=10.0), Geo(lat=45.001, lon=10.001), Geo(lat=45.0, lon=10.002)]
    m = COVER(area=area, fleet_size=3, rotation=True)
    assert m.params["fleet_size"] == 3
    assert m.params["rotation"] is True


def test_relay_and_rtl_dock_are_valid() -> None:
    r = RELAY(geo=Geo(lat=45.0, lon=10.0))
    assert r.kind == MissionKind.RELAY.value
    rtl = RTL_DOCK()
    assert rtl.kind == MissionKind.RTL_DOCK.value


def test_mission_waypoints_extracts_geo_for_visualization() -> None:
    m = VERIFY(geo=Geo(lat=45.0, lon=10.0), hover_s=15.0)
    wps = mission_waypoints(m)
    assert len(wps) == 1
    assert wps[0].geo.lat == 45.0
    assert wps[0].hover_s == 15.0

    p = PATROL(area=[Geo(lat=45.0, lon=10.0), Geo(lat=45.1, lon=10.1)])
    assert len(mission_waypoints(p)) == 2

    assert mission_waypoints(RTL_DOCK()) == []
