"""Security primitives wired into the FastAPI app.

This module is the single place where all defensive defaults live. It is
intentionally framework-light so its individual pieces can be unit-tested
without spinning up FastAPI.

Controls implemented here (numbered per `docs/plan/swarmos-roadmap.md`):
  - S8  CORS allowlist (env-driven) + WebSocket origin check
  - S9  Security response headers middleware (CSP, X-CTO, X-Frame-Options,
        Referrer-Policy, Permissions-Policy, HSTS)
  - S22 Body size limit (1 MB default)
  - S23 Request timeout (30 s default)
  - S24 Error handler returning structured JSON, never a stack trace
  - S30 Operator-id regex (Phase 1 transitional auth before JWT)
  - S31 Token-bucket per-IP rate limiter (Phase 1, wired here in Phase 0)
"""

from __future__ import annotations

import asyncio
import os
import re
import secrets
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocket
from swarm_core.runtime import is_prod_like_env

# ── CORS / Origin allowlist ────────────────────────────────────────────────────

_DEFAULT_ALLOWED_ORIGINS = "http://localhost:3000"


def get_allowed_origins() -> list[str]:
    """Read CORS allowlist from env. Never returns `["*"]` in prod.

    Local dev: defaults to `http://localhost:3000`.
    Prod: set `SWARM_ALLOWED_ORIGINS` to a comma-separated list of
    fully-qualified origins (e.g. `https://swarm.example.com`).
    """
    raw = os.getenv("SWARM_ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS)
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if "*" in origins:
        # Hard-fail in production posture rather than silently regress.
        raise RuntimeError(
            "SWARM_ALLOWED_ORIGINS contains '*'. Refusing wildcard CORS — "
            "set explicit origins."
        )
    return origins


ALLOWED_METHODS: Final[tuple[str, ...]] = ("GET", "POST", "OPTIONS")
ALLOWED_HEADERS: Final[tuple[str, ...]] = (
    "content-type",
    "authorization",
    "x-operator-id",
    "x-request-id",
)


def check_websocket_origin(websocket: WebSocket) -> bool:
    """Return True iff the WS connection origin is in the allowlist.

    A missing `Origin` header is treated as denied — same-origin browsers
    always send one for `ws://`/`wss://`, so absence indicates a non-browser
    client that should authenticate via another channel (Phase 6).
    """
    origin = websocket.headers.get("origin")
    if not origin:
        return False
    return origin in get_allowed_origins()


# ── Security headers ───────────────────────────────────────────────────────────


def _csp_directive() -> str:
    """Content-Security-Policy. Phase 0: restrictive default.

    `connect-src` allows the WS upgrade. `img-src` allows the MapLibre raster
    basemap (CartoDB) used by the Console — when we self-host tiles this
    relaxation can shrink to `'self'`.
    """
    return "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "object-src 'none'",
            "connect-src 'self' ws: wss:",
            "img-src 'self' data: blob: https:",
            "style-src 'self' 'unsafe-inline'",  # Tailwind inline; tighten in Phase 6 with nonce
            "script-src 'self'",
            "font-src 'self' data:",
        ]
    )


def _is_prod() -> bool:
    return is_prod_like_env()


