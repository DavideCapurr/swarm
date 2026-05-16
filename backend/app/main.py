"""FastAPI entrypoint for SwarmOS backend.

Run: `uvicorn backend.app.main:app --reload`

This module wires together:
  - REST routes  (backend.app.api.routes)
  - WebSocket    (backend.app.ws.telemetry)
  - Bus consumer (backend.app.bus_consumer)
  - Security middleware (backend.app.security): CORS allowlist, security
    headers, body-size limit, request timeout, structured error responses.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from backend.app.api.actions import router as actions_router
from backend.app.api.routes import router as api_router
from backend.app.bus_consumer import BusConsumer
from backend.app.hub import HUB
from backend.app.security import (
    BodySizeLimitMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
    check_websocket_origin,
    cors_kwargs,
    error_response,
)

logger = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

bus_consumer = BusConsumer(HUB)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await bus_consumer.start()
    logger.info("backend ready")
    try:
        yield
    finally:
        await bus_consumer.stop()


app = FastAPI(title="SwarmOS Backend", version="0.1.0", lifespan=lifespan)

# Middleware order matters. Starlette wraps middleware in the order they're
# added: first added = innermost, last added = outermost. We want
# SecurityHeadersMiddleware OUTERMOST so it tags every response, including
# CORS preflight (which CORSMiddleware short-circuits without delegating
# inward), 413s from BodySizeLimitMiddleware, and 504s from
# RequestTimeoutMiddleware. So we add it last.
app.add_middleware(BodySizeLimitMiddleware)  # innermost: cap request bytes
app.add_middleware(CORSMiddleware, **cors_kwargs())  # type: ignore[arg-type]
app.add_middleware(RequestTimeoutMiddleware)
app.add_middleware(SecurityHeadersMiddleware)  # outermost: every response

app.include_router(api_router)
app.include_router(actions_router)


# ── Error handlers ────────────────────────────────────────────────────────────
#
# We never want a stack trace in an HTTP response, even in dev (a stale dev
# token in CI artifacts has burned product before). The handlers return a
# stable JSON shape that the Console can render without inferring schemas
# from prose.


@app.exception_handler(HTTPException)
async def _http_exception_handler(_req: Request, exc: HTTPException) -> JSONResponse:
    code = exc.detail if isinstance(exc.detail, str) else "http_error"
    return error_response(status=exc.status_code, code=code)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(req: Request, exc: Exception) -> JSONResponse:
    # Log full detail server-side; respond with an opaque code.
    logger.exception("unhandled exception on %s %s: %s", req.method, req.url.path, exc)
    return error_response(status=500, code="internal_error")


# ── WebSocket ─────────────────────────────────────────────────────────────────


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket) -> None:
    # S8: enforce origin allowlist *before* accepting. Closing with 1008
    # (policy violation) gives the client a precise reason to log.
    if not check_websocket_origin(websocket):
        await websocket.close(code=1008)
        return
    await HUB.connect(websocket)
    try:
        while True:
            # No inbound payloads expected yet. Keep the socket alive; ignore
            # client text (and bound it via the body-size middleware on HTTP
            # — WS itself has its own per-frame size from Starlette).
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws_telemetry error")
    finally:
        await HUB.disconnect(websocket)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "swarmos-backend", "version": "0.1.0"}
