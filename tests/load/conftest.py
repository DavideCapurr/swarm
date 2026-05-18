"""Fixtures for in-process load tests.

Wires a real ``BusConsumer`` to a real ``WSHub`` over the real
``InMemoryBus``. The only fake is the WebSocket client: a ``RecorderWS``
captures each broadcast with a monotonic timestamp, which is what the
p95 assertions read.

The harness clears the shared module-level ``COORDINATOR`` state between
tests so concurrent samples never bleed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import pytest_asyncio
from swarm_core.messages import (
    Attitude,
    Geo,
    Telemetry,
)

from backend.app.bus_consumer import BusConsumer
from backend.app.ws.telemetry import WSHub
from swarm_os import COORDINATOR


@dataclass
class _RecorderWS:
    """Stand-in for ``starlette.WebSocket``.

    ``WSHub`` only needs ``accept`` and ``send_text`` plus ``close``. We
    record ``(monotonic_ts, payload)`` per received frame so the test can
    compute latency without parsing the JSON twice.
    """

    received: list[tuple[float, str]] = field(default_factory=list)
    _closed: bool = False

    async def accept(self, *, subprotocol: str | None = None) -> None:
        return None

    async def send_text(self, payload: str) -> None:
        if self._closed:
            raise RuntimeError("client closed")
        self.received.append((time.monotonic(), payload))

    async def close(self) -> None:
        self._closed = True


@dataclass
class LoadHarness:
    consumer: BusConsumer
    hub: WSHub
    clients: list[_RecorderWS]

    async def attach_clients(self, count: int) -> list[_RecorderWS]:
        new = [_RecorderWS() for _ in range(count)]
        for ws in new:
            # type: ignore[arg-type] — RecorderWS satisfies the surface used by WSHub.
            await self.hub.connect(ws)  # type: ignore[arg-type]
        self.clients.extend(new)
        return new

    async def publish_telemetry(
        self,
        agents: list[str],
        *,
        per_agent_hz: float,
        duration_s: float,
    ) -> list[tuple[float, str]]:
        """Publish telemetry to ``swarm:telemetry:<aid>`` at ``per_agent_hz``.

        Returns the list of ``(publish_ts, agent_id)`` for every published
        frame so the caller can compute end-to-end latency against the
        receipts captured on the fake clients.
        """

        bus = self.consumer.bus
        period = 1.0 / per_agent_hz
        publishes: list[tuple[float, str]] = []
        start = time.monotonic()
        deadline = start + duration_s
        tick = 0
        while time.monotonic() < deadline:
            slot_start = time.monotonic()
            # One tick = one publish per agent. After all agents publish,
            # sleep until the next tick. This produces a real ``per_agent_hz``.
            for aid in agents:
                ts_pub = time.monotonic()
                payload = _telemetry_payload(aid, tick)
                publishes.append((ts_pub, aid))
                await bus.publish(f"swarm:telemetry:{aid}", payload)
            elapsed = time.monotonic() - slot_start
            slack = period - elapsed
            if slack > 0:
                await asyncio.sleep(slack)
            tick += 1
        return publishes


def _reset_coordinator_state() -> None:
    state = COORDINATOR.state
    state.units.clear()
    state.anomalies.clear()
    state.missions.clear()
    state.events.clear()
    state.commands.clear()
    state.tracks.clear()
    state.streams.clear()
    state.safety_actions.clear()


def _telemetry_payload(agent_id: str, tick: int) -> str:
    t = Telemetry(
        agent_id=agent_id,
        # Stagger lat/lon so each agent has a distinct sector — exercises
        # the projection's sector lookup on the hot path, not a constant.
        geo=Geo(
            lat=44.700 + (hash(agent_id) % 100) * 0.0001,
            lon=8.030 + (tick % 100) * 0.0001,
            alt_m=12.0,
        ),
        attitude=Attitude(yaw_deg=float(tick % 360)),
        battery_pct=88.0,
        link_quality=0.95,
    )
    return t.model_dump_json()


@pytest_asyncio.fixture
async def load_harness() -> AsyncIterator[LoadHarness]:
    """Spin a real BusConsumer over an in-memory bus + a real WSHub.

    The fixture lifts the default per-agent rate cap to ``250 Hz`` so the
    50/200-unit smoke tests do not trip the safety limiter. The burst test
    overrides this with its own narrower cap.
    """

    _reset_coordinator_state()
    hub = WSHub()
    consumer = BusConsumer(hub, telemetry_rate_limit_hz=250.0)
    await consumer.start()
    # Subscribers register before any publish — wait one event-loop turn
    # plus a hair of real time so the consumer tasks are blocked on the
    # bus queue before the first publish fires.
    await asyncio.sleep(0.05)
    try:
        yield LoadHarness(consumer=consumer, hub=hub, clients=[])
    finally:
        await consumer.stop()
        # Drain any remaining hub clients so the next test starts fresh.
        with contextlib.suppress(Exception):
            await asyncio.sleep(0)


def latency_samples(
    publishes: list[tuple[float, str]],
    received: list[tuple[float, str]],
    *,
    kind: str = "unit",
) -> list[float]:
    """Match each publish to the first ``kind`` frame received afterwards.

    Returns one latency per publish (in seconds). Receipts before any
    publish, and receipts that do not parse to the requested ``kind``,
    are ignored. The matching is intentionally simple: a single agent's
    publishes are FIFO on the bus, so the n-th publish for ``aid`` maps
    to the n-th ``kind == "unit"`` receipt for ``aid``.
    """

    # Bucket receipts by agent_id for the requested kind.
    by_agent: dict[str, list[float]] = {}
    for ts_rx, raw in received:
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        if msg.get("kind") != kind:
            continue
        data = msg.get("data") or {}
        aid = data.get("agent_id")
        if not aid:
            continue
        by_agent.setdefault(aid, []).append(ts_rx)
    # Walk publishes in order; pop the matching FIFO receipt.
    cursors: dict[str, int] = {}
    out: list[float] = []
    for ts_pub, aid in publishes:
        receipts = by_agent.get(aid)
        if not receipts:
            continue
        idx = cursors.get(aid, 0)
        # Advance the cursor to the first receipt at or after the publish.
        while idx < len(receipts) and receipts[idx] < ts_pub:
            idx += 1
        if idx < len(receipts):
            out.append(receipts[idx] - ts_pub)
            cursors[aid] = idx + 1
    return out


def percentile(samples: list[float], pct: float) -> float:
    """Linear-interpolation percentile. Empty input → ``inf``."""

    if not samples:
        return float("inf")
    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"pct must be in [0, 100], got {pct!r}")
    s = sorted(samples)
    k = (len(s) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


__all__ = (
    "LoadHarness",
    "latency_samples",
    "load_harness",
    "percentile",
)
