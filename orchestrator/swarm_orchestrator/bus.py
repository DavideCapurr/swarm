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
import os
import ssl
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse


class Bus(Protocol):
    """Topic-based pub/sub. Topics are strings; payloads are JSON strings."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def publish(self, topic: str, payload: str) -> None: ...

    def subscribe(self, topic_pattern: str) -> AsyncIterator[tuple[str, str]]:
        """Yields (topic, payload) tuples for messages matching the pattern."""
        ...


_TRUTHY = {"1", "true", "yes", "on"}


class InsecureBusConfiguration(ValueError):
    """Raised when production/out-of-process transport is not fail-closed."""


def secure_bus_required() -> bool:
    """Whether Redis transport must use authenticated TLS/mTLS.

    Phase 5 dev/demo can still use local plaintext Redis or the in-memory
    fallback. Phase 6/prod, and any bench that opts into
    `SWARM_REQUIRE_SECURE_BUS=1`, must prove a secure bus before adapters are
    allowed to communicate out-of-process.
    """

    env = os.getenv("SWARM_ENV", "dev").strip().lower()
    if env in {"prod", "production"}:
        return True
    return os.getenv("SWARM_REQUIRE_SECURE_BUS", "").strip().lower() in _TRUTHY


@dataclass(frozen=True)
class RedisBusSecurity:
    """Redis TLS/mTLS settings derived from environment."""

    ssl_ca_certs: str | None = None
    ssl_certfile: str | None = None
    ssl_keyfile: str | None = None
    require_mtls: bool = False

    @classmethod
    def from_env(
        cls,
        url: str,
        *,
        require_secure: bool | None = None,
    ) -> RedisBusSecurity:
        required = secure_bus_required() if require_secure is None else require_secure
        scheme = urlparse(url).scheme.lower()
        ca_certs = os.getenv("REDIS_TLS_CA_CERTS") or None
        certfile = os.getenv("REDIS_TLS_CERTFILE") or None
        keyfile = os.getenv("REDIS_TLS_KEYFILE") or None

        if required and scheme != "rediss":
            raise InsecureBusConfiguration(
                "secure bus required: REDIS_URL must use rediss://, not "
                f"{scheme or '<missing>'}://"
            )

        if required:
            missing = [
                name
                for name, value in (
                    ("REDIS_TLS_CA_CERTS", ca_certs),
                    ("REDIS_TLS_CERTFILE", certfile),
                    ("REDIS_TLS_KEYFILE", keyfile),
                )
                if not value
            ]
            if missing:
                raise InsecureBusConfiguration(
                    "secure bus required: missing mTLS env var(s) " + ", ".join(missing)
                )
            cls._assert_files(ca_certs, certfile, keyfile)
            return cls(
                ssl_ca_certs=ca_certs,
                ssl_certfile=certfile,
                ssl_keyfile=keyfile,
                require_mtls=True,
            )

        if scheme != "rediss" and (ca_certs or certfile or keyfile):
            raise InsecureBusConfiguration(
                "Redis TLS env vars require REDIS_URL to use rediss://"
            )
        if (certfile and not keyfile) or (keyfile and not certfile):
            raise InsecureBusConfiguration(
                "REDIS_TLS_CERTFILE and REDIS_TLS_KEYFILE must be configured together"
            )
        if ca_certs or certfile or keyfile:
            cls._assert_files(ca_certs, certfile, keyfile)
        return cls(ssl_ca_certs=ca_certs, ssl_certfile=certfile, ssl_keyfile=keyfile)

    @staticmethod
    def _assert_files(*paths: str | None) -> None:
        missing = [path for path in paths if path and not Path(path).is_file()]
        if missing:
            raise InsecureBusConfiguration(
                "secure bus TLS file(s) not found: " + ", ".join(missing)
            )

    def redis_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {}
        if self.ssl_ca_certs:
            kwargs["ssl_ca_certs"] = self.ssl_ca_certs
            kwargs["ssl_cert_reqs"] = ssl.CERT_REQUIRED
        if self.ssl_certfile:
            kwargs["ssl_certfile"] = self.ssl_certfile
        if self.ssl_keyfile:
            kwargs["ssl_keyfile"] = self.ssl_keyfile
        return kwargs


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

    def __init__(
        self,
        url: str | None = None,
        *,
        security: RedisBusSecurity | None = None,
    ) -> None:
        self._url = url or "redis://localhost:6379/0"
        self._security = security or RedisBusSecurity.from_env(self._url)
        self._redis: object | None = None
        self._pubsubs: list[object] = []

    async def connect(self) -> None:
        from redis.asyncio import from_url  # local import

        self._redis = from_url(
            self._url,
            decode_responses=True,
            **self._security.redis_kwargs(),
        )
        # Force a real round-trip to surface connection errors immediately.
        await cast(Awaitable[Any], self._redis.ping())  # type: ignore[attr-defined]

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


__all__ = (
    "Bus",
    "InMemoryBus",
    "InsecureBusConfiguration",
    "RedisBus",
    "RedisBusSecurity",
    "secure_bus_required",
)
