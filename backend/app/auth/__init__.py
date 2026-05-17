"""Phase 6.C — operator authentication + RBAC.

Pure JWT (HS256) with the secret read from `SWARM_JWT_SECRET`. Roles
follow a strict hierarchy commander > operator > viewer; MFA via TOTP is
required for the `commander` role at login time (the access token then
carries an `mfa: true` claim so downstream endpoints can re-check).

The operator store is a YAML file on disk, loaded once at boot and
refreshable via the same hot-reload pattern as the site config. The
revocation list is in-process today; the Redis-backed implementation is
queued for 6.E together with the rest of the secure-bus rollout.

Every login / refresh / revocation appends a `system` Event to the audit
log so the Console timeline and the persisted DB both carry an immutable
trail.
"""

from __future__ import annotations

from backend.app.auth.deps import (
    AUTH_HEADER,
    AuthError,
    Principal,
    extract_bearer_token,
    get_current_principal,
    optional_principal,
    rank,
    require_role,
)
from backend.app.auth.jwt import (
    JWTConfigError,
    JWTError,
    JWTService,
    TokenClaims,
    TokenType,
    get_jwt_service,
    set_jwt_service,
)
from backend.app.auth.mfa import (
    MFAError,
    generate_totp_secret,
    provisioning_uri,
    verify_totp_code,
)
from backend.app.auth.passwords import (
    InvalidPasswordHash,
    hash_password,
    verify_password,
)
from backend.app.auth.revocation import (
    RevocationStore,
    get_revocation_store,
    set_revocation_store,
)
from backend.app.auth.store import (
    Operator,
    OperatorRole,
    OperatorStore,
    OperatorStoreError,
    OperatorStoreNotConfigured,
    get_operator_store,
    load_operator_store,
    set_operator_store,
)

__all__ = (
    "AUTH_HEADER",
    "AuthError",
    "InvalidPasswordHash",
    "JWTConfigError",
    "JWTError",
    "JWTService",
    "MFAError",
    "Operator",
    "OperatorRole",
    "OperatorStore",
    "OperatorStoreError",
    "OperatorStoreNotConfigured",
    "Principal",
    "RevocationStore",
    "TokenClaims",
    "TokenType",
    "extract_bearer_token",
    "generate_totp_secret",
    "get_current_principal",
    "get_jwt_service",
    "get_operator_store",
    "get_revocation_store",
    "hash_password",
    "load_operator_store",
    "optional_principal",
    "provisioning_uri",
    "rank",
    "require_role",
    "set_jwt_service",
    "set_operator_store",
    "set_revocation_store",
    "verify_password",
    "verify_totp_code",
)
