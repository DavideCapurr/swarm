"""Bridge: SWARM OS bus → backend in-memory state → WebSocket broadcast.

Boots one consumer task per topic of interest. Lets the backend serve the
frontend without polling — the dashboard reflects bus events immediately.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING

from swarm_core.messages import Anomaly, FleetState, MissionProgress, Telemetry

from backend.app.state import STATE
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus, RedisBus
from swarm_os import COORDINATOR

if TYPE_CHECKING:  # pragma: no cover
    from backend.app.ws.telemetry import WSHub

logger = logging.getLogger("backend.bus")


class BusConsumer:
    def __init__(self, hub: WSHub) -> None:
        self._hub = hub
        self._bus: Bus | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._coordinator = COORDINATOR

    async def start(self) -> None:
        redis_url = os.getenv("REDIS_URL")
        try:
            self._bus = RedisBus(redis_url) if redis_url else InMemoryBus()
            await self._bus.connect()
            logger.info("backend bus: %s", type(self._bus).__name__)
        except Exception as e:
            logger.warning("backend redis unavailable (%s) — falling back to InMemoryBus", e)
            self._bus = InMemoryBus()
            await self._bus.connect()

        self._tasks = [
            asyncio.create_task(self._consume_telemetry()),
            asyncio.create_task(self._consume_fleet()),
            asyncio.create_task(self._consume_anomalies()),
            asyncio.create_task(self._consume_progress()),
        ]

    async def stop(self) -> None:
        import contextlib
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        if self._bus is not None:
            await self._bus.close()

    @property
    def bus(self) -> Bus:
        if self._bus is None:
            raise RuntimeError("BusConsumer not started")
        return self._bus

    # ── consumers ────────────────────────────────────────────────────────────

    # ── Phase 2 cleanup note ──────────────────────────────────────────────────
    # The dual-emit of raw `telemetry`/`fleet`/`anomaly`/`progress` frames was
    # removed in Phase 2 once the Console started reading only the projected
    # Phase 1 frames (`unit`, `dock`, `sector`, `awareness`, `mission`,
    # `anomaly_view`, `event`, `operator`, `session`). Raw payloads still flow
    # into the in-memory `STATE` for legacy REST endpoints (`/fleet`,
    # `/telemetry/latest`, `/anomalies/raw`) used by external smoke tests.

    async def _consume_telemetry(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:telemetry:*"):
            try:
                t = Telemetry.model_validate_json(payload)
            except Exception:
                continue
            STATE.last_telemetry[t.agent_id] = t
            for frame in await self._coordinator.apply_telemetry(t):
                await self._hub.broadcast(frame)

    async def _consume_fleet(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:fleet:state"):
            try:
                fs = FleetState.model_validate_json(payload)
            except Exception:
                continue
            STATE.fleet[fs.agent_id] = fs
            for frame in await self._coordinator.apply_fleet_state(fs):
                await self._hub.broadcast(frame)

    async def _consume_anomalies(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                a = Anomaly.model_validate_json(payload)
            except Exception:
                continue
            STATE.anomalies[a.id] = a
            STATE.add_event("anomaly", json.loads(payload))
            for frame in await self._coordinator.apply_anomaly(a):
                await self._hub.broadcast(frame)

    async def _consume_progress(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:missions:progress:*"):
            try:
                progress = MissionProgress.model_validate_json(payload)
            except Exception:
                continue
            STATE.add_event("progress", json.loads(payload))
            for frame in await self._coordinator.apply_mission_progress(progress):
                await self._hub.broadcast(frame)
