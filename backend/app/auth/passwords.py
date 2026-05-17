"""Password hashing — PBKDF2-HMAC-SHA256 (stdlib).

Format: ``pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>``.

PBKDF2 with 600k iterations matches OWASP 2023 guidance for SHA-256 and
keeps the implementation stdlib-only — argon2/bcrypt are stronger but
require a C-binding dep we don't otherwise need. The drone-day checklist
calls out the upgrade path when an SSO/OIDC provider takes over local
auth.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000  # OWASP 2023 minimum
PBKDF2_SALT_BYTES = 16
PBKDF2_DKLEN = 32  # 256-bit derived key


class InvalidPasswordHash(ValueError):
    """Stored hash is not in the supported PBKDF2-SHA256 envelope."""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = (-len(text)) % 4
    return base64.urlsafe_b64decode(text + ("=" * padding))


def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS) -> str:
    """Return a serialised PBKDF2 hash safe to store in YAML or a DB column."""

    if not password:
        raise ValueError("password must be non-empty")
    if iterations < 1:
        raise ValueError("iterations must be >= 1")
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=PBKDF2_DKLEN
    )
    return f"{PBKDF2_PREFIX}${iterations}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time compare of `password` against the stored envelope."""

    if not password or not stored:
        return False
    try:
        prefix, iter_str, salt_b64, hash_b64 = stored.split("$", 3)
    except ValueError as exc:
        raise InvalidPasswordHash("malformed password envelope") from exc
    if prefix != PBKDF2_PREFIX:
        raise InvalidPasswordHash(f"unsupported password scheme: {prefix!r}")
    try:
        iterations = int(iter_str)
    except ValueError as exc:
        raise InvalidPasswordHash("malformed iteration count") from exc
    if iterations < 1:
        raise InvalidPasswordHash("invalid iteration count")
    try:
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, binascii.Error) as exc:
        raise InvalidPasswordHash("malformed base64 envelope") from exc

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(derived, expected)


__all__ = (
    "PBKDF2_ITERATIONS",
    "PBKDF2_PREFIX",
    "InvalidPasswordHash",
    "hash_password",
    "verify_password",
)
