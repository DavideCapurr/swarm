"""Live simulated demo driven only by external world events.

Run alongside the backend/Console and a Redis bus. The recording operator may
publish an alarm with ``scripts/send_alarm.py``, later make configured reserve
capacity available with ``scripts/send_sim_capacity_available.py``, and later
publish a physical executor fault with ``scripts/send_sim_fault.py``. None of
these inputs can name a response, replacement, reinforcement, group, role
reassignment or formation transition.

SwarmOS derives all of those outputs from current state and policy. This runner
also opts into executing SwarmOS disposition retasks in the kinematic simulator,
so formation changes are simulation execution truth rather than frontend
choreography.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from typing import Any

from swarm_core.messages import AgentState, FleetState

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
from sim.swarm_sim.external_events import consume_capacity_availability
from sim.swarm_sim.faults import ExecutorFault
from sim.swarm_sim.runner import _tick_world
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


async def _stream_telemetry_lifecycle(
    adapter: SimulatedAdapter,
    bus: Bus,
) -> None:
    """Keep telemetry alive across reserve activation or simulated link loss."""

    while True:
        if not adapter.connected:
            await asyncio.sleep(0.1)
            continue
        async for telemetry in adapter.stream_telemetry():
            await bus.publish(
                f"swarm:telemetry:{adapter.agent_id}", telemetry.model_dump_json()
            )
        await asyncio.sleep(0.1)


async def _publish_fault_aware_fleet_state(
    world: World,
    registry: AdapterRegistry,
    bus: Bus,
) -> None:
    """Publish simulator fleet truth, including unavailable/failed adapters."""

    while True:
        for drone in world.drones:
            adapter = registry.get(drone.agent_id)
            health = await adapter.health()  # type: ignore[attr-defined]
            state = (
                AgentState.OFFLINE
                if not health.online
                else AgentState.DOCKED
                if drone.is_docked
                else AgentState.LANDING
                if drone._mode == "LANDING"
                else AgentState.ON_STATION
                if drone._mode == "HOVER"
                else AgentState.EN_ROUTE
                if drone._mode == "FLYING"
                else AgentState.TAKEOFF
            )
            frame = FleetState(
                agent_id=drone.agent_id,
                vendor=adapter.vendor,  # type: ignore[attr-defined]
                model=adapter.model,  # type: ignore[attr-defined]
                fsm_state=state,
                battery_pct=drone.battery_pct,
                geo=drone.geo,
            )
            await bus.publish("swarm:fleet:state", frame.model_dump_json())
        await asyncio.sleep(0.5)


async def _consume_external_faults(
    bus: Bus,
    adapters: dict[str, SimulatedAdapter],
) -> None:
    """Apply world faults to physical sim adapters; never decide recovery."""

    async for _topic, payload in bus.subscribe("swarm:sim:faults"):
        try:
            fault = ExecutorFault.model_validate_json(payload)
        except Exception as exc:
            logger.warning("invalid simulator fault payload: %s", exc)
            continue
        adapter = adapters.get(fault.agent_id)
        if adapter is None:
            logger.warning("simulator fault names unknown executor %s", fault.agent_id)
            continue
        adapter.inject_failure(fault.reason)
        logger.info("external simulator fault: %s (%s)", fault.agent_id, fault.reason)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
    )
    fleet_size = max(6, int(os.getenv("SWARM_ALARM_DEMO_FLEET", "12")))
    tick_hz = float(os.getenv("SWARM_ALARM_DEMO_TICK_HZ", "10"))
    patrol_radius_m = float(os.getenv("SWARM_ALARM_DEMO_PATROL_RADIUS_M", "160"))
    reserve_count = int(os.getenv("SWARM_ALARM_DEMO_RESERVE", "1"))
    if reserve_count < 0 or reserve_count >= fleet_size:
        raise ValueError("SWARM_ALARM_DEMO_RESERVE must be within [0, fleet size)")

    alarm_max_team = max(2, int(os.getenv("SWARM_ALARM_MAX_TEAM", "4")))
    initially_online = fleet_size - reserve_count
    default_patrol_floor = max(1, initially_online - (alarm_max_team - 1))
    patrol_floor = int(
        os.getenv("SWARM_ALARM_DEMO_PATROL_MIN", str(default_patrol_floor))
    )
    if not 0 <= patrol_floor <= initially_online:
        raise ValueError(
            "SWARM_ALARM_DEMO_PATROL_MIN must be within initially online capacity"
        )

    world = World.vineyard(n_drones=fleet_size, ignition_after_s=86_400.0)
    registry = AdapterRegistry()
    adapters: list[SimulatedAdapter] = []
    adapters_by_id: dict[str, SimulatedAdapter] = {}
    for index, drone in enumerate(world.drones):
        adapter = SimulatedAdapter(
            agent_id=drone.agent_id,
            drone=drone,
            self_tick=False,
        )
        if index < initially_online:
            await adapter.connect()
        registry.register(adapter)
        adapters.append(adapter)
        adapters_by_id[adapter.agent_id] = adapter
    reserve_adapters = adapters[initially_online:]

    bus = await _connect_bus()
    policy = AlarmResponsePolicy(
        cooperative_threshold=float(
            os.getenv("SWARM_ALARM_COOPERATIVE_THRESHOLD", "0.80")
        ),
        high_confidence_threshold=float(
            os.getenv("SWARM_ALARM_HIGH_THRESHOLD", "0.93")
        ),
        max_team_size=alarm_max_team,
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
        execute_disposition_retask=True,
        alarm_policy=policy,
    )

    logger.info(
        "alarm demo ready: fleet=%d online=%d reserve=%d patrol_min=%d; "
        "external inputs: alarm, capacity-available, optional sim fault",
        fleet_size,
        initially_online,
        reserve_count,
        patrol_floor,
    )

    stop = asyncio.Event()

    def _stop(*_: Any) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _stop)

    tasks = [
        asyncio.create_task(_tick_world(world, tick_hz)),
        asyncio.create_task(_publish_fault_aware_fleet_state(world, registry, bus)),
        asyncio.create_task(_consume_external_faults(bus, adapters_by_id)),
        asyncio.create_task(consume_capacity_availability(bus, reserve_adapters)),
        asyncio.create_task(orchestrator.run()),
        *[
            asyncio.create_task(_stream_telemetry_lifecycle(adapter, bus))
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
