"""Phase 1 REST/action endpoints (auth-aware under Phase 6.C)."""

from __future__ import annotations

import warnings
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.messages import AgentState, Geo, UnitState

from backend.app.api.actions import router as actions_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.auth import OperatorRole
from swarm_os import SWARM_STATE


def _client() -> TestClient:
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.units.clear()
    SWARM_STATE.events.clear()
    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.include_router(actions_router)
    return TestClient(app)


def test_phase1_snapshot_endpoints(viewer_headers: dict[str, str]) -> None:
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

    assert (
        client.get("/session", headers=viewer_headers).json()["session"]["label"]
        == "session 014"
    )
    assert "score" in client.get("/awareness", headers=viewer_headers).json()["awareness"]
    assert len(client.get("/sectors", headers=viewer_headers).json()["sectors"]) == 9
    assert (
        client.get("/units", headers=viewer_headers).json()["units"][0]["agent_id"]
        == "sim-1"
    )
    assert (
        client.get("/docks", headers=viewer_headers).json()["docks"][0]["dock_id"]
        == "dock-langhe-01"
    )
    assert client.get("/missions", headers=viewer_headers).json()["missions"] == []


def test_health_endpoint_remains_public() -> None:
    """Liveness probes don't carry tokens — the orchestrator just needs a
    200 + JSON body. Auth-locked /health would break every probe."""

    client = _client()
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_session_endpoint_requires_auth() -> None:
    client = _client()
    r = client.get("/session")
    # The deps emit 401 missing_token; the structured-error handler from
    # main.py is not on this minimal app, so the raw FastAPI 401 is
    # acceptable here. We only assert it's not a 200.
    assert r.status_code == 401


def test_verify_action_accepts_operator_intent(
    operator_headers: dict[str, str],
) -> None:
    client = _client()
    response = client.post(
        "/actions/verify",
        headers=operator_headers,
        json={"target": "sector:north-a"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["command_id"]


def test_verify_action_rejects_viewer(
    viewer_headers: dict[str, str],
) -> None:
    """RBAC: viewer hits 403 on a write endpoint."""

    client = _client()
    response = client.post(
        "/actions/verify",
        headers=viewer_headers,
        json={"target": "sector:north-a"},
    )
    assert response.status_code == 403


def test_rejected_action_uses_current_starlette_422_constant(
    operator_headers: dict[str, str],
) -> None:
    client = _client()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        response = client.post(
            "/actions/verify",
            headers=operator_headers,
            json={"target": "sector:does-not-exist"},
        )
    assert response.status_code == 422
    assert "rejected_reason" in response.json()
    warning_messages = [str(item.message) for item in caught]
    assert not any("HTTP_422_UNPROCESSABLE_ENTITY" in msg for msg in warning_messages)


def test_action_rate_limit_31st_request(
    token_factory: Callable[..., str],
) -> None:
    client = _client()
    # Use a dedicated operator id so the limiter bucket is empty per test.
    token = token_factory(
        OperatorRole.OPERATOR,
        operator_id="op-ratelimit",
    )
    headers = {"Authorization": f"Bearer {token}"}
    # The store needs to know this operator exists. The auth_env fixture
    # only seeds three rows, so we register the rate-limit principal.
    from backend.app.auth import (
        Operator,
        get_operator_store,
        hash_password,
    )

    get_operator_store().upsert(
        Operator(
            operator_id="op-ratelimit",
            password_hash=hash_password("pw", iterations=1_000),
            role=OperatorRole.OPERATOR,
        )
    )
    for _ in range(30):
        assert (
            client.post(
                "/actions/verify", headers=headers, json={"target": "sector:north-a"}
            ).status_code
            == 202
        )
    response = client.post(
        "/actions/verify", headers=headers, json={"target": "sector:north-a"}
    )
    assert response.status_code == 429
