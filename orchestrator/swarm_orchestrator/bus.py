"""Transport bus abstraction.

Day-1 implementations:
  - `InMemoryBus` — pure asyncio, no external dep. Used in tests and as a
    graceful fallback when Redis is not available.
  - `RedisBus` — Redis pub/sub. Default in production.

The orchestrator and adapters import only the `Bus` Protocol; the concrete class
is chosen at boot. Migration paths (NATS, MQTT, ROS2 DDS) plug in here without
touching anything else.
"""

from __future__ import annotations

import asyncio
import fnmatch
from collections.abc import AsyncIterator
from typing import Protocol


class Bus(Protocol):
    """Topic-based pub/sub. Topics are strings; payloads are JSON strings."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def publish(self, topic: str, payload: str) -> None: ...

    def subscribe(self, topic_pattern: str) -> AsyncIterator[tuple[str, str]]:
        """Yields (topic, payload) tuples for messages matching the pattern."""
        ...


# ── InMemory ──────────────────────────────────────────────────────────────────


class InMemoryBus:
    """No external dependencies. Suitable for tests and the `make demo` fallback
    path when Redis is not running."""

    def __init__(self) -> None:
        self._subscribers: list[tuple[str, asyncio.Queue[tuple[str, str]]]] = []
        self._connected = False

    async def connect(self) -> None:
        self._connected = True

    async def close(self) -> None:
        self._connected = False
        for _, q in self._subscribers:
            await q.put(("__close__", ""))

    async def publish(self, topic: str, payload: str) -> None:
        for pattern, q in list(self._subscribers):
            if fnmatch.fnmatchcase(topic, pattern):
                await q.put((topic, payload))

    async def subscribe(self, topic_pattern: str) -> AsyncIterator[tuple[str, str]]:  # type: ignore[override]
        q: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=4096)
        self._subscribers.append((topic_pattern, q))
        try:
            while self._connected:
                topic, payload = await q.get()
                if topic == "__close__":
                    return
                yield topic, payload
        finally:
            self._subscribers[:] = [(p, qq) for p, qq in self._subscribers if qq is not q]


# ── Redis ─────────────────────────────────────────────────────────────────────


class RedisBus:
    """Redis pub/sub backend. Lazy-imports `redis.asyncio` so the package is
    optional at the global level (still listed in pyproject deps, but tests can
    run without redis available)."""

    def __init__(self, url: str | None = None) -> None:
        self._url = url or "redis://localhost:6379/0"
        self._redis: object | None = None
        self._pubsubs: list[object] = []

    async def connect(self) -> None:
        from redis.asyncio import from_url  # local import

        self._redis = from_url(self._url, decode_responses=True)
        # Force a real round-trip to surface connection errors immediately.
        await self._redis.ping()  # type: ignore[attr-defined]

    async def close(self) -> None:
        import contextlib

        for ps in self._pubsubs:
            with contextlib.suppress(Exception):
                await ps.aclose()  # type: ignore[attr-defined]
        self._pubsubs.clear()
        if self._redis is not None:
            await self._redis.aclose()  # type: ignore[attr-defined]
        self._redis = None

    async def publish(self, topic: str, payload: str) -> None:
        if self._redis is None:
            raise RuntimeError("RedisBus.publish before connect()")
        await self._redis.publish(topic, payload)  # type: ignore[attr-defined]

    async def subscribe(self, topic_pattern: str) -> AsyncIterator[tuple[str, str]]:  # type: ignore[override]
        if self._redis is None:
            raise RuntimeError("RedisBus.subscribe before connect()")
        ps = self._redis.pubsub()  # type: ignore[attr-defined]
        self._pubsubs.append(ps)
        await ps.psubscribe(topic_pattern)  # type: ignore[attr-defined]
        import contextlib

        try:
            async for msg in ps.listen():  # type: ignore[attr-defined]
                if msg["type"] != "pmessage":
                    continue
                yield str(msg["channel"]), str(msg["data"])
        finally:
            with contextlib.suppress(Exception):
                await ps.punsubscribe(topic_pattern)  # type: ignore[attr-defined]
