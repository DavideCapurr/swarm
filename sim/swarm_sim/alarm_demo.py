"""Live simulated demo where the operator supplies only an alarm.

Run alongside the existing backend/Console and a Redis bus, then inject an
alarm with ``scripts/send_alarm.py``.  This runner does not schedule response
aircraft, group ids, reinforcement, or formation transitions.

Initial world state:

* a fleet performs continuous moving patrol;
* the patrol is explicitly preemptible down to a configured minimum;
* no anomaly is emitted automatically.

External input:

* an ``Anomaly`` published on ``swarm:anomalies``.

SwarmOS then derives demand and chooses idle/preemptible capacity. With the
default high-confidence policy (desired strength four) and patrol floor
``fleet_size - 3``, the first group may form at 3/4 strength. The normal patrol
and reinforcement loops continue running; when capacity naturally returns,
SwarmOS may create a second group without a scenario command naming it.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import Any

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.alarm_driven import (
    AlarmDrivenExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus import (
    Bus,
    InMemoryBus,
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
    secure_bus_required,
)
from sim.swarm_sim.runner import (
    _publish_fleet_state,
    _stream_telemetry_to_bus,
    _tick_world,
)
from sim.swarm_sim.world import World

logger = logging.getLogger("sim.alarm_demo")


async def _connect_bus() -> Bus:
    redis_url = redis_url_from_env()
    if redis_url:
        try:
            bus: Bus = RedisBus(redis_url)
            await bus.connect()
            return bus
        except InsecureBusConfiguration:
            raise
        except Exception:
            if secure_bus_required():
                raise
            logger.exception("Redis unavailable; using in-process bus")
    if secure_bus_required():
        raise InsecureBusConfiguration(
            "secure bus required: configure Redis before running the demo"
        )
    bus = InMemoryBus()
    await bus.connect()
    return bus


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    fleet_size = max(6, int(os.getenv("SWARM_ALARM_DEMO_FLEET", "12")))
    tick_hz = float(os.getenv("SWARM_ALARM_DEMO_TICK_HZ", "10"))
    patrol_radius_m = float(os.getenv("SWARM_ALARM_DEMO_PATROL_RADIUS_M", "160"))
    patrol_floor = int(
        os.getenv("SWARM_ALARM_DEMO_PATROL_MIN", str(max(1, fleet_size - 3)))
    )
    if not 0 <= patrol_floor <= fleet_size:
        raise ValueError("SWARM_ALARM_DEMO_PATROL_MIN must be within fleet size")

    # Perception is intentionally not run: the person recording the demo is the
    # source of the external alarm via scripts/send_alarm.py.
    world = World.vineyard(n_drones=fleet_size, ignition_after_s=86_400.0)
    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    for drone in world.drones:
        adapter = SimulatedAdapter(
            agent_id=drone.agent_id,
            drone=drone,
            self_tick=False,
        )
        await adapter.connect()
        registry.register(adapter)
        adapters.append(adapter)

    bus = await _connect_bus()
    policy = AlarmResponsePolicy(
        cooperative_threshold=float(
            os.getenv("SWARM_ALARM_COOPERATIVE_THRESHOLD", "0.80")
        ),
        high_confidence_threshold=float(
            os.getenv("SWARM_ALARM_HIGH_THRESHOLD", "0.93")
        ),
        max_team_size=max(2, int(os.getenv("SWARM_ALARM_MAX_TEAM", "4"))),
        cooperative_hover_s=float(os.getenv("SWARM_ALARM_HOVER_S", "18")),
    )
    orchestrator = AlarmDrivenExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=True,
        patrol_origin=world.dock,
        patrol_radius_m=patrol_radius_m,
        patrol_period_s=float(os.getenv("SWARM_ALARM_PATROL_REVIEW_S", "5")),
        continuous_patrol_min_capacity=patrol_floor,
        continuous_patrol_preemptible=True,
        reinforcement_review_period_s=float(
            os.getenv("SWARM_ALARM_RECONCILE_S", "0.5")
        ),
        max_reinforcements_per_objective=2,
        alarm_policy=policy,
    )

    logger.info(
        "alarm demo ready: fleet=%d patrol_min=%d; publish an alarm to swarm:anomalies",
        fleet_size,
        patrol_floor,
    )

    stop = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    tasks = [
        asyncio.create_task(_tick_world(world, tick_hz)),
        asyncio.create_task(_publish_fleet_state(world, registry, bus)),
        asyncio.create_task(orchestrator.run()),
        *[
            asyncio.create_task(_stream_telemetry_to_bus(adapter, bus))
            for adapter in adapters
        ],
    ]

    try:
        await stop.wait()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for adapter in adapters:
            await adapter.disconnect()
        await bus.close()


if __name__ == "__main__":
    asyncio.run(main())
