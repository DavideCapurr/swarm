"""Tests for backend.app.security: the Phase 0 security primitives."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.security import (
    OPERATOR_ID_RE,
    BodySizeLimitMiddleware,
    RateLimiter,
    SecurityHeadersMiddleware,
    check_websocket_origin,
    cors_kwargs,
    get_allowed_origins,
    is_valid_operator_id,
)

# ── Origin allowlist ──────────────────────────────────────────────────────────


def test_get_allowed_origins_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SWARM_ALLOWED_ORIGINS", raising=False)
    assert get_allowed_origins() == ["http://localhost:3000"]


def test_get_allowed_origins_parsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SWARM_ALLOWED_ORIGINS",
        "https://swarm.example.com, https://other.example.com",
    )
    assert get_allowed_origins() == [
        "https://swarm.example.com",
        "https://other.example.com",
    ]


def test_get_allowed_origins_refuses_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "https://x.example, *")
    with pytest.raises(RuntimeError, match="wildcard"):
        get_allowed_origins()


def test_cors_kwargs_never_allow_credentials() -> None:
    kw = cors_kwargs()
    assert kw["allow_credentials"] is False


# ── Operator-id validation ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "valid",
    ["op-davide", "op-abcd", "op-0123abcd", "op-" + "z" * 32],
)
def test_operator_id_valid(valid: str) -> None:
    assert is_valid_operator_id(valid)


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "",
        "op-",
        "op-ab",  # too short
        "OP-davide",  # uppercase rejected
        "op_davide",  # underscore not in pattern
        "op-DAVIDE",  # uppercase letters
        "op-davide;DROP TABLE",  # SQL injection
        "op-" + "z" * 64,  # too long
        "../op-davide",
        "<script>",
    ],
)
def test_operator_id_invalid(invalid: str | None) -> None:
    assert not is_valid_operator_id(invalid)


def test_operator_id_regex_fullmatch_only() -> None:
    # Regex must use fullmatch — a prefix shouldn't allow trailing garbage.
    m = OPERATOR_ID_RE.fullmatch("op-davideXXX!")
    assert m is None


# ── Security headers middleware ───────────────────────────────────────────────


_HEADER_NAMES = (
    "content-security-policy",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
)


def test_security_headers_attached() -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200
    for header in _HEADER_NAMES:
        assert header in r.headers, f"missing header: {header}"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_security_headers_include_hsts_in_prod_like_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_ENV", "staging")
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    r = client.get("/ping")
    assert "strict-transport-security" in r.headers


def test_security_headers_on_cors_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS preflight responses must also carry the security headers.

    Regression: when SecurityHeadersMiddleware is registered before
    CORSMiddleware (i.e. innermost), CORS short-circuits OPTIONS and skips
    the headers middleware. The middleware order in backend.app.main puts
    SecurityHeadersMiddleware OUTERMOST so this works for preflight too.
    """
    from fastapi.middleware.cors import CORSMiddleware

    from backend.app.security import cors_kwargs

    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "https://swarm.example.com")
    app = FastAPI()
    # Order mirrors backend.app.main: CORS innermost, headers outermost.
    app.add_middleware(CORSMiddleware, **cors_kwargs())  # type: ignore[arg-type]
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def _ping() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    r = client.options(
        "/ping",
        headers={
            "Origin": "https://swarm.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    for header in _HEADER_NAMES:
        assert header in r.headers, f"preflight missing header: {header}"


# ── Body size limit ───────────────────────────────────────────────────────────


def test_body_size_limit_rejects_oversize_content_length() -> None:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=1024)

    @app.post("/echo")
    async def _echo(body: dict[str, str]) -> dict[str, str]:
        return body

    client = TestClient(app)
    big = {"x": "z" * 4096}
    r = client.post("/echo", json=big)
    assert r.status_code == 413
    assert r.json() == {"error": "request_too_large"}


def test_body_size_limit_allows_small() -> None:
    app = FastAPI()
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=4096)

    @app.post("/echo")
    async def _echo(body: dict[str, str]) -> dict[str, str]:
        return body

    client = TestClient(app)
    r = client.post("/echo", json={"x": "tiny"})
    assert r.status_code == 200


# ── Rate limiter ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rate_limiter_drains_then_refuses() -> None:
    rl = RateLimiter(capacity=3, refill_per_s=0.0)  # no refill for the test
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-a") is False


@pytest.mark.asyncio
async def test_rate_limiter_isolated_per_key() -> None:
    rl = RateLimiter(capacity=1, refill_per_s=0.0)
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-a") is False
    assert await rl.allow("ip-b") is True


@pytest.mark.asyncio
async def test_rate_limiter_refills_over_time() -> None:
    rl = RateLimiter(capacity=1, refill_per_s=100.0)  # fast refill for the test
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-a") is False
    await asyncio.sleep(0.05)  # 100 * 0.05 = 5 tokens refilled
    assert await rl.allow("ip-a") is True


@pytest.mark.asyncio
async def test_rate_limiter_evicts_idle_buckets_at_cap() -> None:
    """Hitting the bucket cap with fully-refilled (idle) buckets must
    evict them instead of denying the new key — a key-spray attacker
    can't grow the dict, but legitimate new callers still get through."""

    rl = RateLimiter(capacity=1, refill_per_s=100.0, max_buckets=3)
    for key in ("ip-a", "ip-b", "ip-c"):
        assert await rl.allow(key) is True
    await asyncio.sleep(0.05)  # every bucket fully refills → evictable
    assert await rl.allow("ip-d") is True
    assert len(rl._buckets) <= 3


@pytest.mark.asyncio
async def test_rate_limiter_fails_closed_when_every_bucket_is_active() -> None:
    rl = RateLimiter(capacity=2, refill_per_s=0.0, max_buckets=2)
    assert await rl.allow("ip-a") is True
    assert await rl.allow("ip-b") is True
    # No bucket can refill (refill 0) → nothing is evictable; the new
    # key is denied rather than growing the dict past the cap.
    assert await rl.allow("ip-c") is False
    # Established keys keep their own budget.
    assert await rl.allow("ip-a") is True


# ── WebSocket origin check ────────────────────────────────────────────────────


class _FakeWS:
    """Minimal stand-in: only the `.headers` mapping is read."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_ws_origin_check_accepts_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "https://swarm.example.com")
    ws = _FakeWS({"origin": "https://swarm.example.com"})
    # The function only reads .headers, so the WebSocket signature is satisfied
    # structurally for the duck-type.
    assert check_websocket_origin(ws)  # type: ignore[arg-type]


def test_ws_origin_check_rejects_evil(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "https://swarm.example.com")
    ws = _FakeWS({"origin": "https://evil.example"})
    assert not check_websocket_origin(ws)  # type: ignore[arg-type]


def test_ws_origin_check_rejects_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SWARM_ALLOWED_ORIGINS", "https://swarm.example.com")
    ws = _FakeWS({})
    assert not check_websocket_origin(ws)  # type: ignore[arg-type]
