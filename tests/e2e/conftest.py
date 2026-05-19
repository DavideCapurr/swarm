"""Phase 6.J — fixtures for the end-to-end suite.

The harness wires a real ``BusConsumer`` to the real shared ``COORDINATOR``
over the real ``InMemoryBus``, plus a real ``World`` from
``sim.swarm_sim``. The HTTP surface is the real FastAPI app (action +
read routers + auth deps) driven through ``httpx.AsyncClient`` over an
ASGI transport.

Nothing here uses ``unittest.mock``. The roadmap requires the e2e suite
to flow "tutti via API senza mock interni", and the doc-parity test in
``tests/test_phase6j_testing.py`` greps these files to enforce that
constraint.

The auth fixtures (``auth_env`` / ``operator_headers`` /
``commander_headers``) are imported from ``backend/tests/conftest.py`` so
the e2e tests share the same JWT singleton wiring the rest of the
backend test-suite already proves out.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from adapters.base import AdapterRegistry
from adapters.simulated.adapter import SimulatedAdapter
from backend.app.api.actions import _emergency_limiter, _limiter
from backend.app.api.actions import router as actions_router
from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.bus_consumer import BusConsumer
from backend.app.db import Repository, set_repository
from backend.app.ws.telemetry import WSHub

# Re-export the JWT/operator-store fixtures from the backend test suite so
# pytest picks them up under tests/e2e/ without duplicating wiring. The
# `auth_env` fixture is autouse in the backend conftest and stays autouse
# here through the import.
from backend.tests.conftest import (  # noqa: F401
    auth_env,
    commander_headers,
    commander_headers_no_mfa,
    operator_headers,
    test_totp_secret,
    token_factory,
    viewer_headers,
)
from sim.swarm_sim.world import World
from swarm_os import COORDINATOR, SWARM_STATE


@dataclass
class E2EStack:
    """Live SwarmOS in-process stack used by every e2e test.

    Components are all real: ``InMemoryBus`` (via ``BusConsumer.start()``),
    the shared ``COORDINATOR`` singleton, a ``World`` with kinematic drones,
    a ``SimulatedAdapter`` per drone in a registry, and an
    ``httpx.AsyncClient`` driving the FastAPI app. The bus is exposed so
    tests can publish telemetry / anomalies / fleet-state frames through
    the same signal path the production runner uses.
    """

    bus: object  # InMemoryBus, typed as object so the import surface stays narrow
    consumer: BusConsumer
    world: World
    registry: AdapterRegistry
    client: AsyncClient


def _reset_state() -> None:
    """Drop any lingering coordinator state between e2e tests."""

    SWARM_STATE.units.clear()
    SWARM_STATE.anomalies.clear()
    SWARM_STATE.missions.clear()
    SWARM_STATE.events.clear()
    SWARM_STATE.commands.clear()
    SWARM_STATE.tracks.clear()
    SWARM_STATE.streams.clear()
    SWARM_STATE.safety_actions.clear()
    SWARM_STATE.verifier_id = None
    SWARM_STATE.hold_patrol = False
    SWARM_STATE.emergency_active_at = None
    COORDINATOR.events.__init__()  # type: ignore[misc]
    _limiter._buckets.clear()  # type: ignore[attr-defined]
    _emergency_limiter._buckets.clear()  # type: ignore[attr-defined]


@pytest_asyncio.fixture
async def e2e_stack() -> AsyncIterator[E2EStack]:
    """Boot the in-process SwarmOS stack for one test, then tear it down."""

    _reset_state()
    set_repository(Repository(None))

    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(api_router)
    app.include_router(actions_router)

    hub = WSHub()
    consumer = BusConsumer(hub)
    await consumer.start()
    # The consumer subscribes to bus topics inside background tasks; give
    # the event loop one tick to let those subscriptions register before
    # the first publish lands.
    await asyncio.sleep(0.05)

    world = World.vineyard(n_drones=2, ignition_after_s=999.0)
    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    for drone in world.drones:
        adapter = SimulatedAdapter(agent_id=drone.agent_id, drone=drone, self_tick=False)
        await adapter.connect()
        registry.register(adapter)
        adapters.append(adapter)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://e2e") as client:
        try:
            yield E2EStack(
                bus=consumer.bus,
                consumer=consumer,
                world=world,
                registry=registry,
                client=client,
            )
        finally:
            for adapter in adapters:
                await adapter.disconnect()
            await consumer.stop()
            set_repository(Repository(None))
            _reset_state()


async def drain_bus(*, ticks: int = 5, dt: float = 0.02) -> None:
    """Yield to the event loop so the bus consumer drains queued frames.

    The ``InMemoryBus`` delivers via ``asyncio.Queue``; the consumer
    coroutine then runs ``COORDINATOR.apply_*`` and the WS broadcast.
    A short sleep loop is the deterministic way to wait for that
    pipeline without resorting to polling state.
    """

    for _ in range(ticks):
        await asyncio.sleep(dt)


__all__ = (
    "E2EStack",
    "drain_bus",
    "e2e_stack",
)
