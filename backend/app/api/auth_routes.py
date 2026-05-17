"""Phase 6.C — operator auth endpoints (JWT + RBAC + MFA-for-commander).

Surfaces:

  POST /auth/login    body: {operator_id, password, totp_code?}
  POST /auth/refresh  body: {refresh_token}
  POST /auth/logout   header: Authorization: Bearer <access>
  GET  /auth/me       header: Authorization: Bearer <access>

Every transition (login success/failure, refresh, logout) lands as a
`system` Event in the audit log — see ``backend.app.auth.audit``.

The route layer also runs the same per-key rate limiter the action
endpoints use, so brute-forcing a password (or trying TOTP codes) hits
the same 30-req/min ceiling.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.app.auth.audit import emit_auth_event
from backend.app.auth.deps import (
    AUTH_HEADER,
    BEARER_PREFIX,
    AuthError,
    Principal,
    get_current_principal,
)
from backend.app.auth.jwt import (
    JWTConfigError,
    JWTError,
    TokenType,
    get_jwt_service,
)
from backend.app.auth.mfa import verify_totp_code
from backend.app.auth.passwords import InvalidPasswordHash, verify_password
from backend.app.auth.revocation import get_revocation_store
from backend.app.auth.store import (
    OperatorRole,
    OperatorStoreNotConfigured,
    get_operator_store,
)
from backend.app.security import RateLimiter, is_valid_operator_id
from swarm_os import COORDINATOR

logger = logging.getLogger("backend.auth.routes")

router = APIRouter(prefix="/auth")
_login_limiter = RateLimiter()


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    operator_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=512)
    totp_code: str | None = Field(default=None, max_length=12)


class RefreshBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    refresh_token: str = Field(min_length=1, max_length=4096)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expiry
    role: OperatorRole
    operator_id: str
    site_id: str
    mfa: bool


class MeResponse(BaseModel):
    operator_id: str
    role: OperatorRole
    site_id: str
    mfa: bool
    expires_at: int


def _client_key(request: Request, operator_id: str | None) -> str:
    host = request.client.host if request.client else "unknown"
    return f"login:{host}:{operator_id or 'anon'}"


async def _auth_failure(
    *,
    operator_id: str,
    reason: str,
    outcome: str = "login_failure",
    role: OperatorRole | None = None,
) -> AuthError:
    """Helper: emit the audit row, then build an HTTP error to raise.

    Auth failures map to 401 across the board so an attacker can't tell
    whether they got the operator id wrong or the password — the reason
    code is recorded server-side via the audit event, never echoed.
    """

    await emit_auth_event(
        operator_id=operator_id,
        outcome=outcome,  # type: ignore[arg-type]
        role=role,
        reason=reason,
    )
    return AuthError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(request: Request, body: LoginBody) -> TokenResponse:
    if not is_valid_operator_id(body.operator_id):
        # Don't even consult the store — but rate-limit so we can't be used
        # to fingerprint valid operator id shape via timing.
        await _login_limiter.allow(_client_key(request, None))
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "invalid_credentials")

    if not await _login_limiter.allow(_client_key(request, body.operator_id)):
        raise AuthError(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    try:
        store = get_operator_store()
    except OperatorStoreNotConfigured as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc

    operator = store.get(body.operator_id)
    if operator is None:
        raise await _auth_failure(operator_id=body.operator_id, reason="unknown_operator")
    if operator.disabled:
        raise await _auth_failure(
            operator_id=operator.operator_id,
            reason="operator_disabled",
            role=operator.role,
        )
    try:
        password_ok = verify_password(body.password, operator.password_hash)
    except InvalidPasswordHash:
        password_ok = False
    if not password_ok:
        raise await _auth_failure(
            operator_id=operator.operator_id,
            reason="bad_password",
            role=operator.role,
        )

    # MFA: only commanders are required to clear a TOTP challenge.
    # For viewer/operator the `mfa` claim stays False — the require_role
    # dependency only inspects it when the route demands MFA.
    mfa_ok = False
    if operator.role is OperatorRole.COMMANDER:
        if not operator.mfa_secret:
            raise await _auth_failure(
                operator_id=operator.operator_id,
                reason="missing_mfa_secret",
                role=operator.role,
            )
        mfa_ok = verify_totp_code(operator.mfa_secret, body.totp_code)
        if not mfa_ok:
            raise await _auth_failure(
                operator_id=operator.operator_id,
                reason="bad_totp",
                role=operator.role,
            )

    try:
        service = get_jwt_service()
    except JWTConfigError as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc

    site_id = COORDINATOR.state.session.site_id
    access_token, _access_claims = service.issue(
        operator_id=operator.operator_id,
        role=operator.role,
        site_id=site_id,
        mfa=mfa_ok,
        token_type=TokenType.ACCESS,
    )
    refresh_token, _ = service.issue(
        operator_id=operator.operator_id,
        role=operator.role,
        site_id=site_id,
        mfa=mfa_ok,
        token_type=TokenType.REFRESH,
    )

    await emit_auth_event(
        operator_id=operator.operator_id,
        outcome="login_success",
        role=operator.role,
        reason=None,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=service.access_ttl_s,
        role=operator.role,
        operator_id=operator.operator_id,
        site_id=site_id,
        mfa=mfa_ok,
    )


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(request: Request, body: RefreshBody) -> TokenResponse:
    try:
        service = get_jwt_service()
    except JWTConfigError as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc

    try:
        claims = service.decode(body.refresh_token, expected_type=TokenType.REFRESH)
    except JWTError as exc:
        # We don't have a confirmed operator id here, so log "anonymous".
        await emit_auth_event(
            operator_id="unknown",
            outcome="refresh_failure",
            reason=str(exc.args[0]),
        )
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "invalid_refresh") from exc

    if get_revocation_store().is_revoked(claims.jti):
        await emit_auth_event(
            operator_id=claims.operator_id,
            outcome="refresh_failure",
            role=claims.role,
            reason="revoked",
        )
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "token_revoked")

    if not await _login_limiter.allow(_client_key(request, claims.operator_id)):
        raise AuthError(status.HTTP_429_TOO_MANY_REQUESTS, "rate_limited")

    try:
        store = get_operator_store()
    except OperatorStoreNotConfigured as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc
    operator = store.get(claims.operator_id)
    if operator is None or operator.disabled:
        await emit_auth_event(
            operator_id=claims.operator_id,
            outcome="refresh_failure",
            role=claims.role,
            reason="operator_unavailable",
        )
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "invalid_refresh")
    if operator.role is not claims.role:
        await emit_auth_event(
            operator_id=claims.operator_id,
            outcome="refresh_failure",
            role=operator.role,
            reason="role_mismatch",
        )
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "invalid_refresh")

    # Rotate: revoke the spent refresh token so a leaked refresh can't be
    # used twice (defense in depth on top of a short refresh TTL).
    get_revocation_store().revoke(claims.jti, expires_at=claims.expires_at)

    site_id = COORDINATOR.state.session.site_id
    new_access, _ = service.issue(
        operator_id=operator.operator_id,
        role=operator.role,
        site_id=site_id,
        mfa=claims.mfa,
        token_type=TokenType.ACCESS,
    )
    new_refresh, _ = service.issue(
        operator_id=operator.operator_id,
        role=operator.role,
        site_id=site_id,
        mfa=claims.mfa,
        token_type=TokenType.REFRESH,
    )
    await emit_auth_event(
        operator_id=operator.operator_id,
        outcome="refresh_success",
        role=operator.role,
    )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=service.access_ttl_s,
        role=operator.role,
        operator_id=operator.operator_id,
        site_id=site_id,
        mfa=claims.mfa,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    principal: Annotated[Principal, Depends(get_current_principal)],
    request: Request,
) -> None:
    """Revoke the presented access token (and the matching refresh if
    supplied in the body) so neither can be used again before natural
    expiry."""

    revocation = get_revocation_store()
    revocation.revoke(principal.jti, expires_at=principal.expires_at)
    # Also revoke a refresh token if the client sends one along — common
    # for "log me out everywhere on this device" semantics.
    refresh_token = _optional_refresh_from(request)
    if refresh_token:
        try:
            service = get_jwt_service()
            claims = service.decode(refresh_token, expected_type=TokenType.REFRESH)
        except (JWTConfigError, JWTError):
            claims = None
        if claims is not None and claims.operator_id == principal.operator_id:
            revocation.revoke(claims.jti, expires_at=claims.expires_at)

    await emit_auth_event(
        operator_id=principal.operator_id,
        outcome="logout",
        role=principal.role,
    )


def _optional_refresh_from(request: Request) -> str | None:
    # We accept the refresh token either as a JSON body field or as a
    # second bearer header (rare). FastAPI 0.110's Request.json() raises
    # if the body is empty; guard accordingly.
    raw = request.headers.get("X-Refresh-Token")
    if raw and len(raw) <= 4096:
        return raw
    return None


@router.get("/me", response_model=MeResponse, status_code=status.HTTP_200_OK)
async def me(
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> MeResponse:
    return MeResponse(
        operator_id=principal.operator_id,
        role=principal.role,
        site_id=principal.site_id,
        mfa=principal.mfa,
        expires_at=principal.expires_at,
    )


# Re-export the header constants so the FastAPI router test fixtures can
# reuse them without importing the deps module directly.
__all__ = (
    "AUTH_HEADER",
    "BEARER_PREFIX",
    "LoginBody",
    "MeResponse",
    "RefreshBody",
    "TokenResponse",
    "router",
)


# Suppress unused-import warning — kept on purpose; some integration tests
# expect a known FastAPI exception type when route deps fail.
_ = HTTPException
