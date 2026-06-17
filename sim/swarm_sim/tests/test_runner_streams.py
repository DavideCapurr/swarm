"""CV-live video sub-step — the sim runner advertises the simulated feed.

`_publish_simulated_streams` publishes a `simulated` `StreamDescriptor` per
drone so the Console viewport shows the synthetic SIM-labelled clip. The sim
has no real camera, so this is the honest source of the demo viewport feed.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import SimpleNamespace

from swarm_core.streams import StreamDescriptor

from orchestrator.swarm_orchestrator.bus import InMemoryBus
from sim.swarm_sim.runner import _publish_simulated_streams


async def test_publish_simulated_streams_advertises_per_unit() -> None:
    bus = InMemoryBus()
    await bus.connect()
    world = SimpleNamespace(
        drones=[SimpleNamespace(agent_id="sim-1"), SimpleNamespace(agent_id="sim-2")]
    )

    received: dict[str, StreamDescriptor] = {}

    async def collect() -> None:
        async for _topic, payload in bus.subscribe("swarm:streams:*"):
            desc = StreamDescriptor.model_validate_json(payload)
            received[desc.agent_id] = desc
            if len(received) >= 2:
                return

    collector = asyncio.create_task(collect())
    # Republishes every 10 ms, so the collector reliably catches a batch even
    # though InMemoryBus does not buffer pre-subscription messages.
    publisher = asyncio.create_task(
        _publish_simulated_streams(world, bus, "/sim-feed/drone-pov.mp4", period_s=0.01)  # type: ignore[arg-type]
    )
    try:
        await asyncio.wait_for(collector, timeout=2.0)
    finally:
        publisher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await publisher
        await bus.close()

    assert set(received) == {"sim-1", "sim-2"}
    for desc in received.values():
        assert desc.simulated is True
        assert desc.available is True
        assert desc.url == "/sim-feed/drone-pov.mp4"
        assert desc.protocol is None
        assert desc.codec == "h264"
