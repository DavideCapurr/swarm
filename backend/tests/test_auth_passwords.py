"""Phase 6.C — PBKDF2 password envelope unit tests."""

from __future__ import annotations

import pytest

from backend.app.auth.passwords import (
    PBKDF2_PREFIX,
    InvalidPasswordHash,
    hash_password,
    verify_password,
)


def test_hash_password_round_trip() -> None:
    pw = "swarm-test-password"
    envelope = hash_password(pw, iterations=1_000)
    assert envelope.startswith(f"{PBKDF2_PREFIX}$1000$")
    assert verify_password(pw, envelope) is True


def test_hash_password_rejects_empty_password() -> None:
    with pytest.raises(ValueError):
        hash_password("", iterations=1_000)


def test_hash_password_rejects_zero_iterations() -> None:
    with pytest.raises(ValueError):
        hash_password("x", iterations=0)


def test_verify_password_constant_time_wrong_password() -> None:
    envelope = hash_password("right-password", iterations=1_000)
    assert verify_password("wrong-password", envelope) is False


def test_verify_password_returns_false_on_empty_inputs() -> None:
    envelope = hash_password("abc", iterations=1_000)
    assert verify_password("", envelope) is False
    assert verify_password("abc", "") is False


def test_verify_password_rejects_unsupported_scheme() -> None:
    with pytest.raises(InvalidPasswordHash):
        verify_password("x", "bcrypt$1$salt$hash")


def test_verify_password_rejects_malformed_envelope() -> None:
    with pytest.raises(InvalidPasswordHash):
        verify_password("x", "not-an-envelope")


def test_verify_password_rejects_malformed_iterations() -> None:
    with pytest.raises(InvalidPasswordHash):
        verify_password("x", "pbkdf2_sha256$abc$salt$hash")


def test_verify_password_rejects_zero_iterations() -> None:
    with pytest.raises(InvalidPasswordHash):
        verify_password("x", "pbkdf2_sha256$0$AAAA$AAAA")


def test_hash_is_salted_per_call() -> None:
    """Same password, two calls → two different envelopes (salt rotation)."""

    a = hash_password("same", iterations=1_000)
    b = hash_password("same", iterations=1_000)
    assert a != b
    assert verify_password("same", a) is True
    assert verify_password("same", b) is True
