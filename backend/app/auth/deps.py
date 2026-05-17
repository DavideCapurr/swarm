"""FastAPI dependencies — extract the principal + enforce RBAC.

``Principal`` is the thin, immutable view of the caller that the rest of
the API touches. Endpoints declare a role floor via ``require_role``::

    @router.post("/admin/reload-site-config")
    async def reload(p: Principal = Depends(require_role("commander"))) -> ...:
        ...

The dependency does the heavy lifting:

  1. Extract the bearer token from ``Authorization: Bearer …``.
  2. Decode + validate via the installed ``JWTService``.
  3. Reject if the JTI is in the revocation list.
  4. Look up the operator in the store and refuse if disabled.
  5. Check the role rank against the required floor.
  6. For commander-only routes, re-check ``mfa=True`` on the claim.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Final

from fastapi import Depends, HTTPException, Request, status

from backend.app.auth.jwt import (
    JWTConfigError,
    JWTError,
    TokenClaims,
    TokenType,
    get_jwt_service,
)
from backend.app.auth.revocation import get_revocation_store
from backend.app.auth.store import (
    Operator,
    OperatorRole,
    OperatorStoreNotConfigured,
    get_operator_store,
    role_rank,
)

AUTH_HEADER: Final[str] = "Authorization"
BEARER_PREFIX: Final[str] = "Bearer "


class AuthError(HTTPException):
    """401/403 wrapper that always returns a stable ``error`` envelope."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(status_code=status_code, detail=code)


@dataclass(frozen=True)
class Principal:
    """The authenticated caller of an endpoint.

    Carries only what the API layer needs: operator id, role, MFA bit
    from the access token, and the bound site id (for IDOR checks once
    multi-site multiplexing lands)."""

    operator_id: str
    role: OperatorRole
    site_id: str
    mfa: bool
    jti: str
    expires_at: int

    @classmethod
    def from_claims(cls, claims: TokenClaims) -> Principal:
        return cls(
            operator_id=claims.operator_id,
            role=claims.role,
            site_id=claims.site_id,
            mfa=claims.mfa,
            jti=claims.jti,
            expires_at=claims.expires_at,
        )


def rank(role: OperatorRole) -> int:
    return role_rank(role)


# ── Bearer extraction ──────────────────────────────────────────────────────────


def extract_bearer_token(request: Request) -> str | None:
    """Pull the bearer token from the Authorization header.

    Returns ``None`` when no header is present or the scheme is not
    ``Bearer``. The caller decides whether absence is a 401 (mandatory
    auth) or simply means "no principal yet" (optional auth)."""

    header = request.headers.get(AUTH_HEADER)
    if not header:
        return None
    if not header.startswith(BEARER_PREFIX):
        return None
    token = header[len(BEARER_PREFIX) :].strip()
    return token or None


def extract_bearer_or_query(request: Request, *, query_param: str = "token") -> str | None:
    """Pull a token from the Authorization header or, failing that, from
    a query string parameter.

    The browser ``WebSocket`` constructor does not let JS attach custom
    headers; the query-param fallback exists *only* for the WS upgrade
    handshake. HTTP endpoints continue to require the Authorization
    header.
    """

    token = extract_bearer_token(request)
    if token:
        return token
    qv = request.query_params.get(query_param)
    if qv:
        return qv.strip() or None
    return None


# ── Core auth dependency ───────────────────────────────────────────────────────


async def get_current_principal(request: Request) -> Principal:
    """Decode + validate the access token, hand back an immutable ``Principal``.

    Every branch maps to a stable ``WWW-Authenticate``-style error code so
    the Console can render a precise reason (token expired vs revoked vs
    disabled) without inferring schemas from prose.
    """

    token = extract_bearer_token(request)
    if not token:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "missing_token")

    try:
        service = get_jwt_service()
    except JWTConfigError as exc:
        # Misconfigured deploy: fail closed so we never accept unsigned bytes.
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc

    try:
        claims = service.decode(token, expected_type=TokenType.ACCESS)
    except JWTError as exc:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, str(exc.args[0])) from exc

    if get_revocation_store().is_revoked(claims.jti):
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "token_revoked")

    try:
        store = get_operator_store()
    except OperatorStoreNotConfigured as exc:
        raise AuthError(status.HTTP_503_SERVICE_UNAVAILABLE, "auth_not_configured") from exc

    operator = store.get(claims.operator_id)
    if operator is None:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "unknown_operator")
    if operator.disabled:
        raise AuthError(status.HTTP_403_FORBIDDEN, "operator_disabled")
    # The token's recorded role and the store's current role must match.
    # If an operator is demoted server-side, all outstanding tokens for the
    # old role are invalidated at next request.
    if operator.role is not claims.role:
        raise AuthError(status.HTTP_401_UNAUTHORIZED, "role_mismatch")

    return Principal.from_claims(claims)


# ── Soft (optional) auth ───────────────────────────────────────────────────────


async def optional_principal(request: Request) -> Principal | None:
    """Like ``get_current_principal`` but returns ``None`` instead of 401.

    Used for endpoints that want to log the operator if present but accept
    anonymous health/info calls. Not used to gate any mutation."""

    if not extract_bearer_token(request):
        return None
    try:
        return await get_current_principal(request)
    except AuthError:
        return None


# ── RBAC dependency factory ────────────────────────────────────────────────────


def require_role(
    required: OperatorRole | str, *, require_mfa: bool | None = None
) -> Callable[..., Awaitable[Principal]]:
    """Return a FastAPI dependency that enforces a role floor.

    ``require_mfa=None`` (default) means "MFA is required iff the floor is
    commander". Pass ``require_mfa=True`` to demand MFA on a non-commander
    route, or ``require_mfa=False`` to opt out (rarely useful).
    """

    required_role = OperatorRole(required) if isinstance(required, str) else required
    needs_mfa = (
        require_mfa
        if require_mfa is not None
        else (required_role is OperatorRole.COMMANDER)
    )
    floor = role_rank(required_role)

    async def _dep(
        principal: Annotated[Principal, Depends(get_current_principal)],
    ) -> Principal:
        if role_rank(principal.role) < floor:
            raise AuthError(status.HTTP_403_FORBIDDEN, "insufficient_role")
        if needs_mfa and not principal.mfa:
            raise AuthError(status.HTTP_403_FORBIDDEN, "mfa_required")
        return principal

    _dep.__name__ = f"require_role_{required_role.value}"
    return _dep


# ── Convenience: typed deps for the common roles ───────────────────────────────

require_viewer = require_role(OperatorRole.VIEWER)
require_operator = require_role(OperatorRole.OPERATOR)
require_commander = require_role(OperatorRole.COMMANDER)


def operator_view(principal: Operator | None) -> dict[str, str | bool] | None:
    """Render a safe operator view — no password hash, no MFA secret."""

    if principal is None:
        return None
    return {
        "operator_id": principal.operator_id,
        "role": principal.role.value,
        "mfa_enabled": principal.mfa_secret is not None,
        "disabled": principal.disabled,
    }


__all__ = (
    "AUTH_HEADER",
    "BEARER_PREFIX",
    "AuthError",
    "Principal",
    "extract_bearer_or_query",
    "extract_bearer_token",
    "get_current_principal",
    "operator_view",
    "optional_principal",
    "rank",
    "require_commander",
    "require_operator",
    "require_role",
    "require_viewer",
)
