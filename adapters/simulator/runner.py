"""Simulator-to-SwarmOS projection runner."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from swarm_core.messages import Anomaly, FleetState, MissionProgress, Telemetry

from orchestrator.swarm_orchestrator.bus import Bus
from swarm_os.coordinator import SwarmCoordinator


@dataclass
class SimulatorProjectionRunner:
    """Project existing simulator topics into SwarmState without booting FastAPI."""

    bus: Bus
    coordinator: SwarmCoordinator
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._consume_telemetry()),
            asyncio.create_task(self._consume_fleet()),
            asyncio.create_task(self._consume_anomalies()),
            asyncio.create_task(self._consume_progress()),
        ]

    async def stop(self) -> None:
        import contextlib

        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    async def _consume_telemetry(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:telemetry:*"):
            await self.coordinator.apply_telemetry(Telemetry.model_validate_json(payload))

    async def _consume_fleet(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:fleet:state"):
            await self.coordinator.apply_fleet_state(FleetState.model_validate_json(payload))

    async def _consume_anomalies(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            await self.coordinator.apply_anomaly(Anomaly.model_validate_json(payload))

    async def _consume_progress(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:missions:progress:*"):
            await self.coordinator.apply_mission_progress(
                MissionProgress.model_validate_json(payload)
            )
