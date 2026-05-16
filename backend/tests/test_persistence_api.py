"""Phase 4 — historical query endpoints + SQL-injection sanity at the HTTP layer.

These tests instantiate the FastAPI app with an aiosqlite-backed repository
swapped in via `set_repository`, then exercise the new endpoints end-to-end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from swarm_core.messages import (
    Event,
    EventKind,
    OperatorAction,
    OperatorCommand,
)

from backend.app.api.routes import router
from backend.app.db import repository as repo_mod
from backend.app.db.models import Base
from backend.app.db.repository import Repository, set_repository
from swarm_os import SWARM_STATE


@pytest_asyncio.fixture
async def app_with_persistence() -> AsyncIterator[tuple[TestClient, Repository]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    repo = Repository(sm)

    # Swap the module-level repository so the routes pick it up.
    original = repo_mod._REPOSITORY
    set_repository(repo)
    try:
        SWARM_STATE.events.clear()
        SWARM_STATE.commands.clear()
        app = FastAPI()
        app.include_router(router)
        yield TestClient(app), repo
    finally:
        set_repository(original)
        await engine.dispose()


def test_health_reports_persistence_enabled(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    client, _ = app_with_persistence
    body = client.get("/health").json()
    assert body["persistence"] is True


def test_events_history_window(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    client, repo = app_with_persistence
    base = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    older = Event(kind=EventKind.SYSTEM, body="old", ts=base - timedelta(hours=2))
    middle = Event(kind=EventKind.SYSTEM, body="middle", ts=base)
    newer = Event(kind=EventKind.SYSTEM, body="new", ts=base + timedelta(hours=2))

    import asyncio
    asyncio.get_event_loop().run_until_complete(
        repo.write_events([older, middle, newer])
    )

    r = client.get(
        "/events",
        params={
            "from": (base - timedelta(minutes=30)).isoformat(),
            "to": (base + timedelta(minutes=30)).isoformat(),
        },
    )
    assert r.status_code == 200
    ids = {e["id"] for e in r.json()["events"]}
    assert ids == {middle.id}


def test_events_history_rejects_inverted_range(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    client, _ = app_with_persistence
    r = client.get(
        "/events",
        params={
            "from": "2026-05-16T12:00:00+00:00",
            "to": "2026-05-16T11:00:00+00:00",
        },
    )
    assert r.status_code == 400


def test_mission_history_endpoint(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    client, repo = app_with_persistence
    e1 = Event(kind=EventKind.MISSION, mission_id="m-42", body="patrol started")
    e2 = Event(kind=EventKind.PATROL, mission_id="m-42", body="sector visited")
    other = Event(kind=EventKind.MISSION, mission_id="m-99", body="other mission")

    import asyncio
    asyncio.get_event_loop().run_until_complete(repo.write_events([e1, e2, other]))

    r = client.get("/missions/m-42/history")
    assert r.status_code == 200
    body = r.json()
    assert body["mission_id"] == "m-42"
    ids = {e["id"] for e in body["events"]}
    assert ids == {e1.id, e2.id}


def test_operator_commands_endpoint(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    client, repo = app_with_persistence
    alice = OperatorCommand(
        action=OperatorAction.VERIFY, target="anomaly:1", operator_id="op-alice01"
    )
    bob = OperatorCommand(
        action=OperatorAction.DISMISS, target="anomaly:2", operator_id="op-bob02"
    )
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        repo.write_operator_command(alice)
    )
    asyncio.get_event_loop().run_until_complete(
        repo.write_operator_command(bob)
    )

    r = client.get("/operator-commands", params={"operator_id": "op-alice01"})
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()["commands"]}
    assert ids == {alice.id}


def test_operator_commands_rejects_malformed_id(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    """The audit endpoint applies the same regex as the action endpoints."""
    client, _ = app_with_persistence
    r = client.get("/operator-commands", params={"operator_id": "DROP TABLE users"})
    assert r.status_code == 400


def test_mission_history_sql_injection_path_param_is_safe(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    """A SQL-shaped mission id can't drop the events table.

    The Phase 4 spec verification calls this out:
        "make audit continua a passare; aggiunto controllo SQL injection
         via test che invia '; DROP TABLE events;-- come filtro."
    """
    client, repo = app_with_persistence
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        repo.write_events([Event(kind=EventKind.SYSTEM, body="seed")])
    )

    payload = "'; DROP TABLE events;--"
    r = client.get(f"/missions/{payload}/history")
    assert r.status_code == 200
    assert r.json()["events"] == []
    # Table must still hold the seed row.
    r2 = client.get("/events", params={"from": "2026-01-01T00:00:00+00:00"})
    assert len(r2.json()["events"]) == 1


def test_events_sql_injection_payload_returns_empty(
    app_with_persistence: tuple[TestClient, Repository],
) -> None:
    """A classic injection payload as a filter must return empty + leave the DB intact."""
    client, repo = app_with_persistence
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        repo.write_events([Event(kind=EventKind.SYSTEM, body="ok")])
    )

    payload = "'; DROP TABLE events;--"
    r = client.get(
        "/events",
        params={
            "sector": payload,
            "from": "2026-01-01T00:00:00+00:00",
        },
    )
    assert r.status_code == 200
    assert r.json()["events"] == []

    # The events table must still hold our row.
    r2 = client.get("/events", params={"from": "2026-01-01T00:00:00+00:00"})
    assert r2.status_code == 200
    assert len(r2.json()["events"]) == 1
