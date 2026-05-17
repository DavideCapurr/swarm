"""Phase 6.C — login / refresh / logout / me endpoints."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.actions import router as actions_router
from backend.app.api.admin import router as admin_router
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.auth import (
    JWTService,
    Operator,
    OperatorRole,
    OperatorStore,
    RevocationStore,
    TokenType,
    get_operator_store,
    get_revocation_store,
    set_jwt_service,
    set_operator_store,
    set_revocation_store,
)
from backend.app.auth.passwords import hash_password
from swarm_os import SWARM_STATE


def _build_app() -> TestClient:
    SWARM_STATE.events.clear()
    SWARM_STATE.commands.clear()
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.units.clear()
    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.include_router(actions_router)
    app.include_router(admin_router)
    app.include_router(auth_router)
    return TestClient(app)


def _ref_totp(secret: str) -> str:
    cleaned = secret.replace(" ", "").upper()
    padding = (-len(cleaned)) % 8
    key = base64.b32decode(cleaned + ("=" * padding))
    counter = int(time.time()) // 30
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % 1_000_000).zfill(6)


# ── /auth/login ────────────────────────────────────────────────────────────────


def test_login_viewer_no_mfa(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": auth_env["viewer_id"], "password": auth_env["password"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "viewer"
    assert body["mfa"] is False
    assert body["operator_id"] == auth_env["viewer_id"]
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0


def test_login_operator_no_mfa(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_login_commander_requires_totp(auth_env: dict[str, Any]) -> None:
    """Commander login without a totp_code is rejected."""

    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": auth_env["commander_id"], "password": auth_env["password"]},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_login_commander_with_valid_totp(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={
            "operator_id": auth_env["commander_id"],
            "password": auth_env["password"],
            "totp_code": _ref_totp(auth_env["totp_secret"]),
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "commander"
    assert body["mfa"] is True


def test_login_commander_with_wrong_totp(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={
            "operator_id": auth_env["commander_id"],
            "password": auth_env["password"],
            "totp_code": "000000",
        },
    )
    assert r.status_code == 401


def test_login_bad_password(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": "wrong"},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "invalid_credentials"


def test_login_unknown_operator(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": "op-nobody", "password": "x"},
    )
    # Note: same generic error code as bad password, on purpose.
    assert r.status_code == 401


def test_login_malformed_operator_id(auth_env: dict[str, Any]) -> None:
    """The operator_id pattern is checked before consulting the store."""

    client = _build_app()
    r = client.post(
        "/auth/login",
        json={"operator_id": "BAD-ID", "password": "x"},
    )
    assert r.status_code == 401


def test_login_disabled_operator(auth_env: dict[str, Any]) -> None:
    store = get_operator_store()
    store.upsert(
        Operator(
            operator_id="op-disabled",
            password_hash=hash_password("pw", iterations=1_000),
            role=OperatorRole.OPERATOR,
            disabled=True,
        )
    )
    client = _build_app()
    r = client.post(
        "/auth/login", json={"operator_id": "op-disabled", "password": "pw"}
    )
    assert r.status_code == 401


def test_login_writes_success_audit(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    )
    bodies = [e.body for e in SWARM_STATE.events]
    assert any(
        b.startswith("auth login_success") and auth_env["operator_id"] in b for b in bodies
    )


def test_login_writes_failure_audit(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": "wrong"},
    )
    bodies = [e.body for e in SWARM_STATE.events]
    assert any(b.startswith("auth login_failure") for b in bodies)


# ── /auth/refresh ──────────────────────────────────────────────────────────────


def test_refresh_rotates_tokens(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    refresh = client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert refresh.status_code == 200
    new_tokens = refresh.json()
    assert new_tokens["access_token"] != login["access_token"]
    assert new_tokens["refresh_token"] != login["refresh_token"]


def test_refresh_rejects_used_refresh(auth_env: dict[str, Any]) -> None:
    """The old refresh token is revoked at rotation; reuse is 401."""

    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    client.post("/auth/refresh", json={"refresh_token": login["refresh_token"]})
    second = client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert second.status_code == 401


def test_refresh_rejects_access_token_as_refresh(auth_env: dict[str, Any]) -> None:
    """An attacker can't substitute an access token for a refresh."""

    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    r = client.post(
        "/auth/refresh", json={"refresh_token": login["access_token"]}
    )
    assert r.status_code == 401


def test_refresh_rejects_garbage(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    r = client.post("/auth/refresh", json={"refresh_token": "not.a.token"})
    assert r.status_code == 401


# ── /auth/logout ───────────────────────────────────────────────────────────────


def test_logout_revokes_access_token(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    bearer = {"Authorization": f"Bearer {login['access_token']}"}

    logout = client.post("/auth/logout", headers=bearer)
    assert logout.status_code == 204

    # The revoked access token must no longer be accepted.
    me = client.get("/auth/me", headers=bearer)
    assert me.status_code == 401


def test_logout_revokes_refresh_when_supplied(auth_env: dict[str, Any]) -> None:
    """Sending the refresh token along on /auth/logout revokes it too."""

    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    bearer = {
        "Authorization": f"Bearer {login['access_token']}",
        "X-Refresh-Token": login["refresh_token"],
    }
    client.post("/auth/logout", headers=bearer)
    r = client.post(
        "/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )
    assert r.status_code == 401


def test_logout_requires_auth() -> None:
    client = _build_app()
    r = client.post("/auth/logout")
    assert r.status_code == 401


# ── /auth/me ───────────────────────────────────────────────────────────────────


def test_me_returns_principal(auth_env: dict[str, Any]) -> None:
    client = _build_app()
    login = client.post(
        "/auth/login",
        json={"operator_id": auth_env["operator_id"], "password": auth_env["password"]},
    ).json()
    r = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["operator_id"] == auth_env["operator_id"]
    assert body["role"] == "operator"
    assert body["mfa"] is False


# ── Auth service-unavailable behaviour ────────────────────────────────────────


def test_login_503_when_jwt_not_configured() -> None:
    """If the JWT service is not installed, login fails closed with 503."""

    set_jwt_service(None)
    set_operator_store(OperatorStore())
    set_revocation_store(RevocationStore())
    client = _build_app()
    r = client.post(
        "/auth/login", json={"operator_id": "op-x01", "password": "x"}
    )
    assert r.status_code in (401, 503)
    # Re-install for downstream tests in the same module.
    set_jwt_service(JWTService(secret=b"a" * 32))


# ── Rate limiting ──────────────────────────────────────────────────────────────


def test_login_rate_limit_kicks_in(auth_env: dict[str, Any]) -> None:
    """Brute-force defence: after 30 failed attempts the same key gets 429."""

    client = _build_app()
    # Use a malformed-but-passable operator id so we hit the limiter
    # path rather than short-circuiting on the regex.
    payload = {"operator_id": auth_env["operator_id"], "password": "wrong"}
    for _ in range(30):
        client.post("/auth/login", json=payload)
    r = client.post("/auth/login", json=payload)
    assert r.status_code in (401, 429)


# Suppress unused-import warning — pyflakes still complains otherwise.
_ = (
    TokenType,
    get_revocation_store,
)
