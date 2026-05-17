"""Phase 6.D — ``/ready`` endpoint tests.

The endpoint must:
  - return 200 with ``{db, redis, auth} = ok`` when everything is up,
  - return 503 with a structured payload when any subsystem is down,
  - never leak a stack trace.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app.db.models import Base
from backend.app.db.repository import Repository, set_repository
from backend.app.observability.routes import public_router


@pytest.fixture
def app_with_ready() -> FastAPI:
    app = FastAPI()
    app.include_router(public_router)
    return app


@pytest_asyncio.fixture
async def healthy_repo() -> AsyncIterator[Repository]:
    """A repository wired to a live aiosqlite engine — ``SELECT 1`` succeeds."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    repo = Repository(sm)
    set_repository(repo)
    yield repo
    set_repository(Repository(None))
    await engine.dispose()


def _patch_bus(monkeypatch: pytest.MonkeyPatch, *, ping_ok: bool) -> None:
    """Install a stub bus that mimics RedisBus / InMemoryBus shape."""

    class _StubRedis:
        async def ping(self) -> bool:
            return ping_ok

    class _StubBus:
        _redis = _StubRedis()

    class _StubConsumer:
        @property
        def bus(self) -> _StubBus:
            return _StubBus()

    import backend.app.main as main_mod

    monkeypatch.setattr(main_mod, "bus_consumer", _StubConsumer())


def _patch_bus_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """In-memory bus has no `_redis`; the probe should treat that as ok."""

    class _StubInMemBus:
        # No `_redis` attribute on purpose.
        pass

    class _StubConsumer:
        @property
        def bus(self) -> _StubInMemBus:
            return _StubInMemBus()

    import backend.app.main as main_mod

    monkeypatch.setattr(main_mod, "bus_consumer", _StubConsumer())


def _patch_bus_not_started(monkeypatch: pytest.MonkeyPatch) -> None:
    class _StubConsumer:
        @property
        def bus(self) -> object:
            raise RuntimeError("BusConsumer not started")

    import backend.app.main as main_mod

    monkeypatch.setattr(main_mod, "bus_consumer", _StubConsumer())


def test_ready_returns_200_when_everything_is_up(
    app_with_ready: FastAPI,
    healthy_repo: Repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bus(monkeypatch, ping_ok=True)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"db": "ok", "redis": "ok", "auth": "ok"}


def test_ready_503_when_redis_is_down(
    app_with_ready: FastAPI,
    healthy_repo: Repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_bus(monkeypatch, ping_ok=False)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["redis"] == "down"
    assert body["checks"]["db"] == "ok"
    assert body["checks"]["auth"] == "ok"
    # No stack traces in the payload.
    assert "Traceback" not in resp.text


def test_ready_503_when_db_is_down(
    app_with_ready: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A repository that claims enabled=True but whose ``_sm()`` raises
    must surface as ``db: down`` in the readiness probe."""

    class _BrokenSM:
        def __call__(self) -> object:
            raise RuntimeError("simulated DB failure")

    class _EnabledRepo:
        enabled = True
        _sm = _BrokenSM()

    from backend.app.db.repository import set_repository

    set_repository(_EnabledRepo())  # type: ignore[arg-type]
    _patch_bus(monkeypatch, ping_ok=True)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["checks"]["db"] == "down"
    # Cleanup — let other tests use a clean disabled repo.
    set_repository(Repository(None))


def test_ready_503_when_auth_singletons_missing(
    app_with_ready: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the JWT service / operator store isn't installed, /ready is 503."""

    monkeypatch.delenv("SWARM_AUTH_DISABLED", raising=False)
    # The autouse `auth_env` fixture installed JWT + store. Wipe them
    # for this test only.
    from backend.app.auth import set_jwt_service, set_operator_store

    set_jwt_service(None)
    set_operator_store(None)
    _patch_bus(monkeypatch, ping_ok=True)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["checks"]["auth"] == "down"


def test_ready_in_memory_bus_is_ready(
    app_with_ready: FastAPI,
    healthy_repo: Repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The probe must not falsely fail when the bus is in-memory."""

    _patch_bus_in_memory(monkeypatch)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["redis"] == "ok"


def test_ready_503_when_bus_not_started(
    app_with_ready: FastAPI,
    healthy_repo: Repository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the bus consumer is pre-startup, the redis check returns down."""

    _patch_bus_not_started(monkeypatch)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["checks"]["redis"] == "down"


def test_ready_persistence_disabled_treated_as_ready(
    app_with_ready: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No DATABASE_URL means demo mode — the DB check returns ok."""

    monkeypatch.delenv("DATABASE_URL", raising=False)
    set_repository(Repository(None))
    _patch_bus(monkeypatch, ping_ok=True)
    client = TestClient(app_with_ready)
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["checks"]["db"] == "ok"
