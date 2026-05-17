"""Phase 6.D — HTTP middleware: request id + latency histogram.

Two middlewares live here:

  - ``RequestIDMiddleware``: read or mint a request id, propagate it to
    the response headers (``X-Request-ID``), and bind it to the
    structlog context for the duration of the request so every log
    line emitted by the handler carries the correlation id.

  - ``RequestLatencyMiddleware``: observe the request duration into the
    Prometheus histogram with ``(route, method, status)`` labels. Uses
    the FastAPI route template (``/missions/{mission_id}/history``)
    rather than the rendered path so the cardinality stays bounded.

Both are added at FastAPI app construction. The request-id middleware
runs *outermost* so the id is available to every other middleware (and
their log lines), and the response gets the header even on error.
"""

from __future__ import annotations

import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Final

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.app.observability.logging import (
    bind_request_context,
    clear_request_context,
)
from backend.app.observability.metrics import get_metrics

REQUEST_ID_HEADER: Final[str] = "X-Request-ID"

# Conservative regex: only allow URL-safe chars in an inbound request id
# so we can't be used to inject CRLF or shell metacharacters into
# downstream logs. Anything that doesn't match gets a fresh server-side
# id.
_VALID_REQUEST_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")


def _new_request_id() -> str:
    return uuid.uuid4().hex


def _extract_request_id(request: Request) -> str:
    raw = request.headers.get(REQUEST_ID_HEADER, "").strip()
    if raw and _VALID_REQUEST_ID_RE.fullmatch(raw):
        return raw
    return _new_request_id()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate / propagate ``X-Request-ID`` and bind it to log context.

    A caller supplying a valid id (alphanumeric / underscore / hyphen,
    ≤128 chars) gets it echoed back; anything else is replaced by a
    fresh server-side id so a malicious client can't inject log
    payloads through the header.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _extract_request_id(request)
        # Stash on the ASGI scope so handlers / other middlewares can
        # read it without re-parsing headers.
        request.state.request_id = request_id
        bind_request_context(request_id=request_id, path=request.url.path,
                             method=request.method)
        try:
            response = await call_next(request)
        finally:
            clear_request_context()
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


# ── Latency histogram ─────────────────────────────────────────────────────────


def _route_template(request: Request) -> str:
    """Return the FastAPI route template if one was matched, else ``"<other>"``.

    Using the template keeps the cardinality of the histogram bounded —
    we don't want every ``/missions/abc-123/history`` to count as a
    separate label set.
    """

    route = request.scope.get("route")
    if route is None:
        return "<other>"
    # FastAPI stores `path` on its Route objects; fallback for raw
    # Starlette routes.
    path: object = getattr(route, "path", None) or getattr(route, "path_format", None)
    return str(path) if path else "<other>"


class RequestLatencyMiddleware(BaseHTTPMiddleware):
    """Observe request duration into the Prometheus histogram."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            template = _route_template(request)
            metrics = get_metrics()
            metrics.http_request_duration_seconds.labels(
                route=template,
                method=request.method,
                status=str(status_code),
            ).observe(elapsed)


__all__ = (
    "REQUEST_ID_HEADER",
    "RequestIDMiddleware",
    "RequestLatencyMiddleware",
)
