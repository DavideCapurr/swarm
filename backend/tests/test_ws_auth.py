"""Phase 6.C — WebSocket upgrade auth.

The Console WS connects over ``/ws/telemetry?token=…``. Without a valid
access token the connection is refused with a 1008 (policy violation)
close code. The same fail-closed posture covers a missing JWT service or
operator store at boot.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from backend.app.auth import OperatorRole
from backend.app.auth.ws_auth import (
    WS_AUTH_QUERY_PARAM,
    authenticate_websocket,
)


def _build_ws_app() -> FastAPI:
    from backend.app.auth.ws_auth import WS_CLOSE_POLICY
    from backend.app.hub import HUB
    from backend.app.security import check_websocket_origin

    app = FastAPI()

    @app.websocket("/ws/telemetry")
    async def ws(websocket: WebSocket) -> None:  # pragma: no cover (test plumbing)
        if not check_websocket_origin(websocket):
            await websocket.close(code=WS_CLOSE_POLICY)
            return
        auth = await authenticate_websocket(websocket)
        if auth is None:
            await websocket.close(code=WS_CLOSE_POLICY)
            return
        await HUB.connect(websocket, subprotocol=auth.accepted_subprotocol)
        try:
            while True:
                await websocket.receive_text()
        except Exception:
            pass
        finally:
            await HUB.disconnect(websocket)

    return app


def test_ws_accepts_valid_token(
    token_factory: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A valid access token in the query string opens the socket."""

    from fastapi.testclient import TestClient

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "http://testserver")
    app = _build_ws_app()
    client = TestClient(app)
    token = token_factory(OperatorRole.OPERATOR)
    with client.websocket_connect(
        f"/ws/telemetry?{WS_AUTH_QUERY_PARAM}={token}",
        headers={"origin": "http://testserver"},
    ) as ws:
        # Snapshot frames are sent on connect — we don't care about the
        # contents here, only that the connection opened.
        ws.close()


def test_ws_rejects_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "http://testserver")
    app = _build_ws_app()
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        "/ws/telemetry",
        headers={"origin": "http://testserver"},
    ):
        pass


def test_ws_rejects_invalid_token(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "http://testserver")
    app = _build_ws_app()
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        f"/ws/telemetry?{WS_AUTH_QUERY_PARAM}=garbage.not.jwt",
        headers={"origin": "http://testserver"},
    ):
        pass


def test_ws_rejects_revoked_token(
    token_factory: Callable[..., str],
    auth_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from backend.app.auth import TokenType, get_revocation_store

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "http://testserver")
    app = _build_ws_app()
    client = TestClient(app)
    token = token_factory(OperatorRole.OPERATOR)
    service = auth_env["service"]
    claims = service.decode(token, expected_type=TokenType.ACCESS)
    get_revocation_store().revoke(claims.jti, expires_at=claims.expires_at)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        f"/ws/telemetry?{WS_AUTH_QUERY_PARAM}={token}",
        headers={"origin": "http://testserver"},
    ):
        pass


def test_ws_accepts_subprotocol_bearer(
    token_factory: Callable[..., str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advanced clients can pass the token in the ``Sec-WebSocket-Protocol``
    subprotocol so the JWT never lands in a URL / access log."""

    from fastapi.testclient import TestClient

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "http://testserver")
    app = _build_ws_app()
    client = TestClient(app)
    token = token_factory(OperatorRole.OPERATOR)
    with client.websocket_connect(
        "/ws/telemetry",
        headers={
            "origin": "http://testserver",
            "sec-websocket-protocol": f"bearer, {token}",
        },
        subprotocols=["bearer", token],
    ) as ws:
        ws.close()


def test_main_ws_route_has_no_auth_disabled_bypass() -> None:
    """Regression guard: WS auth cannot be disabled by an env toggle."""

    import backend.app.main as main_mod

    assert "SWARM_AUTH_DISABLED" not in inspect.getsource(main_mod.ws_telemetry)


# Silence unused-import noise.
_ = asyncio
