"""FastAPI entrypoint for SwarmOS backend.

Run: `uvicorn backend.app.main:app --reload`

This module wires together:
  - REST routes  (backend.app.api.routes)
  - WebSocket    (backend.app.ws.telemetry)
  - Bus consumer (backend.app.bus_consumer)
  - Security middleware (backend.app.security): CORS allowlist, security
    headers, body-size limit, request timeout, structured error responses.
  - Persistence (backend.app.db): Phase 4 SQLAlchemy + Timescale (optional).
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from backend.app.api.actions import router as actions_router
from backend.app.api.admin import router as admin_router
from backend.app.api.auth_routes import router as auth_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.auth import (
    JWTConfigError,
    JWTService,
    OperatorStoreError,
    RevocationStore,
    load_operator_store,
    set_jwt_service,
    set_operator_store,
    set_revocation_store,
)
from backend.app.auth.ws_auth import authenticate_websocket
from backend.app.bus_consumer import BusConsumer
from backend.app.db import (
    Repository,
    get_repository,
    init_persistence,
    is_persistence_enabled,
    set_repository,
    shutdown_persistence,
)
from backend.app.fleet import FleetManager, UnknownVendor, VendorBootError, fleet_from_env
from backend.app.hub import HUB
from backend.app.security import (
    BodySizeLimitMiddleware,
    RequestTimeoutMiddleware,
    SecurityHeadersMiddleware,
    check_websocket_origin,
    cors_kwargs,
    error_response,
)
from swarm_os import COORDINATOR

logger = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

bus_consumer = BusConsumer(HUB)
fleet_manager: FleetManager | None = None


def _init_auth() -> None:
    """Phase 6.C — wire the JWT service, operator store, and revocation list.

    Failure modes:
      - SWARM_AUTH_DISABLED=1: skip entirely (dev-only escape hatch). The
        rest of the app then refuses any request that needs auth with
        503 ``auth_not_configured`` — operationally equivalent to "I'm
        not ready to serve" so a misconfigured prod deploy still fails
        closed without crashing the process.
      - prod (SWARM_ENV=prod) with no secret / missing operator config:
        hard crash via ``RuntimeError`` so the orchestrator restarts.
      - dev with no secret: log a warning and skip; the rest of the app
        will respond 503 on protected endpoints. This keeps test
        bootstraps that don't exercise auth from breaking.
    """

    if os.getenv("SWARM_AUTH_DISABLED") == "1":
        logger.warning(
            "SWARM_AUTH_DISABLED=1 — auth surface OFF (development only)"
        )
        return
    is_prod = os.getenv("SWARM_ENV", "dev").lower() == "prod"
    try:
        service = JWTService.from_env()
        set_jwt_service(service)
    except JWTConfigError as exc:
        if is_prod:
            raise RuntimeError(f"refusing to boot: {exc}") from exc
        logger.warning("JWT service not initialised: %s", exc)
        return
    try:
        store = load_operator_store()
        set_operator_store(store)
    except OperatorStoreError as exc:
        if is_prod:
            raise RuntimeError(f"refusing to boot: {exc}") from exc
        logger.warning("operator store not loaded: %s", exc)
        return
    set_revocation_store(RevocationStore())
    logger.info("auth ready: %d operator(s) loaded", len(store))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    global fleet_manager
    # Phase 6.C: bring auth up first so the action / admin routes have an
    # issuer + a store + a revocation list before any request lands.
    _init_auth()

    # Phase 4: bring up persistence first so the bus consumer can write.
    if is_persistence_enabled():
        try:
            sm = await init_persistence()
            set_repository(Repository(sm))
            logger.info("persistence enabled")
            # Best-effort backfill: re-hydrate the in-memory event deque from
            # the DB so the Console shows history after a backend restart.
            try:
                events = await get_repository().list_events(limit=200)
                for event in events:
                    COORDINATOR.state.append_event(event)
                logger.info("event backfill: %d row(s)", len(events))
            except Exception:  # pragma: no cover — defensive
                logger.exception("event backfill failed")
        except Exception:  # pragma: no cover
            logger.exception("persistence init failed — continuing without it")
            set_repository(Repository(None))
    else:
        logger.info("persistence disabled (DATABASE_URL not set)")

    await bus_consumer.start()
    # Phase 5: boot any in-process vendor runners declared in SWARM_VENDORS.
    # `parse_vendors` raises `UnknownVendor` on a typo — fail-fast so the
    # operator sees the misconfiguration immediately.
    try:
        fleet_manager = fleet_from_env(bus_consumer.bus)
        await fleet_manager.start()
        logger.info("fleet: vendors=%s", fleet_manager.vendors)
    except UnknownVendor as e:
        logger.error("fleet: refusing to boot (%s)", e)
        raise
    except VendorBootError as e:
        logger.error("fleet: refusing to boot (%s)", e)
        raise

    logger.info("backend ready")
    try:
        yield
    finally:
        if fleet_manager is not None:
            await fleet_manager.stop()
            fleet_manager = None
        await bus_consumer.stop()
        await shutdown_persistence()


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

app.include_router(public_api_router)
app.include_router(api_router)
app.include_router(actions_router)
app.include_router(admin_router)
app.include_router(auth_router)


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
    # Phase 6.C: every WS upgrade carries a valid access token (viewer or
    # above) or it's refused. We do not echo failure reasons — the client
    # already knows whether it sent a token.
    auth_disabled = os.getenv("SWARM_AUTH_DISABLED") == "1"
    accepted_subprotocol: str | None = None
    if not auth_disabled:
        auth = await authenticate_websocket(websocket)
        if auth is None:
            await websocket.close(code=1008)
            return
        accepted_subprotocol = auth.accepted_subprotocol
    await HUB.connect(websocket, subprotocol=accepted_subprotocol)
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
