from __future__ import annotations

import asyncio

import pytest

from orchestrator.swarm_orchestrator.bus import InMemoryBus


@pytest.mark.asyncio
async def test_inmemory_pub_sub_round_trip() -> None:
    bus = InMemoryBus()
    await bus.connect()
    received: list[tuple[str, str]] = []

    async def consume() -> None:
        async for topic, payload in bus.subscribe("swarm:test:*"):
            received.append((topic, payload))
            if len(received) >= 2:
                return

    consumer = asyncio.create_task(consume())
    # Allow the subscription to register before publishing.
    await asyncio.sleep(0.01)
    await bus.publish("swarm:test:a", "1")
    await bus.publish("swarm:test:b", "2")
    await asyncio.wait_for(consumer, timeout=1.0)
    await bus.close()

    assert received == [("swarm:test:a", "1"), ("swarm:test:b", "2")]


@pytest.mark.asyncio
async def test_inmemory_does_not_deliver_unmatched_topics() -> None:
    bus = InMemoryBus()
    await bus.connect()
    received: list[tuple[str, str]] = []

    async def consume() -> None:
        async for topic, payload in bus.subscribe("swarm:foo:*"):
            received.append((topic, payload))

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await bus.publish("swarm:bar:1", "should not be seen")
    await asyncio.sleep(0.05)
    await bus.close()
    consumer.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consumer

    assert received == []
