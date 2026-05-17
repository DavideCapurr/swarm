"""WebSocket auth — accept the bearer token from the upgrade handshake.

The browser ``WebSocket`` constructor doesn't let JS attach custom HTTP
headers, so we accept the access token either via:

  * ``?token=<jwt>`` query parameter (default — what the Console uses);
  * ``Sec-WebSocket-Protocol: bearer, <jwt>`` subprotocol header (advanced
    clients that don't want the token in URLs / access logs).

When the operator store + JWT service aren't both initialised the WS
endpoint refuses every upgrade — same fail-closed posture as the HTTP
auth dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

from starlette.websockets import WebSocket

from backend.app.auth.deps import Principal
from backend.app.auth.jwt import (
    JWTConfigError,
    JWTError,
    TokenType,
    get_jwt_service,
)
from backend.app.auth.revocation import get_revocation_store
from backend.app.auth.store import (
    OperatorStoreNotConfigured,
    get_operator_store,
)

WS_AUTH_QUERY_PARAM = "token"
WS_AUTH_SUBPROTOCOL = "bearer"
WS_CLOSE_POLICY = 1008  # Starlette: policy violation


@dataclass(frozen=True)
class WebSocketAuth:
    principal: Principal
    accepted_subprotocol: str | None


def _extract_ws_token(ws: WebSocket) -> tuple[str | None, str | None]:
    """Return ``(token, accepted_subprotocol)``.

    Query-string wins (the Console's default). If the client requests the
    ``bearer`` subprotocol we echo it back on accept so the connection
    completes with the negotiated protocol header.
    """

    qs_token = ws.query_params.get(WS_AUTH_QUERY_PARAM)
    if qs_token:
        return qs_token, None

    subprotos = ws.headers.get("sec-websocket-protocol")
    if not subprotos:
        return None, None
    parts = [p.strip() for p in subprotos.split(",") if p.strip()]
    if len(parts) < 2 or parts[0] != WS_AUTH_SUBPROTOCOL:
        return None, None
    return parts[1], WS_AUTH_SUBPROTOCOL


async def authenticate_websocket(ws: WebSocket) -> WebSocketAuth | None:
    """Validate the incoming WS upgrade. Returns ``None`` if rejected.

    The caller is expected to ``await ws.close(code=1008)`` on rejection;
    we don't close the socket here so the caller controls the lifecycle.
    """

    token, accepted = _extract_ws_token(ws)
    if not token:
        return None

    try:
        service = get_jwt_service()
    except JWTConfigError:
        return None

    try:
        claims = service.decode(token, expected_type=TokenType.ACCESS)
    except JWTError:
        return None

    if get_revocation_store().is_revoked(claims.jti):
        return None

    try:
        store = get_operator_store()
    except OperatorStoreNotConfigured:
        return None

    operator = store.get(claims.operator_id)
    if operator is None or operator.disabled:
        return None
    if operator.role is not claims.role:
        return None

    return WebSocketAuth(
        principal=Principal.from_claims(claims), accepted_subprotocol=accepted
    )


__all__ = (
    "WS_AUTH_QUERY_PARAM",
    "WS_AUTH_SUBPROTOCOL",
    "WS_CLOSE_POLICY",
    "WebSocketAuth",
    "authenticate_websocket",
)
