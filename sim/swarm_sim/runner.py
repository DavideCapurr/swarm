"""Sim runner — wires the world + simulated adapters + orchestrator + bus.

Run: `python -m sim.swarm_sim.runner`

This is what `make demo` boots. It does NOT require Postgres or a frontend — those
are layered on top. With only this running you can `redis-cli SUBSCRIBE 'swarm:*'`
and watch the full event stream.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from pathlib import Path
from typing import Any

from swarm_core.messages import Anomaly, FleetState

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.bus import (
    Bus,
    InMemoryBus,
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
    secure_bus_required,
)
from orchestrator.swarm_orchestrator.service import Orchestrator
from sim.swarm_sim.world import World

logger = logging.getLogger("sim.runner")


async def _stream_telemetry_to_bus(adapter: SimulatedAdapter, bus: Bus) -> None:
    async for t in adapter.stream_telemetry():
        await bus.publish(f"swarm:telemetry:{adapter.agent_id}", t.model_dump_json())


async def _publish_anomalies(world: World, bus: Bus) -> None:
    """Bridge perception anomalies onto the bus."""

    if not world.perception:
        return

    # Strong refs to fire-and-forget publish tasks.
    pending: set[asyncio.Task[None]] = set()

    def _on_anomaly(a: Anomaly) -> None:
        task = asyncio.create_task(bus.publish("swarm:anomalies", a.model_dump_json()))
        pending.add(task)
        task.add_done_callback(pending.discard)
        logger.info("anomaly: %s @ (%.5f, %.5f) c=%.2f", a.kind.value, a.geo.lat, a.geo.lon, a.confidence)

    world.perception.on_anomaly = _on_anomaly
    await world.perception.run()


async def _publish_simulated_streams(
    world: World, bus: Bus, sim_feed_path: str, *, period_s: float = 5.0
) -> None:
    """Advertise the synthetic SIM-labelled drone-POV clip per unit.

    The sim has no real camera, so for the demo viewport we publish a
    `simulated` `StreamDescriptor` (CV-live video sub-step) for every drone.
    The Console renders the bundled `/sim-feed/…` clip stamped `SIMULATED FEED`
    instead of the offline placard. Republished periodically so a Console that
    connects mid-run still receives it. Off unless `SWARM_SIM_FEED_PATH` is set
    — without it the Console keeps the honest VIEWPORT PENDING placard.
    """
    from swarm_core.streams import StreamDescriptor

    while True:
        for d in world.drones:
            desc = StreamDescriptor.simulated_feed(
                d.agent_id, sim_feed_path, codec="h264"
            )
            await bus.publish(f"swarm:streams:{d.agent_id}", desc.model_dump_json())
        await asyncio.sleep(period_s)


async def _publish_fleet_state(world: World, registry: AdapterRegistry, bus: Bus) -> None:
    """Aggregate drone state at 2 Hz and publish on /fleet/state."""
    from swarm_core.messages import AgentState

    while True:
        for d in world.drones:
            adapter = registry.get(d.agent_id)
            state = (
                AgentState.DOCKED if d.is_docked
                else AgentState.LANDING if d._mode == "LANDING"
                else AgentState.ON_STATION if d._mode == "HOVER"
                else AgentState.EN_ROUTE if d._mode == "FLYING"
                else AgentState.TAKEOFF
            )
            fs = FleetState(
                agent_id=d.agent_id,
                vendor=adapter.vendor,
                model=adapter.model,
                fsm_state=state,
                battery_pct=d.battery_pct,
                geo=d.geo,
            )
            await bus.publish("swarm:fleet:state", fs.model_dump_json())
        await asyncio.sleep(0.5)


async def _tick_world(world: World, hz: float) -> None:
    dt = 1.0 / hz
    while True:
        world.step(dt)
        await asyncio.sleep(dt)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

    scenario_path = os.getenv("SIM_SCENARIO")
    if scenario_path:
        from sim.swarm_sim.scenario import load_scenario

        scenario = load_scenario(Path(scenario_path))
        world = scenario.build_world()
        hz = scenario.tick_hz
        n_drones = scenario.fleet.n_drones
        logger.info("loaded scenario %s (%d drones, %d anomalies)",
                    scenario.id, n_drones, len(scenario.anomalies))
        # Phase 7.B — flip the in-process autonomy gate when the scenario
        # opts in. The backend process owns the COORDINATOR + state; this
        # stamp is only meaningful when the runner + backend share a
        # process (e.g. integration tests). For `make demo` the backend
        # reads `SWARM_AUTONOMY_BASELINE` from the env at boot.
        if scenario.autonomy_baseline:
            from swarm_os import SWARM_STATE

            SWARM_STATE.set_autonomy_enabled(True)
            logger.info("autonomy baseline enabled for scenario %s", scenario.id)
    else:
        n_drones = int(os.getenv("SIM_DRONES", "3"))
        hz = float(os.getenv("SIM_TICK_HZ", "10"))
        ignition_after_s = float(os.getenv("SIM_IGNITION_AT_S", "10"))
        world = World.vineyard(n_drones=n_drones, ignition_after_s=ignition_after_s)
    registry = AdapterRegistry()

    bus: Bus
    redis_url = redis_url_from_env()
    if redis_url:
        try:
            bus = RedisBus(redis_url)
            await bus.connect()
            logger.info("bus connected: %s", type(bus).__name__)
        except InsecureBusConfiguration:
            logger.exception("sim runner refused insecure Redis configuration")
            raise
        except Exception as e:
            if secure_bus_required():
                logger.exception("redis unavailable and secure bus is required")
                raise
            logger.warning("redis unavailable (%s) — using InMemoryBus", e)
            bus = InMemoryBus()
            await bus.connect()
    else:
        if secure_bus_required():
            raise InsecureBusConfiguration(
                "secure bus required: configure REDIS_URL=rediss://... or "
                "REDIS_HOST/REDIS_PASSWORD with Redis TLS env vars"
            )
        bus = InMemoryBus()
        await bus.connect()

    adapters: list[SimulatedAdapter] = []
    for d in world.drones:
        # `self_tick=False` because the world ticks all drones atomically below.
        a = SimulatedAdapter(agent_id=d.agent_id, drone=d, self_tick=False)
        await a.connect()
        registry.register(a)
        adapters.append(a)

    # Continuous patrol keeps every unit sweeping its own wedge of the
    # territory so the Console map is alive and Unit 003 doesn't sit docked.
    # On by default for the demo; SIM_CONTINUOUS_PATROL=0 restores the
    # single-shot (anomaly-only) behaviour.
    continuous_patrol = os.getenv("SIM_CONTINUOUS_PATROL", "1") != "0"
    patrol_radius_m = float(os.getenv("SIM_PATROL_RADIUS_M", "130"))
    orchestrator = Orchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=continuous_patrol,
        patrol_origin=world.dock,
        patrol_radius_m=patrol_radius_m,
    )
    if continuous_patrol:
        logger.info("continuous patrol enabled (radius %.0f m)", patrol_radius_m)

    stop = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        stop.set()

    import contextlib

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, _on_signal)

    tasks = [
        asyncio.create_task(_tick_world(world, hz)),
        asyncio.create_task(_publish_anomalies(world, bus)),
        asyncio.create_task(_publish_fleet_state(world, registry, bus)),
        asyncio.create_task(orchestrator.run()),
        *[asyncio.create_task(_stream_telemetry_to_bus(a, bus)) for a in adapters],
    ]

    # CV-live video sub-step: optionally advertise the synthetic SIM-labelled
    # drone-POV clip on the viewport. Validated up front so a misconfigured
    # path fails loud (a warning) rather than silently dropping every tick.
    sim_feed_path = os.getenv("SWARM_SIM_FEED_PATH")
    if sim_feed_path:
        from swarm_core.streams import InvalidStreamURL, validate_sim_feed_path

        try:
            validate_sim_feed_path(sim_feed_path)
        except InvalidStreamURL as e:
            logger.warning("ignoring SWARM_SIM_FEED_PATH=%r: %s", sim_feed_path, e)
        else:
            tasks.append(
                asyncio.create_task(_publish_simulated_streams(world, bus, sim_feed_path))
            )
            logger.info("simulated viewport feed advertised for all units: %s", sim_feed_path)

    logger.info("SWARM OS sim running with %d drones — Ctrl+C to stop", n_drones)
    await stop.wait()
    logger.info("shutting down")
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for a in adapters:
        await a.disconnect()
    await bus.close()


if __name__ == "__main__":
    asyncio.run(main())
