"""Phase 6.D — observability endpoints.

  - ``/metrics`` — Prometheus exposition. Defaults to ``require_commander``
    (the operator role with MFA already enforced at login). An optional
    IP allowlist via ``SWARM_METRICS_IP_ALLOWLIST`` lets a scraper sitting
    on the trusted backplane skip the JWT — useful for in-cluster
    Prometheus that pulls over a private network. The default is JWT.

  - ``/ready`` — public readiness probe. Returns 200 only when database,
    Redis (via the bus consumer), and the auth singletons are all ready.
    Returns 503 with a structured ``{subsystem: ok|down}`` body otherwise.
    Never includes a stack trace.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import text
from swarm_core.runtime import env_flag

from backend.app.auth.deps import (
    AuthError,
    Principal,
    require_commander,
)
from backend.app.auth.jwt import JWTConfigError, get_jwt_service
from backend.app.auth.store import OperatorStoreNotConfigured, get_operator_store
from backend.app.db import get_repository
from backend.app.observability.metrics import CONTENT_TYPE_LATEST, get_metrics

logger = logging.getLogger("backend.observability.routes")

router = APIRouter()
public_router = APIRouter()


# ── /metrics ──────────────────────────────────────────────────────────────────


def _ip_allowlist() -> list[str]:
    """Parse ``SWARM_METRICS_IP_ALLOWLIST`` as a comma-separated CIDR list.

    Invalid CIDRs are skipped + logged once. An empty allowlist means
    "no exemption — every scrape must carry a commander JWT".
    """

    raw = (os.getenv("SWARM_METRICS_IP_ALLOWLIST") or "").strip()
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    valid: list[str] = []
    for part in parts:
        try:
            ipaddress.ip_network(part, strict=False)
        except ValueError:
            logger.warning("ignoring invalid metrics allowlist entry: %r", part)
            continue
        valid.append(part)
    return valid


def _client_ip(request: Request) -> str | None:
    client = request.client
    return client.host if client is not None else None


def _is_ip_allowed(request: Request) -> bool:
    """Return True iff the request comes from an allowlisted CIDR."""

    cidrs = _ip_allowlist()
    if not cidrs:
        return False
    host = _client_ip(request)
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    for cidr in cidrs:
        try:
            if addr in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


async def _metrics_principal_or_ip(
    request: Request,
) -> Principal | None:
    """Allow either a commander JWT *or* a request from an allowlisted CIDR.

    The IP fallback is opt-in (env var) and is meant for Prometheus
    scrapers that live on the trusted side of the network boundary —
    setting ``SWARM_METRICS_IP_ALLOWLIST=10.0.0.0/8`` ensures the
    cluster-internal scraper doesn't need a JWT. Default is empty, in
    which case this dependency falls through to ``require_commander``
    and rejects anonymous requests.
    """

    if _is_ip_allowed(request):
        return None
    # No IP exemption — require a commander JWT (MFA already enforced
    # at login). We invoke the dependency manually to keep the IP path
    # cleanly separate.
    return await require_commander(await _current_principal(request))


async def _current_principal(request: Request) -> Principal:
    # Import lazily so the dependency tree stays explicit at call time.
    from backend.app.auth.deps import get_current_principal

    return await get_current_principal(request)


@router.get("/metrics")
async def metrics(
    request: Request,
    _: Annotated[Principal | None, Depends(_metrics_principal_or_ip)],
) -> Response:
    body = get_metrics().render()
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


# ── /ready ────────────────────────────────────────────────────────────────────


async def _check_database() -> bool:
    """Run ``SELECT 1`` against the repository's sessionmaker.

    Returns True iff the engine answers. Persistence disabled (no
    repository wired) is treated as "ready" — the demo path is allowed.
    """

    repo = get_repository()
    if not repo.enabled:
        return True
    sm = getattr(repo, "_sm", None)
    if sm is None:
        return False
    try:
        async with sm() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover — defensive
        logger.exception("readiness: DB probe failed")
        return False


async def _check_redis() -> bool:
    """Ping the bus if it's the live Redis one; in-memory is always ready.

    We deliberately call the underlying redis client's ``ping()`` so
    the probe traverses the same connection the bus consumer uses.
    Anything raising is treated as down.
    """

    from backend.app.main import bus_consumer

    try:
        bus = bus_consumer.bus
    except RuntimeError:
        # Bus consumer hasn't started yet — readiness can't be claimed.
        return False
    redis_obj = getattr(bus, "_redis", None)
    if redis_obj is None:
        # In-memory bus path — nothing to ping, always "ready".
        return True
    try:
        result = redis_obj.ping()  # type: ignore[attr-defined]
        if asyncio.iscoroutine(result):
            result = await result
        return bool(result)
    except Exception:  # pragma: no cover — defensive
        logger.exception("readiness: Redis probe failed")
        return False


def _check_auth() -> bool:
    """JWT service + operator store both loaded."""

    if env_flag("SWARM_AUTH_DISABLED"):
        return True
    try:
        get_jwt_service()
        get_operator_store()
    except (JWTConfigError, OperatorStoreNotConfigured):
        return False
    return True


@public_router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    """Active readiness probe — DB + Redis + auth singletons.

    Body shape (200 + 503):

      ``{"status": "ready", "checks": {"db": "ok", "redis": "ok", "auth": "ok"}}``
      ``{"status": "degraded", "checks": {"db": "down", "redis": "ok", "auth": "ok"}}``

    No stack traces — failure reasons are server-side via the logger.
    """

    db_ok, redis_ok = await asyncio.gather(_check_database(), _check_redis())
    auth_ok = _check_auth()
    checks = {
        "db": "ok" if db_ok else "down",
        "redis": "ok" if redis_ok else "down",
        "auth": "ok" if auth_ok else "down",
    }
    all_ok = db_ok and redis_ok and auth_ok
    if not all_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "checks": checks}
    return {"status": "ready", "checks": checks}


# Unused-import guard so static checkers don't strip the AuthError
# import (used by the require_commander shim path).
_ = AuthError


__all__ = ("public_router", "router")
