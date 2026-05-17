"""Async engine + sessionmaker for Phase 4 persistence.

Two modes:
  - **disabled** — `DATABASE_URL` is empty. `get_sessionmaker()` returns None
    and the repository becomes a no-op. Tests and the demo can run without a
    Postgres daemon.
  - **enabled** — `DATABASE_URL` is set. The engine connects with
    `pool_pre_ping=True` and (in non-dev) requires SSL.

Security:
  - DB credentials never appear in code; only `DATABASE_URL` is read from env.
  - When `SWARM_ENV != "dev"` and the URL is Postgres, we force `ssl=true`
    via `connect_args` so a misconfigured URL can't downgrade to plaintext.
  - The engine is constructed lazily on first call to `init_persistence()`.
"""

from __future__ import annotations

import os
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _database_url() -> str:
    """Read `DATABASE_URL` from env. Empty string means persistence disabled."""
    return (os.getenv("DATABASE_URL") or "").strip()


def _is_dev() -> bool:
    return os.getenv("SWARM_ENV", "dev").lower() == "dev"


def _engine_kwargs(url_str: str) -> dict[str, Any]:
    """Return create_async_engine kwargs with SSL enforced outside dev."""
    url: URL = make_url(url_str)
    kwargs: dict[str, Any] = {"future": True, "pool_pre_ping": True}
    # SQLite (tests) has no pool pre-ping concept; skip the kwarg.
    if url.drivername.startswith("sqlite"):
        return {"future": True}
    # asyncpg accepts `ssl="require"` via connect_args, which is the same as
    # libpq's `sslmode=require`. We only enforce it outside dev so a developer
    # running plain `docker compose up` doesn't need a self-signed cert.
    if not _is_dev() and url.drivername.startswith("postgresql"):
        # Only inject if the URL didn't already specify ssl behavior.
        existing_query = dict(url.query)
        if "ssl" not in existing_query and "sslmode" not in existing_query:
            kwargs["connect_args"] = {"ssl": "require"}
    return kwargs


def make_engine(url: str | None = None) -> AsyncEngine:
    """Build an async engine. Raises if no URL is configured."""
    url_str = url if url is not None else _database_url()
    if not url_str:
        raise RuntimeError(
            "DATABASE_URL is not set. Persistence is disabled — "
            "call is_persistence_enabled() before make_engine()."
        )
    return create_async_engine(url_str, **_engine_kwargs(url_str))


# ── Module-level singleton (lazy) ────────────────────────────────────────────
#
# The engine is created on first `init_persistence()` call. Tests bypass this
# singleton entirely and pass their own sessionmaker into the Repository.

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def is_persistence_enabled() -> bool:
    return bool(_database_url())


async def init_persistence() -> async_sessionmaker[AsyncSession] | None:
    """Create the engine + sessionmaker if `DATABASE_URL` is set.

    Idempotent: calling twice returns the same sessionmaker.
    Returns None if persistence is disabled.
    """
    global _engine, _sessionmaker
    if not is_persistence_enabled():
        return None
    if _sessionmaker is not None:
        return _sessionmaker
    _engine = make_engine()
    _sessionmaker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
    return _sessionmaker


async def shutdown_persistence() -> None:
    """Dispose of the engine. Called from FastAPI lifespan on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def get_sessionmaker() -> async_sessionmaker[AsyncSession] | None:
    """Return the module-level sessionmaker (after init), or None if disabled."""
    return _sessionmaker


# ── Backwards-compat shim (legacy `get_session` from Phase 0 scaffolding) ────
#
# The Phase 0 commit exposed `engine` + `get_session`. Phase 4 owns the engine
# via `init_persistence()`, but FastAPI dependencies that imported the old
# names still work — they just resolve lazily now.


async def get_session() -> AsyncSession:  # pragma: no cover — kept for compat
    sm = get_sessionmaker()
    if sm is None:
        raise RuntimeError("persistence is disabled — set DATABASE_URL")
    return sm()


__all__ = (
    "get_session",
    "get_sessionmaker",
    "init_persistence",
    "is_persistence_enabled",
    "make_engine",
    "shutdown_persistence",
)