def security_headers() -> dict[str, str]:
    """Headers attached to every HTTP response."""
    headers = {
        "Content-Security-Policy": _csp_directive(),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
    if _is_prod():
        headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for k, v in security_headers().items():
            response.headers[k] = v
        return response


# ── Body size limit + request timeout (S22, S23) ───────────────────────────────

BODY_SIZE_LIMIT_BYTES: Final[int] = 1_000_000  # 1 MB
REQUEST_TIMEOUT_S: Final[float] = 30.0


class BodySizeLimitMiddleware:
    """Reject requests whose declared Content-Length exceeds the limit.

    Streaming bodies without Content-Length are allowed through but capped at
    the same byte budget downstream via ASGI receive wrapping.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = BODY_SIZE_LIMIT_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Cheap path: trust Content-Length when present.
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        await _send_413(send)
                        return
                except ValueError:
                    await _send_413(send)
                    return
                break

        # Otherwise cap on the fly.
        bytes_received = 0
        max_bytes = self.max_bytes

        async def capped_receive() -> MutableMapping[str, Any]:
            nonlocal bytes_received
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"") or b""
                bytes_received += len(body) if isinstance(body, (bytes, bytearray)) else 0
                if bytes_received > max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, capped_receive, send)
        except _BodyTooLarge:
            await _send_413(send)


class _BodyTooLarge(Exception):
    pass


async def _send_413(send: Send) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b'{"error":"request_too_large"}',
        }
    )


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    """Cancel a request that runs longer than REQUEST_TIMEOUT_S seconds."""

    def __init__(self, app: ASGIApp, timeout_s: float = REQUEST_TIMEOUT_S) -> None:
        super().__init__(app)
        self.timeout_s = timeout_s

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await asyncio.wait_for(call_next(request), timeout=self.timeout_s)
        except TimeoutError:
            return JSONResponse(
                {"error": "request_timeout", "timeout_s": self.timeout_s},
                status_code=504,
            )


# ── Operator ID validation (S30) ───────────────────────────────────────────────

OPERATOR_ID_RE: Final[re.Pattern[str]] = re.compile(r"^op-[a-z0-9]{4,32}$")


def is_valid_operator_id(value: str | None) -> bool:
    """Phase 1 transitional gate before full JWT/OIDC (Phase 6).

    Rejects empty, malformed, or oversize values. The regex deliberately
    forbids underscores, dashes after `op-`, uppercase, and Unicode to keep
    log lines + audit rows trivially safe.
    """
    if value is None:
        return False
    if len(value) > 64:  # belt-and-braces against degenerate inputs
        return False
    return bool(OPERATOR_ID_RE.fullmatch(value))


# ── Token-bucket rate limiter (S31) ────────────────────────────────────────────


@dataclass
class _Bucket:
    capacity: int
    refill_per_s: float
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.monotonic)


class RateLimiter:
    """In-memory per-key token-bucket. Use for action endpoints.

    `capacity` tokens drained per request, refilled at `refill_per_s` tokens
    per second. Default 30 req/min ≡ refill 0.5/s with capacity 30.

    In-memory means single-process. For multi-replica deployment this is
    replaced by a Redis-backed implementation in Phase 4.
    """

    def __init__(self, capacity: int = 30, refill_per_s: float = 0.5) -> None:
        self.capacity = capacity
        self.refill_per_s = refill_per_s
        self._buckets: dict[str, _Bucket] = defaultdict(self._new_bucket)
        self._lock = asyncio.Lock()

    def _new_bucket(self) -> _Bucket:
        return _Bucket(
            capacity=self.capacity,
            refill_per_s=self.refill_per_s,
            tokens=float(self.capacity),
        )

    async def allow(self, key: str) -> bool:
        async with self._lock:
            b = self._buckets[key]
            now = time.monotonic()
            elapsed = now - b.last_refill
            b.tokens = min(b.capacity, b.tokens + elapsed * b.refill_per_s)
            b.last_refill = now
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return True
            return False


# ── Structured error handler (S24) ─────────────────────────────────────────────


def error_response(
    status: int, code: str, detail: str | None = None
) -> JSONResponse:
    """Return a stable JSON shape. Never includes stack traces."""
    body: dict[str, object] = {"error": code}
    if detail:
        body["detail"] = detail
    return JSONResponse(body, status_code=status)


# ── Per-request correlation id (Phase 1 helper) ────────────────────────────────


def new_correlation_id() -> str:
    """Generate a short opaque request id (16 hex chars from os.urandom)."""
    return secrets.token_hex(8)


# ── Convenience: shape for setup ───────────────────────────────────────────────


def cors_kwargs() -> dict[str, object]:
    """Return kwargs ready for `app.add_middleware(CORSMiddleware, **kw)`."""
    return {
        "allow_origins": get_allowed_origins(),
        "allow_methods": list(ALLOWED_METHODS),
        "allow_headers": list(ALLOWED_HEADERS),
        "allow_credentials": False,
        "max_age": 600,
    }


__all__: Sequence[str] = (
    "ALLOWED_HEADERS",
    "ALLOWED_METHODS",
    "BODY_SIZE_LIMIT_BYTES",
    "OPERATOR_ID_RE",
    "REQUEST_TIMEOUT_S",
    "BodySizeLimitMiddleware",
    "RateLimiter",
    "RequestTimeoutMiddleware",
    "SecurityHeadersMiddleware",
    "check_websocket_origin",
    "cors_kwargs",
    "error_response",
    "get_allowed_origins",
    "is_valid_operator_id",
    "new_correlation_id",
    "security_headers",
)
