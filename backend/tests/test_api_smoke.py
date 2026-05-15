"""Backend smoke tests — exercises the REST routes with TestClient.

We do NOT start the lifespan (which would need Redis); we instead poke the
state directly and verify the endpoints reflect it.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    FleetState,
    Geo,
    Telemetry,
)

from backend.app.api.routes import router
from backend.app.state import STATE
from swarm_os import SWARM_STATE


@pytest.fixture
def client() -> TestClient:
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.units.clear()
    SWARM_STATE.events.clear()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_reports_state_sizes(client: TestClient) -> None:
    STATE.fleet.clear()
    STATE.anomalies.clear()
    STATE.last_telemetry.clear()

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["fleet_size"] == 0


def test_fleet_reflects_state(client: TestClient) -> None:
    STATE.fleet.clear()
    STATE.fleet["sim-1"] = FleetState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=99.0,
        geo=Geo(lat=44.7, lon=8.03),
    )
    r = client.get("/fleet")
    assert r.status_code == 200
    fleet = r.json()["fleet"]
    assert len(fleet) == 1
    assert fleet[0]["agent_id"] == "sim-1"


def test_anomalies_endpoint(client: TestClient) -> None:
    STATE.anomalies.clear()
    a = Anomaly(kind=AnomalyKind.SMOKE, geo=Geo(lat=44.7, lon=8.03), confidence=0.9)
    STATE.anomalies[a.id] = a
    r = client.get("/anomalies")
    assert r.status_code == 200
    body = r.json()
    assert body["anomalies"][0]["confidence"] == 0.9


def test_telemetry_latest_endpoint(client: TestClient) -> None:
    STATE.last_telemetry.clear()
    t = Telemetry(agent_id="sim-1", geo=Geo(lat=44.7, lon=8.03), battery_pct=88.0)
    STATE.last_telemetry["sim-1"] = t
    r = client.get("/telemetry/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["telemetry"]["sim-1"]["battery_pct"] == 88.0


def test_events_endpoint_limit(client: TestClient) -> None:
    STATE.events.clear()
    for i in range(10):
        STATE.add_event("anomaly", {"i": i})
    r = client.get("/events?limit=3")
    body = r.json()
    assert len(body["events"]) == 3
