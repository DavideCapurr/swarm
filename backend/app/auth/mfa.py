"""TOTP MFA (RFC 6238) using stdlib hashlib/hmac.

The commander role must enrol a TOTP secret; login fails closed when the
secret is missing or the supplied code does not validate. We keep the
window narrow (±1 step, ~90 s) and rate-limit at the route level so
brute-force is impractical.

The implementation is stdlib-only on purpose. `pyotp` would add a small
dep but the whole RFC fits in a handful of well-tested lines; the
drone-day checklist documents the swap if/when the operator base outgrows
this surface.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

DEFAULT_DIGITS = 6
DEFAULT_PERIOD_S = 30
DEFAULT_WINDOW = 1  # ±1 step → 90 s usable window
DEFAULT_SECRET_BYTES = 20  # 160-bit; standard for SHA-1 TOTP


class MFAError(ValueError):
    """Raised for malformed TOTP secrets or codes."""


def generate_totp_secret(num_bytes: int = DEFAULT_SECRET_BYTES) -> str:
    """Return a fresh base32 TOTP secret (no padding)."""

    if num_bytes < 10:
        raise MFAError("TOTP secret must be at least 10 bytes")
    raw = secrets.token_bytes(num_bytes)
    return base64.b32encode(raw).rstrip(b"=").decode("ascii")


def _decode_secret(secret: str) -> bytes:
    cleaned = secret.replace(" ", "").upper()
    if not cleaned:
        raise MFAError("empty TOTP secret")
    padding = (-len(cleaned)) % 8
    try:
        return base64.b32decode(cleaned + ("=" * padding))
    except (ValueError, binascii.Error) as exc:
        raise MFAError("malformed TOTP secret (not base32)") from exc


def _generate_code(
    secret: str,
    *,
    for_time: int,
    period: int = DEFAULT_PERIOD_S,
    digits: int = DEFAULT_DIGITS,
) -> str:
    if digits < 6 or digits > 8:
        raise MFAError("digits must be 6..8")
    key = _decode_secret(secret)
    counter = for_time // period
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = truncated % (10**digits)
    return str(code).zfill(digits)


def verify_totp_code(
    secret: str,
    code: str | None,
    *,
    now: int | None = None,
    period: int = DEFAULT_PERIOD_S,
    digits: int = DEFAULT_DIGITS,
    window: int = DEFAULT_WINDOW,
) -> bool:
    """Constant-time check of a 6-digit code against `secret`.

    Walks ``[-window, +window]`` steps to tolerate small clock skew. A
    missing or wrong-shape `code` returns ``False`` rather than raising —
    the route layer turns a False into a 401 and audits the attempt.
    """

    if code is None:
        return False
    cleaned = code.strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != digits:
        return False
    now_s = int(now if now is not None else time.time())
    for delta in range(-window, window + 1):
        try:
            candidate = _generate_code(
                secret,
                for_time=now_s + delta * period,
                period=period,
                digits=digits,
            )
        except MFAError:
            return False
        if hmac.compare_digest(candidate, cleaned):
            return True
    return False


def provisioning_uri(
    operator_id: str,
    secret: str,
    *,
    issuer: str = "SWARM",
    period: int = DEFAULT_PERIOD_S,
    digits: int = DEFAULT_DIGITS,
) -> str:
    """Build an `otpauth://totp/...` URL for QR-code enrolment.

    Format follows the Google Authenticator key URI spec so any standard
    TOTP authenticator (FreeOTP, Aegis, 1Password, …) accepts it.
    """

    if not operator_id:
        raise MFAError("operator_id is required for provisioning")
    label = f"{issuer}:{operator_id}"
    params = urlencode(
        {
            "secret": secret.replace(" ", "").upper(),
            "issuer": issuer,
            "algorithm": "SHA1",
            "digits": digits,
            "period": period,
        }
    )
    return f"otpauth://totp/{quote(label, safe=':')}?{params}"


__all__ = (
    "DEFAULT_DIGITS",
    "DEFAULT_PERIOD_S",
    "DEFAULT_SECRET_BYTES",
    "DEFAULT_WINDOW",
    "MFAError",
    "generate_totp_secret",
    "provisioning_uri",
    "verify_totp_code",
)
