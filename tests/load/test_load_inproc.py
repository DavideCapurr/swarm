"""Phase 6.F — in-process load smoke.

Three assertions, all marked ``load_smoke`` so they only run when the
caller asks for them (``pytest -m load_smoke``):

  1. ``test_p95_ws_latency`` — 50 agents publish telemetry through a real
     ``BusConsumer`` + ``InMemoryBus`` + ``WSHub``; the p95 latency from
     ``bus.publish`` to ``unit`` frame receipt at a fake WS client must
     be under 200 ms.

  2. ``test_rest_p95_under_load`` — same load profile, plus concurrent
     REST polls of ``/awareness``, ``/units``, ``/anomalies``,
     ``/missions``. p95 must be under 100 ms.

  3. ``test_burst_200_units_graceful`` — 200 agents publish at a rate
     above the configured ``TelemetryRateLimiter`` cap. Assert that the
     consumer never raises and the limiter's ``dropped_total`` counter
     advances, proving graceful degradation rather than crash.

The window is intentionally short (≤ 5 s) so CI smoke stays under
10 s of wall time per assertion; the longer ``500 msg/s x 5 min`` profile
runs out-of-process via ``python -m tests.load.driver``.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from backend.app.api.routes import public_router as public_api_router
from backend.app.api.routes import router as api_router
from backend.app.auth import (
    JWTService,
    Operator,
    OperatorRole,
    OperatorStore,
    RevocationStore,
    TokenType,
    hash_password,
    set_jwt_service,
    set_operator_store,
    set_revocation_store,
)
from backend.app.bus_consumer import BusConsumer
from backend.app.ws.telemetry import WSHub
from swarm_os import COORDINATOR
from tests.load.conftest import LoadHarness, latency_samples, percentile

WS_P95_TARGET_S = 0.200
REST_P95_TARGET_S = 0.100

# Default smoke profile: 50 agents x 1 Hz over 5 s = 250 publishes.
# Each publish produces ≥ 1 ``unit`` frame per WS client, plenty for a
# stable p95 estimate while keeping the CI smoke under ~10 s.
SMOKE_AGENTS = 50
SMOKE_HZ = 1.0
SMOKE_DURATION_S = 5.0


pytestmark = pytest.mark.load_smoke


@pytest.mark.asyncio
async def test_p95_ws_latency(load_harness: LoadHarness) -> None:
    """50-agent x 1 Hz x 5 s → ``unit`` frame p95 < 200 ms.

    The fake client records ``time.monotonic()`` on each receipt; the
    fixture records the publish timestamp; ``latency_samples`` matches
    them FIFO per agent.
    """

    [client] = await load_harness.attach_clients(1)
    agents = [f"sim-{i:02d}" for i in range(SMOKE_AGENTS)]
    publishes = await load_harness.publish_telemetry(
        agents, per_agent_hz=SMOKE_HZ, duration_s=SMOKE_DURATION_S
    )
    # Drain the bus queue so every publish has been broadcast.
    await asyncio.sleep(0.25)
    samples = latency_samples(publishes, client.received, kind="unit")
    assert samples, "no matched receipts — consumer not running?"
    p95 = percentile(samples, 95.0)
    assert p95 < WS_P95_TARGET_S, (
        f"WS p95 latency {p95 * 1000:.1f} ms > {WS_P95_TARGET_S * 1000:.0f} ms "
        f"(n={len(samples)}, p50={percentile(samples, 50) * 1000:.1f} ms, "
        f"p99={percentile(samples, 99) * 1000:.1f} ms)"
    )


# ── REST test ────────────────────────────────────────────────────────────────


_TEST_JWT_SECRET = b"swarm-load-test-jwt-secret-not-prod-32"
_TEST_VIEWER_ID = "op-loadviewer01"
_TEST_PASSWORD = "swarm-load-test-pw"


@pytest.fixture
def _rest_auth_env() -> Iterator[str]:
    """Spin a JWT service + single-viewer operator store for the REST test.

    Returns the bearer access token. The fixture restores singletons
    after the test so other tests are not affected.
    """

    service = JWTService(secret=_TEST_JWT_SECRET)
    set_jwt_service(service)
    operators = {
        _TEST_VIEWER_ID: Operator(
            operator_id=_TEST_VIEWER_ID,
            password_hash=hash_password(_TEST_PASSWORD, iterations=1_000),
            role=OperatorRole.VIEWER,
        ),
    }
    set_operator_store(OperatorStore(operators=operators))
    set_revocation_store(RevocationStore())
    token, _ = service.issue(
        operator_id=_TEST_VIEWER_ID,
        role=OperatorRole.VIEWER,
        site_id="vineyard-01",
        mfa=False,
        token_type=TokenType.ACCESS,
    )
    try:
        yield token
    finally:
        set_jwt_service(None)
        set_operator_store(None)
        set_revocation_store(None)


@pytest_asyncio.fixture
async def _rest_app(load_harness: LoadHarness) -> AsyncIterator[FastAPI]:
    """Stand-up a FastAPI app that shares the running coordinator state.

    No middleware — those are exercised by ``test_api_smoke.py``; here
    we only care about the per-route projection latency.
    """

    app = FastAPI()
    app.include_router(public_api_router)
    app.include_router(api_router)
    yield app


@pytest.mark.asyncio
async def test_rest_p95_under_load(
    load_harness: LoadHarness,
    _rest_app: FastAPI,
    _rest_auth_env: str,
) -> None:
    """REST polls under 50-agent telemetry load → p95 < 100 ms."""

    token = _rest_auth_env
    headers = {"Authorization": f"Bearer {token}"}
    paths = ("/awareness", "/units", "/anomalies", "/missions")

    samples: list[float] = []
    errors = 0

    async def _poll(client: httpx.AsyncClient, stop: asyncio.Event) -> None:
        nonlocal errors
        idx = 0
        while not stop.is_set():
            path = paths[idx % len(paths)]
            idx += 1
            t0 = time.monotonic()
            try:
                r = await client.get(path, headers=headers, timeout=5.0)
                elapsed = time.monotonic() - t0
                if r.status_code >= 500:
                    errors += 1
                else:
                    samples.append(elapsed)
            except httpx.HTTPError:
                errors += 1
            # ASGITransport completes requests in-loop without socket I/O,
            # so a tight poll loop can starve the event-loop timer. Yield
            # once per iteration to let ``asyncio.sleep`` (e.g. the
            # publisher's pacing) and the publisher task make progress.
            await asyncio.sleep(0)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_rest_app),
        base_url="http://test",
    ) as client:
        stop = asyncio.Event()
        pollers = [asyncio.create_task(_poll(client, stop)) for _ in range(4)]
        # Run the publisher alongside the REST pollers so the projection
        # is genuinely under load while we measure REST latency.
        agents = [f"sim-{i:02d}" for i in range(SMOKE_AGENTS)]
        try:
            await load_harness.publish_telemetry(
                agents, per_agent_hz=SMOKE_HZ, duration_s=SMOKE_DURATION_S
            )
        finally:
            stop.set()
            for t in pollers:
                t.cancel()
            for t in pollers:
                with contextlib.suppress(asyncio.CancelledError):
                    await t

    assert errors == 0, f"REST 5xx during load: {errors}"
    assert samples, "no REST samples — pollers never ran"
    p95 = percentile(samples, 95.0)
    assert p95 < REST_P95_TARGET_S, (
        f"REST p95 {p95 * 1000:.1f} ms > {REST_P95_TARGET_S * 1000:.0f} ms "
        f"(n={len(samples)}, p50={percentile(samples, 50) * 1000:.1f} ms)"
    )


# ── Burst graceful-degradation test ──────────────────────────────────────────


@pytest_asyncio.fixture
async def _burst_harness() -> AsyncIterator[BusConsumer]:
    """A harness with a deliberately low telemetry cap (5 Hz).

    The burst test publishes at 10 Hz/agent through 200 agents — well
    above the cap — so the per-agent rate limiter must drop ≥ 1 frame
    per agent and the consumer must never raise. ``_burst_harness``
    yields ``(consumer, agents)`` for the test body.
    """

    state = COORDINATOR.state
    state.units.clear()
    state.anomalies.clear()
    state.missions.clear()
    state.events.clear()
    state.commands.clear()
    state.tracks.clear()
    state.streams.clear()
    state.safety_actions.clear()

    hub = WSHub()
    # Cap deliberately low so the test publishes well above the limit and
    # ``dropped_total`` is guaranteed to advance — proving the rate
    # limiter is wired even when the consumer can't be saturated above
    # its in-process drain rate.
    consumer = BusConsumer(hub, telemetry_rate_limit_hz=1.0)
    await consumer.start()
    await asyncio.sleep(0.05)
    try:
        yield consumer
    finally:
        await consumer.stop()


@pytest.mark.asyncio
async def test_burst_200_units_graceful(_burst_harness: BusConsumer) -> None:
    """200 agents x ~10 Hz x 2 s → rate-limiter drops, never crashes."""

    consumer = _burst_harness
    bus = consumer.bus
    rate_limiter = consumer._telemetry_limiter  # type: ignore[attr-defined]
    # Build a single payload per agent — content doesn't matter, only that
    # the consumer accepts/drops it via the limiter.
    from swarm_core.messages import Attitude, Geo, Telemetry

    agents = [f"burst-{i:03d}" for i in range(200)]
    payload_per_agent = {
        aid: Telemetry(
            agent_id=aid,
            geo=Geo(lat=44.7, lon=8.03, alt_m=10.0),
            attitude=Attitude(),
            battery_pct=90.0,
            link_quality=0.95,
        ).model_dump_json()
        for aid in agents
    }
    accepted_before = rate_limiter.stats["accepted_total"]
    dropped_before = rate_limiter.stats["dropped_total"]

    # Burst: publish as fast as the bus accepts. With cap=5 Hz/agent and
    # ~2 s of total publish time, the limiter must drop everything past
    # the first 10 frames per agent. We don't pace the publisher — the
    # InMemoryBus queue backpressures us via ``await``.
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        for aid in agents:
            await bus.publish(f"swarm:telemetry:{aid}", payload_per_agent[aid])
        # Yield once per fan-out so the consumer task gets a chance to
        # drain — otherwise the publisher monopolises the event loop and
        # the consumer never runs the limiter check.
        await asyncio.sleep(0)

    # Let the consumer drain.
    await asyncio.sleep(0.5)

    accepted_after = rate_limiter.stats["accepted_total"]
    dropped_after = rate_limiter.stats["dropped_total"]
    accepted_delta = accepted_after - accepted_before
    dropped_delta = dropped_after - dropped_before

    assert accepted_delta > 0, (
        f"limiter accepted zero frames — consumer not running? "
        f"(before={accepted_before}, after={accepted_after})"
    )
    assert dropped_delta > 0, (
        f"limiter dropped zero frames — rate cap not enforced "
        f"(accepted={accepted_delta}, dropped={dropped_delta})"
    )
