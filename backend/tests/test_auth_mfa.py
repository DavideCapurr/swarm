"""Phase 6.C — TOTP unit tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time

import pytest

from backend.app.auth.mfa import (
    DEFAULT_PERIOD_S,
    MFAError,
    generate_totp_secret,
    provisioning_uri,
    verify_totp_code,
)


def _ref_code(secret: str, for_time: int, *, period: int = DEFAULT_PERIOD_S) -> str:
    """Reference implementation used to compute valid codes in tests."""

    cleaned = secret.replace(" ", "").upper()
    padding = (-len(cleaned)) % 8
    key = base64.b32decode(cleaned + ("=" * padding))
    counter = for_time // period
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % 1_000_000).zfill(6)


def test_generate_secret_is_base32_decodable() -> None:
    secret = generate_totp_secret()
    padding = (-len(secret)) % 8
    base64.b32decode(secret + "=" * padding)
    # Two consecutive secrets must not collide (entropy sanity).
    assert generate_totp_secret() != generate_totp_secret()


def test_generate_secret_rejects_short_request() -> None:
    with pytest.raises(MFAError):
        generate_totp_secret(num_bytes=5)


def test_verify_accepts_current_code() -> None:
    secret = generate_totp_secret()
    now = int(time.time())
    code = _ref_code(secret, now)
    assert verify_totp_code(secret, code, now=now) is True


def test_verify_accepts_previous_step_in_window() -> None:
    """A 30 s skew is tolerated by the default ±1 window."""

    secret = generate_totp_secret()
    now = int(time.time())
    code = _ref_code(secret, now - DEFAULT_PERIOD_S)
    assert verify_totp_code(secret, code, now=now) is True


def test_verify_rejects_out_of_window_code() -> None:
    secret = generate_totp_secret()
    now = int(time.time())
    far_past = _ref_code(secret, now - 5 * DEFAULT_PERIOD_S)
    assert verify_totp_code(secret, far_past, now=now) is False


def test_verify_rejects_missing_code() -> None:
    secret = generate_totp_secret()
    assert verify_totp_code(secret, None) is False
    assert verify_totp_code(secret, "") is False


def test_verify_rejects_wrong_shape() -> None:
    secret = generate_totp_secret()
    now = int(time.time())
    assert verify_totp_code(secret, "12345", now=now) is False  # 5 digits
    assert verify_totp_code(secret, "abcdef", now=now) is False  # not digits
    assert verify_totp_code(secret, "1234567", now=now) is False  # 7 digits


def test_verify_rejects_malformed_secret() -> None:
    now = int(time.time())
    assert verify_totp_code("not-base32!@#$", "123456", now=now) is False


def test_provisioning_uri_format() -> None:
    uri = provisioning_uri("op-alice01", "JBSWY3DPEHPK3PXP")
    assert uri.startswith("otpauth://totp/SWARM:op-alice01?")
    assert "secret=JBSWY3DPEHPK3PXP" in uri
    assert "issuer=SWARM" in uri
    assert "digits=6" in uri


def test_provisioning_uri_requires_operator_id() -> None:
    with pytest.raises(MFAError):
        provisioning_uri("", "JBSWY3DPEHPK3PXP")
