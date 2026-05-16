"""Shared backend test fixtures.

Phase 4 introduces an aiosqlite-backed persistence fixture so the repository
+ history endpoints can be exercised without a Postgres daemon.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.models import Base
from backend.app.db.repository import Repository


@pytest_asyncio.fixture
async def memory_repository() -> AsyncIterator[Repository]:
    """Repository bound to an in-memory aiosqlite engine.

    Each test gets its own engine so writes never leak between tests.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield Repository(sm)
    await engine.dispose()


@pytest.fixture
def disabled_repository() -> Repository:
    """Repository with no sessionmaker — every write becomes a no-op."""
    return Repository(None)
