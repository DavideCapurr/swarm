"""MAVLink producer.

The backend boots this runner in-process when `SWARM_VENDORS` includes
`mavlink`. The module also keeps a standalone `python -m adapters.mavlink.runner`
entrypoint for bench debugging, but the supported Phase 5 dev/demo path is the
in-process backend lifecycle in `backend.app.fleet`. The runner owns one
`MAVLinkAdapter`, projects its telemetry / fleet-state / mission progress onto
the bus topics, and publishes a `StreamDescriptor` per agent so the Console
knows whether a live video stream is available.

Topics (identical to the simulator runner, so the bus consumer code path is
shared):
  - `swarm:telemetry:<agent_id>`           ← Telemetry JSON
  - `swarm:fleet:state`                     ← FleetState JSON
  - `swarm:missions:progress:<mission_id>`  ← MissionProgress JSON
  - `swarm:streams:<agent_id>`              ← StreamDescriptor JSON

Env knobs:
  - `MAVLINK_CONNECTION`     default `udp:localhost:14540`
  - `MAVLINK_AGENT_ID`       default `mav-001`
  - `MAVLINK_MODEL`          default `px4-x500`
  - `MAVLINK_STREAM_URL`     optional; must be `rtsps://` or `https://`
  - `MAVLINK_RATE_LIMIT_HZ`  default `50`

The runner is intentionally vendor-scoped: it only knows about
`MAVLinkAdapter`. `backend/app/fleet.py` is the registry that picks which
vendor runners to boot from `SWARM_VENDORS`.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import signal
from dataclasses import dataclass, field
from typing import Any

from swarm_core.messages import AgentState, FleetState

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus, RedisBus

logger = logging.getLogger("mavlink.runner")


# ── Runner ─────────────────────────────────────────────────────────────────────


@dataclass
class MAVLinkRunner:
    """Boots one `MAVLinkAdapter` and bridges it onto the SwarmOS bus."""

    adapter: MAVLinkAdapter
    bus: Bus
    fleet_state_hz: float = 2.0
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)
    _running: bool = False

    async def start(self) -> None:
        await self.adapter.connect()
        self._running = True
        self._tasks = [
            asyncio.create_task(self._publish_telemetry()),
            asyncio.create_task(self._publish_fleet_state()),
            asyncio.create_task(self._publish_stream_descriptor()),
        ]
        logger.info("mavlink runner: %s online", self.adapter.agent_id)

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._tasks.clear()
        await self.adapter.disconnect()

    # ── publishers ───────────────────────────────────────────────────────────

    async def _publish_telemetry(self) -> None:
        topic = f"swarm:telemetry:{self.adapter.agent_id}"
        try:
            async for t in self.adapter.stream_telemetry():
                if not self._running:
                    return
                await self.bus.publish(topic, t.model_dump_json())
        except asyncio.CancelledError:
            raise

    async def _publish_fleet_state(self) -> None:
        period = 1.0 / max(self.fleet_state_hz, 0.1)
        try:
            while self._running:
                # Pull current health + last known geo from the adapter; the
                # adapter caches them on every HEARTBEAT / GLOBAL_POSITION_INT.
                health = await self.adapter.health()
                geo = self.adapter._last_position
                if geo is None:
                    await asyncio.sleep(period)
                    continue
                fsm_state = _infer_fsm_state(self.adapter, health.online)
                fs = FleetState(
                    agent_id=self.adapter.agent_id,
                    vendor=self.adapter.vendor,
                    model=self.adapter.model,
                    fsm_state=fsm_state,
                    battery_pct=health.battery_pct,
                    geo=geo,
                    link_quality=health.link_quality,
                )
                await self.bus.publish("swarm:fleet:state", fs.model_dump_json())
                await asyncio.sleep(period)
        except asyncio.CancelledError:
            raise

    async def _publish_stream_descriptor(self) -> None:
        topic = f"swarm:streams:{self.adapter.agent_id}"
        try:
            # Stream URL is configured at boot; publish once per second so
            # the backend can rebroadcast even after a Console reconnect.
            while self._running:
                desc = self.adapter.stream_descriptor()
                await self.bus.publish(topic, desc.model_dump_json())
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise


def _infer_fsm_state(adapter: MAVLinkAdapter, online: bool) -> AgentState:
    """Best-effort FSM mapping from MAVLink state to SwarmOS canon."""
    if not online:
        return AgentState.OFFLINE
    if adapter._last_position is None:
        return AgentState.DOCKED
    alt = adapter._last_position.alt_m
    # Crude but honest: under 1 m AGL = on the dock; otherwise EN_ROUTE.
    # Phase 6's policy engine will replace this with telemetry-state mapping
    # informed by ARMED / IN_AIR flags from EXTENDED_SYS_STATE.
    if alt < 1.0:
        return AgentState.DOCKED
    return AgentState.EN_ROUTE


# ── Bootstrap helpers (used by `backend.app.fleet`) ───────────────────────────


def adapter_from_env(*, agent_id: str | None = None) -> MAVLinkAdapter:
    """Materialize a `MAVLinkAdapter` from env vars."""
    resolved_agent_id: str = agent_id or os.getenv("MAVLINK_AGENT_ID") or "mav-001"
    return MAVLinkAdapter(
        agent_id=resolved_agent_id,
        connection=os.getenv("MAVLINK_CONNECTION", "udp:localhost:14540"),
        model=os.getenv("MAVLINK_MODEL", "px4-x500"),
        stream_url=os.getenv("MAVLINK_STREAM_URL") or None,
        rate_limit_hz=float(os.getenv("MAVLINK_RATE_LIMIT_HZ", "50")),
    )


async def boot_runner(
    bus: Bus,
    registry: AdapterRegistry | None = None,
    *,
    adapter: MAVLinkAdapter | None = None,
) -> MAVLinkRunner:
    """Standard boot path: build adapter from env, register, start runner."""
    adapter = adapter or adapter_from_env()
    if registry is not None:
        registry.register(adapter)
    runner = MAVLinkRunner(adapter=adapter, bus=bus)
    await runner.start()
    return runner


# ── Standalone entrypoint (`python -m adapters.mavlink.runner`) ───────────────


async def _amain() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    bus: Bus
    redis_url = os.getenv("REDIS_URL")
    try:
        bus = RedisBus(redis_url) if redis_url else InMemoryBus()
        await bus.connect()
        logger.info("bus connected: %s", type(bus).__name__)
    except Exception as e:
        logger.warning("redis unavailable (%s) — using InMemoryBus", e)
        bus = InMemoryBus()
        await bus.connect()

    runner = await boot_runner(bus, AdapterRegistry())
    stop = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows
            loop.add_signal_handler(sig, _on_signal)

    logger.info("mavlink runner: idle, waiting for SIGINT/SIGTERM")
    try:
        await stop.wait()
    finally:
        await runner.stop()
        await bus.close()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = (
    "MAVLinkRunner",
    "adapter_from_env",
    "boot_runner",
    "main",
)
