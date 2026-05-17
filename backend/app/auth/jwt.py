"""JWT issuance + verification (HS256).

A single ``JWTService`` is installed at boot; tests swap it for an
instance bound to a short-lived secret. Production reads the secret from
``SWARM_JWT_SECRET`` (env var, base64-or-raw, ≥ 32 bytes). When the env
var is missing in non-dev, ``JWTService.from_env()`` refuses to construct
the service and the FastAPI lifespan fails closed before accepting any
request.

Token claims::

    iss   "swarm-os"
    aud   "swarm-console"
    sub   <operator_id>
    role  "viewer" | "operator" | "commander"
    site  <site_id>
    mfa   bool (true iff MFA was satisfied at login)
    typ   "access" | "refresh"
    jti   16-hex-char unique id (used by the revocation list)
    iat   issue time
    exp   expiry

Access token: 15 min. Refresh token: 8 h. Both lifetimes are configurable
via env so deployments with stricter audit policies can shorten them.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import jwt

from backend.app.auth.store import OperatorRole

logger = logging.getLogger("backend.auth.jwt")

JWT_SECRET_ENV = "SWARM_JWT_SECRET"
JWT_ISSUER_DEFAULT = "swarm-os"
JWT_AUDIENCE_DEFAULT = "swarm-console"
JWT_ALGORITHM = "HS256"
JWT_LEEWAY_S = 30  # tolerate small clock skew across nodes

DEFAULT_ACCESS_TTL_S = 15 * 60  # 15 min — roadmap §6.C
DEFAULT_REFRESH_TTL_S = 8 * 60 * 60  # 8 h — roadmap §6.C

MIN_SECRET_BYTES = 32  # 256-bit HS256 requirement


class JWTError(ValueError):
    """Token rejected — malformed, expired, wrong sig, wrong aud, revoked."""


class JWTConfigError(RuntimeError):
    """JWT service refused to construct — usually a missing/weak secret."""


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class TokenClaims:
    """The subset of decoded claims the rest of the app reads.

    `mfa` is True iff the login that produced this token satisfied the
    MFA challenge. Endpoints that demand commander MFA re-check this on
    every call so a stolen token from a non-MFA flow can't be elevated.
    """

    operator_id: str
    role: OperatorRole
    site_id: str
    mfa: bool
    token_type: TokenType
    jti: str
    issued_at: int
    expires_at: int
    raw: dict[str, Any] = field(default_factory=dict)


def _load_secret_from_env() -> bytes:
    raw = os.getenv(JWT_SECRET_ENV)
    if not raw:
        raise JWTConfigError(
            f"{JWT_SECRET_ENV} is not set — refusing to issue JWTs. "
            "Generate ≥32 random bytes (e.g. `openssl rand -hex 32`) and mount "
            "it as a deploy secret."
        )
    if len(raw.encode("utf-8")) < MIN_SECRET_BYTES:
        raise JWTConfigError(
            f"{JWT_SECRET_ENV} too short — need ≥{MIN_SECRET_BYTES} bytes of "
            "entropy for HS256."
        )
    return raw.encode("utf-8")


@dataclass
class JWTService:
    """Issue + verify SwarmOS JWTs. One instance per backend process."""

    secret: bytes
    issuer: str = JWT_ISSUER_DEFAULT
    audience: str = JWT_AUDIENCE_DEFAULT
    access_ttl_s: int = DEFAULT_ACCESS_TTL_S
    refresh_ttl_s: int = DEFAULT_REFRESH_TTL_S
    algorithm: str = JWT_ALGORITHM

    def __post_init__(self) -> None:
        if len(self.secret) < MIN_SECRET_BYTES:
            raise JWTConfigError(
                f"JWT secret too short — need ≥{MIN_SECRET_BYTES} bytes."
            )
        if self.access_ttl_s <= 0 or self.refresh_ttl_s <= 0:
            raise JWTConfigError("token TTLs must be positive")
        if self.refresh_ttl_s < self.access_ttl_s:
            raise JWTConfigError("refresh TTL must be ≥ access TTL")

    # ── Construction ────────────────────────────────────────────────────────

    @classmethod
    def from_env(
        cls,
        *,
        access_ttl_s: int | None = None,
        refresh_ttl_s: int | None = None,
        issuer: str | None = None,
        audience: str | None = None,
    ) -> JWTService:
        secret = _load_secret_from_env()
        a_ttl = access_ttl_s or int(
            os.getenv("SWARM_JWT_ACCESS_TTL_S", DEFAULT_ACCESS_TTL_S)
        )
        r_ttl = refresh_ttl_s or int(
            os.getenv("SWARM_JWT_REFRESH_TTL_S", DEFAULT_REFRESH_TTL_S)
        )
        return cls(
            secret=secret,
            issuer=issuer or os.getenv("SWARM_JWT_ISSUER") or JWT_ISSUER_DEFAULT,
            audience=audience or os.getenv("SWARM_JWT_AUDIENCE") or JWT_AUDIENCE_DEFAULT,
            access_ttl_s=a_ttl,
            refresh_ttl_s=r_ttl,
        )

    # ── Issue ───────────────────────────────────────────────────────────────

    def issue(
        self,
        *,
        operator_id: str,
        role: OperatorRole,
        site_id: str,
        mfa: bool,
        token_type: TokenType,
        now: int | None = None,
        jti: str | None = None,
    ) -> tuple[str, TokenClaims]:
        """Return ``(encoded_token, decoded_claims)``."""

        ttl = (
            self.access_ttl_s
            if token_type is TokenType.ACCESS
            else self.refresh_ttl_s
        )
        issued_at = int(now if now is not None else time.time())
        expires_at = issued_at + ttl
        jti_v = jti or secrets.token_hex(16)
        payload = {
            "iss": self.issuer,
            "aud": self.audience,
            "sub": operator_id,
            "role": role.value,
            "site": site_id,
            "mfa": bool(mfa),
            "typ": token_type.value,
            "jti": jti_v,
            "iat": issued_at,
            "exp": expires_at,
        }
        encoded = jwt.encode(payload, self.secret, algorithm=self.algorithm)
        claims = TokenClaims(
            operator_id=operator_id,
            role=role,
            site_id=site_id,
            mfa=bool(mfa),
            token_type=token_type,
            jti=jti_v,
            issued_at=issued_at,
            expires_at=expires_at,
            raw=payload,
        )
        return encoded, claims

    # ── Verify ──────────────────────────────────────────────────────────────

    def decode(self, token: str, *, expected_type: TokenType) -> TokenClaims:
        """Decode + validate a token. Raises :class:`JWTError` on any failure."""

        if not token:
            raise JWTError("missing_token")
        try:
            payload = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=JWT_LEEWAY_S,
                options={
                    "require": ["iss", "aud", "sub", "exp", "iat", "jti", "typ", "role"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise JWTError("token_expired") from exc
        except jwt.InvalidAudienceError as exc:
            raise JWTError("invalid_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise JWTError("invalid_issuer") from exc
        except jwt.InvalidSignatureError as exc:
            raise JWTError("invalid_signature") from exc
        except jwt.MissingRequiredClaimError as exc:
            raise JWTError("missing_claim") from exc
        except jwt.InvalidTokenError as exc:
            # Catch-all for malformed input + future PyJWT validations.
            raise JWTError("invalid_token") from exc

        typ = payload.get("typ")
        if typ != expected_type.value:
            raise JWTError("invalid_token_type")
        role_raw = payload.get("role")
        try:
            role = OperatorRole(role_raw)
        except (ValueError, TypeError) as exc:
            raise JWTError("invalid_role") from exc
        site = payload.get("site")
        if not isinstance(site, str) or not site:
            raise JWTError("invalid_site")
        mfa_claim = payload.get("mfa")
        if not isinstance(mfa_claim, bool):
            raise JWTError("invalid_mfa_claim")
        operator_id = payload["sub"]
        if not isinstance(operator_id, str) or not operator_id:
            raise JWTError("invalid_subject")

        return TokenClaims(
            operator_id=operator_id,
            role=role,
            site_id=site,
            mfa=mfa_claim,
            token_type=TokenType(typ),
            jti=payload["jti"],
            issued_at=int(payload["iat"]),
            expires_at=int(payload["exp"]),
            raw=payload,
        )


# ── Module-level swappable singleton ───────────────────────────────────────────

_SERVICE: JWTService | None = None
_SERVICE_LOCK = threading.RLock()


def set_jwt_service(service: JWTService | None) -> None:
    global _SERVICE
    with _SERVICE_LOCK:
        _SERVICE = service


def get_jwt_service() -> JWTService:
    with _SERVICE_LOCK:
        if _SERVICE is None:
            raise JWTConfigError("JWT service not initialised")
        return _SERVICE


__all__ = (
    "DEFAULT_ACCESS_TTL_S",
    "DEFAULT_REFRESH_TTL_S",
    "JWT_ALGORITHM",
    "JWT_AUDIENCE_DEFAULT",
    "JWT_ISSUER_DEFAULT",
    "JWT_SECRET_ENV",
    "MIN_SECRET_BYTES",
    "JWTConfigError",
    "JWTError",
    "JWTService",
    "TokenClaims",
    "TokenType",
    "get_jwt_service",
    "set_jwt_service",
)
