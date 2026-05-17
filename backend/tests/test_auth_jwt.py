"""Phase 6.C — JWT issuance + verification unit tests."""

from __future__ import annotations

import time

import jwt as pyjwt
import pytest

from backend.app.auth.jwt import (
    JWTConfigError,
    JWTError,
    JWTService,
    TokenType,
)
from backend.app.auth.store import OperatorRole

TEST_SECRET = b"a" * 32


def _service(**kwargs: object) -> JWTService:
    return JWTService(secret=TEST_SECRET, **kwargs)  # type: ignore[arg-type]


def test_issue_and_decode_round_trip() -> None:
    svc = _service()
    token, claims = svc.issue(
        operator_id="op-alice01",
        role=OperatorRole.OPERATOR,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
    )
    decoded = svc.decode(token, expected_type=TokenType.ACCESS)
    assert decoded.operator_id == "op-alice01"
    assert decoded.role is OperatorRole.OPERATOR
    assert decoded.token_type is TokenType.ACCESS
    assert decoded.site_id == "vineyard-01"
    assert decoded.mfa is False
    assert decoded.jti == claims.jti


def test_decode_rejects_expired_token() -> None:
    svc = _service(access_ttl_s=1, refresh_ttl_s=2)
    token, _ = svc.issue(
        operator_id="op-x",
        role=OperatorRole.OPERATOR,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
        now=int(time.time()) - 3600,
    )
    with pytest.raises(JWTError, match="token_expired"):
        svc.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_wrong_signature() -> None:
    svc = _service()
    other = JWTService(secret=b"b" * 32)
    token, _ = svc.issue(
        operator_id="op-x",
        role=OperatorRole.OPERATOR,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
    )
    with pytest.raises(JWTError):
        other.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_wrong_audience() -> None:
    svc = _service()
    payload = {
        "iss": svc.issuer,
        "aud": "evil",
        "sub": "op-x",
        "role": OperatorRole.OPERATOR.value,
        "site": "vineyard-01",
        "mfa": False,
        "typ": TokenType.ACCESS.value,
        "jti": "xyz",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = pyjwt.encode(payload, svc.secret, algorithm="HS256")
    with pytest.raises(JWTError):
        svc.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_wrong_issuer() -> None:
    svc = _service()
    payload = {
        "iss": "spoof",
        "aud": svc.audience,
        "sub": "op-x",
        "role": OperatorRole.OPERATOR.value,
        "site": "vineyard-01",
        "mfa": False,
        "typ": TokenType.ACCESS.value,
        "jti": "xyz",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = pyjwt.encode(payload, svc.secret, algorithm="HS256")
    with pytest.raises(JWTError):
        svc.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_wrong_typ() -> None:
    """An access token must not validate as a refresh token (or vice versa)."""

    svc = _service()
    access, _ = svc.issue(
        operator_id="op-x",
        role=OperatorRole.OPERATOR,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
    )
    with pytest.raises(JWTError, match="invalid_token_type"):
        svc.decode(access, expected_type=TokenType.REFRESH)


def test_decode_rejects_missing_claims() -> None:
    svc = _service()
    payload = {
        "iss": svc.issuer,
        "aud": svc.audience,
        "sub": "op-x",
        # `role` deliberately missing
        "site": "vineyard-01",
        "mfa": False,
        "typ": TokenType.ACCESS.value,
        "jti": "xyz",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = pyjwt.encode(payload, svc.secret, algorithm="HS256")
    with pytest.raises(JWTError):
        svc.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_invalid_role() -> None:
    svc = _service()
    payload = {
        "iss": svc.issuer,
        "aud": svc.audience,
        "sub": "op-x",
        "role": "god-mode",
        "site": "vineyard-01",
        "mfa": False,
        "typ": TokenType.ACCESS.value,
        "jti": "xyz",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    token = pyjwt.encode(payload, svc.secret, algorithm="HS256")
    with pytest.raises(JWTError, match="invalid_role"):
        svc.decode(token, expected_type=TokenType.ACCESS)


def test_decode_rejects_missing_token() -> None:
    svc = _service()
    with pytest.raises(JWTError, match="missing_token"):
        svc.decode("", expected_type=TokenType.ACCESS)


def test_jwt_service_rejects_short_secret() -> None:
    with pytest.raises(JWTConfigError):
        JWTService(secret=b"too-short")


def test_jwt_service_rejects_inverted_ttls() -> None:
    with pytest.raises(JWTConfigError):
        JWTService(
            secret=TEST_SECRET, access_ttl_s=600, refresh_ttl_s=300
        )


def test_from_env_rejects_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWARM_JWT_SECRET", raising=False)
    with pytest.raises(JWTConfigError):
        JWTService.from_env()


def test_from_env_rejects_short_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_JWT_SECRET", "tiny")
    with pytest.raises(JWTConfigError):
        JWTService.from_env()


def test_decode_rejects_algorithm_substitution() -> None:
    """The decoder allowlists exactly HS256.

    A token signed with ``none`` or ``HS384`` must not validate even if
    its payload claims the right issuer/audience — defends against the
    classic alg-confusion attack."""

    svc = _service()
    payload = {
        "iss": svc.issuer,
        "aud": svc.audience,
        "sub": "op-x",
        "role": OperatorRole.OPERATOR.value,
        "site": "vineyard-01",
        "mfa": False,
        "typ": TokenType.ACCESS.value,
        "jti": "xyz",
        "iat": int(time.time()),
        "exp": int(time.time()) + 60,
    }
    hs384 = pyjwt.encode(payload, svc.secret, algorithm="HS384")
    with pytest.raises(JWTError):
        svc.decode(hs384, expected_type=TokenType.ACCESS)
