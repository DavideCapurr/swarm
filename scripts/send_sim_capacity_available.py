"""Publish the simulation-only fact that reserve capacity became available.

The event has no executor IDs and cannot request reinforcement, dispatch,
replacement, role changes or geometry. It changes only the simulated world's
physical availability; the running SwarmOS reconciliation loop decides whether
anything should happen in response.
"""

from __future__ import annotations

import asyncio

from orchestrator.swarm_orchestrator.bus import (
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
)
from sim.swarm_sim.external_events import CAPACITY_AVAILABLE_TOPIC, CapacityAvailable


async def _main() -> None:
    redis_url = redis_url_from_env()
    if not redis_url:
        raise InsecureBusConfiguration(
            "send_sim_capacity_available requires the shared Redis simulator bus"
        )
    bus = RedisBus(redis_url)
    await bus.connect()
    try:
        event = CapacityAvailable()
        await bus.publish(CAPACITY_AVAILABLE_TOPIC, event.model_dump_json())
        print("published simulator world fact: reserve capacity available")
    finally:
        await bus.close()


if __name__ == "__main__":
    asyncio.run(_main())
