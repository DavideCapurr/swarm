"""Lifecycle bridge from backend-owned adapters to the vendor-neutral orchestrator.

The simulator already owns its own orchestrator in ``sim.swarm_sim.runner``.
For a MAVLink-only backend, however, the adapters are booted in-process by
``FleetManager`` and previously had no orchestrator consuming anomalies and
calling ``execute_mission`` on them.

This module closes that gap without enabling ambiguous mixed-fleet semantics.
``simulator,mavlink`` remains observation-only for the backend MAVLink side
until one unified routing policy owns both registries.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from backend.app.fleet import FleetManager
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator

logger = logging.getLogger("backend.mission_runtime")


class MissionRuntimeError(RuntimeError):
    """Raised when a requested mission runtime cannot become ready."""


def should_run_backend_orchestrator(vendors: tuple[str, ...]) -> bool:
    """Only a MAVLink-only backend has unambiguous orchestrator ownership."""

    return vendors == ("mavlink",)


@dataclass
class MissionRuntime:
    fleet: FleetManager
    fleet_ready_timeout_s: float = 8.0
    orchestrator: BusFleetOrchestrator | None = None
    _task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if not should_run_backend_orchestrator(self.fleet.vendors):
            if "mavlink" in self.fleet.vendors:
                logger.warning(
                    "backend orchestrator disabled for mixed vendors=%s; "
                    "simulator owns its own orchestrator",
                    self.fleet.vendors,
                )
            return
        if self._task is not None:
            raise MissionRuntimeError("mission runtime already started")

        orchestrator = BusFleetOrchestrator(
            bus=self.fleet.bus,
            registry=self.fleet.registry,
            continuous_patrol=False,
        )
        task = asyncio.create_task(orchestrator.run())
        self.orchestrator = orchestrator
        self._task = task
        try:
            await orchestrator.wait_for_registered_fleet(
                timeout_s=self.fleet_ready_timeout_s
            )
        except Exception as exc:
            await self.stop()
            raise MissionRuntimeError(
                "MAVLink mission runtime did not receive fresh fleet state"
            ) from exc

        logger.info(
            "backend orchestrator ready for %d MAVLink adapter(s)",
            len(self.fleet.registry),
        )

    async def stop(self) -> None:
        task = self._task
        self._task = None
        self.orchestrator = None
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


__all__ = (
    "MissionRuntime",
    "MissionRuntimeError",
    "should_run_backend_orchestrator",
)
