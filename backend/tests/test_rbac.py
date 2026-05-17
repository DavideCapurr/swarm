"""Phase 6.C — RBAC end-to-end matrix.

Walks the role hierarchy (viewer < operator < commander) against the
three protected route families (read, write, admin) and verifies the
expected 200/202/403 outcomes. Plus a couple of focused checks for the
MFA enforcement on commander-only routes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from swarm_core.messages import AgentState, Geo, UnitState

from backend.app.api.actions import router as actions_router
from backend.app.api.admin import router as admin_router
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.auth import OperatorRole, TokenType
from backend.app.auth.deps import Principal
from swarm_os import SWARM_STATE


@pytest.fixture()
def client(site_yaml_for_rbac: object) -> TestClient:
    SWARM_STATE.events.clear()
    SWARM_STATE.commands.clear()
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.units.clear()
    # Plant a unit so the snapshot endpoints have shape.
    SWARM_STATE.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=99.0,
        geo=Geo(lat=44.7, lon=8.03),
        dock_id="dock-langhe-01",
    )
    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.include_router(actions_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    return TestClient(app)


@pytest.fixture()
def site_yaml_for_rbac(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> object:
    site_dir = tmp_path / "sites"
    site_dir.mkdir()
    (site_dir / "vineyard-01.yaml").write_text(
        """
site_id: vineyard-01
name: "Vineyard"
center: {lat: 44.7, lon: 8.03, alt_m: 0.0}
geofence:
  polygon:
    - {lat: 44.69, lon: 8.02}
    - {lat: 44.69, lon: 8.04}
    - {lat: 44.71, lon: 8.04}
    - {lat: 44.71, lon: 8.02}
  max_alt_m: 120.0
weather_provider:
  kind: stub
  refresh_interval_s: 300
docks:
  - dock_id: dock-langhe-01
    primary: true
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("swarm_os.sites.DEFAULT_CONFIG_DIR", site_dir)
    return site_dir


# ── Read route (viewer floor) ──────────────────────────────────────────────────


def test_read_route_viewer_200(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    assert client.get("/units", headers=viewer_headers).status_code == 200


def test_read_route_operator_200(
    client: TestClient, operator_headers: dict[str, str]
) -> None:
    assert client.get("/units", headers=operator_headers).status_code == 200


def test_read_route_commander_200(
    client: TestClient, commander_headers: dict[str, str]
) -> None:
    assert client.get("/units", headers=commander_headers).status_code == 200


def test_read_route_anonymous_401(client: TestClient) -> None:
    assert client.get("/units").status_code == 401


# ── Write route (operator floor) ───────────────────────────────────────────────


def test_write_route_viewer_403(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    r = client.post(
        "/actions/hold-patrol", json={"target": "global"}, headers=viewer_headers
    )
    assert r.status_code == 403


def test_write_route_operator_202(
    client: TestClient, operator_headers: dict[str, str]
) -> None:
    r = client.post(
        "/actions/hold-patrol", json={"target": "global"}, headers=operator_headers
    )
    assert r.status_code in (202, 422)


def test_write_route_commander_202(
    client: TestClient, commander_headers: dict[str, str]
) -> None:
    r = client.post(
        "/actions/hold-patrol",
        json={"target": "global"},
        headers=commander_headers,
    )
    assert r.status_code in (202, 422)


def test_write_route_anonymous_401(client: TestClient) -> None:
    r = client.post("/actions/hold-patrol", json={"target": "global"})
    assert r.status_code == 401


# ── Admin route (commander floor with MFA) ─────────────────────────────────────


def test_admin_route_viewer_403(
    client: TestClient, viewer_headers: dict[str, str]
) -> None:
    r = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers=viewer_headers,
    )
    assert r.status_code == 403


def test_admin_route_operator_403(
    client: TestClient, operator_headers: dict[str, str]
) -> None:
    r = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers=operator_headers,
    )
    assert r.status_code == 403


def test_admin_route_commander_without_mfa_403(
    client: TestClient, commander_headers_no_mfa: dict[str, str]
) -> None:
    r = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers=commander_headers_no_mfa,
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "mfa_required"


def test_admin_route_commander_with_mfa_200(
    client: TestClient, commander_headers: dict[str, str]
) -> None:
    r = client.post(
        "/admin/reload-site-config",
        json={"site_id": "vineyard-01"},
        headers=commander_headers,
    )
    assert r.status_code == 200


# ── Token integrity / revocation ───────────────────────────────────────────────


def test_expired_access_token_returns_401(
    client: TestClient, auth_env: dict[str, Any]
) -> None:
    import time

    service = auth_env["service"]
    token, _ = service.issue(
        operator_id=auth_env["operator_id"],
        role=OperatorRole.OPERATOR,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
        now=int(time.time()) - 3600,
    )
    r = client.get(
        "/units", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "token_expired"


def test_token_with_unknown_operator_rejected(
    client: TestClient, token_factory: Callable[..., str]
) -> None:
    """A token whose `sub` isn't in the store is rejected — even if the
    signature is valid. Defends against stale tokens after a user is
    deleted from the store mid-session."""

    token = token_factory(OperatorRole.OPERATOR, operator_id="op-unknown-99")
    r = client.get("/units", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "unknown_operator"


def test_token_role_mismatch_rejected(
    client: TestClient, token_factory: Callable[..., str]
) -> None:
    """If the store demotes an operator, an outstanding token claiming
    a higher role is rejected on the next request."""

    # Mint a token claiming commander for the viewer principal.
    token = token_factory(
        OperatorRole.COMMANDER,
        operator_id="op-viewer01",
        mfa=True,
    )
    r = client.get("/units", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["detail"] == "role_mismatch"


def test_revoked_token_returns_401(
    client: TestClient,
    operator_headers: dict[str, str],
    auth_env: dict[str, Any],
) -> None:
    """Revoking the JTI of an in-flight access token blocks the next call."""

    from backend.app.auth import get_revocation_store

    # Decode the token to find its JTI.
    bearer = operator_headers["Authorization"]
    raw = bearer.removeprefix("Bearer ").strip()
    service = auth_env["service"]
    claims = service.decode(raw, expected_type=TokenType.ACCESS)
    get_revocation_store().revoke(claims.jti, expires_at=claims.expires_at)
    r = client.get("/units", headers=operator_headers)
    assert r.status_code == 401
    assert r.json()["detail"] == "token_revoked"


_ = Principal  # imported for type-doc only
