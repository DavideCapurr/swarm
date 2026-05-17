"""Phase 4 — integration: bus consumer + coordinator round-trip into DB.

These tests drive the BusConsumer over the in-memory bus, publish a real
Telemetry / Anomaly / FleetState / MissionProgress, and check that:
  1. the projected frame ends up in the DB through REPOSITORY
  2. an operator command flows through the actions endpoint into the audit log
  3. the FastAPI lifespan-style backfill restores events into the live deque

The repository is swapped to a sqlite engine via `set_repository`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    FleetState,
    Geo,
    Telemetry,
)

from backend.app.api.actions import router as actions_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as routes_router
from backend.app.bus_consumer import BusConsumer
from backend.app.db import repository as repo_mod
from backend.app.db.models import (
    AnomalyRow,
    Base,
    EventRow,
    TelemetryRow,
)
from backend.app.db.repository import Repository, set_repository
from backend.app.hub import HUB
from swarm_os import COORDINATOR, SWARM_STATE


@pytest_asyncio.fixture
async def persisted_app() -> AsyncIterator[tuple[TestClient, Repository]]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    repo = Repository(sm)
    original = repo_mod._REPOSITORY
    set_repository(repo)

    # Reset shared coordinator state so tests don't bleed.
    SWARM_STATE.units.clear()
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.events.clear()
    SWARM_STATE.commands.clear()

    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(routes_router)
    app.include_router(actions_router)
    try:
        yield TestClient(app), repo
    finally:
        set_repository(original)
        await engine.dispose()


@pytest.mark.asyncio
async def test_bus_consumer_persists_telemetry(
    persisted_app: tuple[TestClient, Repository],
) -> None:
    _, repo = persisted_app
    consumer = BusConsumer(HUB)
    await consumer.start()
    # Let the per-topic subscriber tasks register before publishing.
    await asyncio.sleep(0.05)
    try:
        t = Telemetry(
            agent_id="ag-1",
            geo=Geo(lat=44.7, lon=8.03, alt_m=12.0),
            battery_pct=88.0,
        )
        await consumer.bus.publish("swarm:telemetry:ag-1", t.model_dump_json())
        assert await _wait_for_rows(repo, TelemetryRow, min_count=1) >= 1
    finally:
        await consumer.stop()


@pytest.mark.asyncio
async def test_bus_consumer_persists_anomaly_and_events(
    persisted_app: tuple[TestClient, Repository],
) -> None:
    _, repo = persisted_app
    consumer = BusConsumer(HUB)
    await consumer.start()
    await asyncio.sleep(0.05)
    try:
        # Need a unit on the map before an anomaly lands in a sector.
        fleet = FleetState(
            agent_id="ag-1",
            vendor="simulated",
            model="sim-x500",
            fsm_state=AgentState.ON_STATION,
            battery_pct=92.0,
            geo=Geo(lat=44.7, lon=8.03, alt_m=10.0),
        )
        await consumer.bus.publish("swarm:fleet:state", fleet.model_dump_json())

        a = Anomaly(
            kind=AnomalyKind.SMOKE,
            geo=Geo(lat=44.7, lon=8.03, alt_m=0.0),
            confidence=0.6,
            source_agent="ag-1",
        )
        await consumer.bus.publish("swarm:anomalies", a.model_dump_json())
        assert await _wait_for_rows(repo, AnomalyRow, min_count=1) >= 1
        assert await _wait_for_rows(repo, EventRow, min_count=1) >= 1
    finally:
        await consumer.stop()


@pytest.mark.asyncio
async def test_action_endpoint_persists_operator_command(
    persisted_app: tuple[TestClient, Repository],
    operator_headers: dict[str, str],
) -> None:
    """The action endpoint records each accepted command in the audit log.

    Under Phase 6.C the operator identity is read off the JWT principal,
    not the legacy ``X-Operator-Id`` header. We use the ``operator_id``
    that ``operator_headers`` mints (`op-operator01`)."""

    client, repo = persisted_app

    # The endpoint validates that the target exists in state for VERIFY.
    # Easier: use HOLD_PATROL which flips a flag and doesn't need a target.
    r = client.post(
        "/actions/hold-patrol",
        json={"target": "global"},
        headers=operator_headers,
    )
    assert r.status_code in (202, 422)  # accepted or schema-level reject
    rows = await repo.list_operator_commands(operator_id="op-operator01")
    assert len(rows) >= 1
    assert rows[-1].operator_id == "op-operator01"


@pytest.mark.asyncio
async def test_backfill_repopulates_event_deque(
    persisted_app: tuple[TestClient, Repository],
) -> None:
    """Simulating a backend restart: clear the deque, then read events back."""
    _, repo = persisted_app
    # Seed the DB.
    from swarm_core.messages import Event, EventKind

    e = Event(kind=EventKind.SYSTEM, body="boot")
    await repo.write_events([e])
    # Mimic lifespan backfill.
    SWARM_STATE.events.clear()
    rows = await repo.list_events(limit=50)
    for ev in rows:
        COORDINATOR.state.append_event(ev)
    assert any(ev.id == e.id for ev in SWARM_STATE.events)


# ── helpers ─────────────────────────────────────────────────────────────────


async def _row_count(repo: Repository, model: type) -> int:
    from sqlalchemy import func

    sm = repo._sm
    assert sm is not None
    async with sm() as db:
        count_result = await db.execute(select(func.count()).select_from(model))
        return int(count_result.scalar_one())


async def _wait_for_rows(
    repo: Repository, model: type, *, min_count: int = 1, timeout_s: float = 2.0
) -> int:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        n = await _row_count(repo, model)
        if n >= min_count:
            return n
        await asyncio.sleep(0.02)
    raise AssertionError(f"row count for {model.__name__} did not reach {min_count}")
