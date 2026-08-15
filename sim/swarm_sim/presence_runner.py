"""Presence-response demo runner.

This runner intentionally reuses the production-shaped simulator plumbing from
``sim.swarm_sim.runner`` but swaps in ``PresenceResponseOrchestrator`` and
registers an honest simulated payload controller for each simulated aircraft.

It is opt-in and does not change the canonical simulator runner or existing
scenario regression behaviour.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path
from typing import Any

from adapters.base import AdapterRegistry
from adapters.payload import PayloadControllerRegistry
from adapters.simulated import SimulatedAdapter
from adapters.simulated.payload import SimulatedPayloadController
from orchestrator.swarm_orchestrator.bus import (
    Bus,
    InMemoryBus,
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
    secure_bus_required,
)
from orchestrator.swarm_orchestrator.presence import PresenceResponseOrchestrator
from sim.swarm_sim.runner import (
    _publish_anomalies,
    _publish_fleet_state,
    _publish_simulated_streams,
    _stream_telemetry_to_bus,
    _tick_world,
)
from sim.swarm_sim.world import World

logger = logging.getLogger("sim.presence_runner")


async def _build_bus() -> Bus:
    redis_url = redis_url_from_env()
    if redis_url:
        try:
            bus: Bus = RedisBus(redis_url)
            await bus.connect()
            logger.info("bus connected: %s", type(bus).__name__)
            return bus
        except InsecureBusConfiguration:
            logger.exception("presence runner refused insecure Redis configuration")
            raise
        except Exception as exc:
            if secure_bus_required():
                logger.exception("redis unavailable and secure bus is required")
                raise
            logger.warning("redis unavailable (%s) — using InMemoryBus", exc)
    elif secure_bus_required():
        raise InsecureBusConfiguration(
            "secure bus required: configure REDIS_URL=rediss://... or "
            "REDIS_HOST/REDIS_PASSWORD with Redis TLS env vars"
        )

    fallback = InMemoryBus()
    await fallback.connect()
    return fallback


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    scenario_path = os.getenv("SIM_SCENARIO")
    if scenario_path:
        from sim.swarm_sim.scenario import load_scenario

        scenario = load_scenario(Path(scenario_path))
        world = scenario.build_world()
        hz = scenario.tick_hz
        n_drones = scenario.fleet.n_drones
        logger.info(
            "loaded scenario %s (%d drones, %d anomalies)",
            scenario.id,
            n_drones,
            len(scenario.anomalies),
        )
        if scenario.autonomy_baseline:
            from swarm_os import SWARM_STATE

            SWARM_STATE.set_autonomy_enabled(True)
            logger.info("autonomy baseline enabled for scenario %s", scenario.id)
    else:
        n_drones = int(os.getenv("SIM_DRONES", "3"))
        hz = float(os.getenv("SIM_TICK_HZ", "10"))
        ignition_after_s = float(os.getenv("SIM_IGNITION_AT_S", "10"))
        world = World.vineyard(n_drones=n_drones, ignition_after_s=ignition_after_s)

    bus = await _build_bus()
    registry = AdapterRegistry()
    payload_registry = PayloadControllerRegistry()
    adapters: list[SimulatedAdapter] = []

    for drone in world.drones:
        adapter = SimulatedAdapter(agent_id=drone.agent_id, drone=drone, self_tick=False)
        await adapter.connect()
        registry.register(adapter)
        payload_registry.register(SimulatedPayloadController(agent_id=drone.agent_id))
        adapters.append(adapter)

    continuous_patrol = os.getenv("SIM_CONTINUOUS_PATROL", "1") != "0"
    patrol_radius_m = float(os.getenv("SIM_PATROL_RADIUS_M", "130"))
    hold_s = float(os.getenv("SWARM_PRESENCE_HOLD_S", "5"))
    min_confidence = float(os.getenv("SWARM_PRESENCE_MIN_CONFIDENCE", "0.75"))
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("SWARM_PRESENCE_MIN_CONFIDENCE must be in [0, 1]")

    orchestrator = PresenceResponseOrchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=continuous_patrol,
        patrol_origin=world.dock,
        patrol_radius_m=patrol_radius_m,
        payload_registry=payload_registry,
        presence_hold_s=max(0.0, hold_s),
        presence_min_confidence=min_confidence,
    )
    logger.info(
        "presence response enabled: confidence>=%.2f hold=%.1fs payload=SIMULATED",
        min_confidence,
        max(0.0, hold_s),
    )

    stop = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _on_signal)

    tasks = [
        asyncio.create_task(_tick_world(world, hz)),
        asyncio.create_task(_publish_anomalies(world, bus)),
        asyncio.create_task(_publish_fleet_state(world, registry, bus)),
        asyncio.create_task(orchestrator.run()),
        *[asyncio.create_task(_stream_telemetry_to_bus(a, bus)) for a in adapters],
    ]

    sim_feed_path = os.getenv("SWARM_SIM_FEED_PATH")
    if sim_feed_path:
        from swarm_core.streams import InvalidStreamURL, validate_sim_feed_path

        try:
            validate_sim_feed_path(sim_feed_path)
        except InvalidStreamURL as exc:
            logger.warning("ignoring SWARM_SIM_FEED_PATH=%r: %s", sim_feed_path, exc)
        else:
            tasks.append(
                asyncio.create_task(_publish_simulated_streams(world, bus, sim_feed_path))
            )

    logger.info("SWARM presence demo running with %d drones — Ctrl+C to stop", n_drones)
    await stop.wait()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for adapter in adapters:
        await adapter.disconnect()
    await bus.close()


if __name__ == "__main__":
    asyncio.run(main())
