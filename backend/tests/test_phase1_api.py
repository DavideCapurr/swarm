"""Phase 1 REST/action endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.messages import AgentState, Geo, UnitState

from backend.app.api.actions import router as actions_router
from backend.app.api.routes import router as api_router
from swarm_os import SWARM_STATE


def _client() -> TestClient:
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.units.clear()
    SWARM_STATE.events.clear()
    app = FastAPI()
    app.include_router(api_router)
    app.include_router(actions_router)
    return TestClient(app)


def test_phase1_snapshot_endpoints() -> None:
    client = _client()
    SWARM_STATE.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=99.0,
        geo=Geo(lat=44.7, lon=8.03),
        dock_id="dock-langhe-01",
    )

    assert client.get("/session").json()["session"]["label"] == "session 014"
    assert "score" in client.get("/awareness").json()["awareness"]
    assert len(client.get("/sectors").json()["sectors"]) == 9
    assert client.get("/units").json()["units"][0]["agent_id"] == "sim-1"
    assert client.get("/docks").json()["docks"][0]["dock_id"] == "dock-langhe-01"
    assert client.get("/missions").json()["missions"] == []


def test_verify_action_accepts_operator_intent() -> None:
    client = _client()
    response = client.post(
        "/actions/verify",
        headers={"X-Operator-Id": "op-davide"},
        json={"target": "sector:north-a"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["command_id"]


def test_action_requires_valid_operator_id() -> None:
    client = _client()
    response = client.post(
        "/actions/verify",
        headers={"X-Operator-Id": "OP-davide"},
        json={"target": "sector:north-a"},
    )
    assert response.status_code == 400


def test_action_rate_limit_31st_request() -> None:
    client = _client()
    headers = {"X-Operator-Id": "op-ratelimit"}
    for _ in range(30):
        assert client.post(
            "/actions/verify", headers=headers, json={"target": "sector:north-a"}
        ).status_code == 202
    response = client.post(
        "/actions/verify", headers=headers, json={"target": "sector:north-a"}
    )
    assert response.status_code == 429
