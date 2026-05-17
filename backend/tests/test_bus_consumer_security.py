"""Secure bus gate behavior for backend startup."""

from __future__ import annotations

import pytest

from backend.app.bus_consumer import BusConsumer
from orchestrator.swarm_orchestrator.bus import InsecureBusConfiguration


class _Hub:
    async def broadcast(self, _frame: object) -> None:
        return None


@pytest.mark.asyncio
async def test_bus_consumer_refuses_inmemory_fallback_when_secure_bus_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.delenv("REDIS_URL", raising=False)

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    with pytest.raises(InsecureBusConfiguration, match="REDIS_URL"):
        await consumer.start()


@pytest.mark.asyncio
async def test_bus_consumer_refuses_plaintext_redis_when_secure_bus_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_REQUIRE_SECURE_BUS", "1")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    consumer = BusConsumer(_Hub())  # type: ignore[arg-type]
    with pytest.raises(InsecureBusConfiguration, match="rediss://"):
        await consumer.start()
