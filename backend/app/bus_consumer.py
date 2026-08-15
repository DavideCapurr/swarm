"""Bridge: SWARM OS bus → backend in-memory state → WebSocket broadcast.

Boots one consumer task per topic of interest. Lets the backend serve the
frontend without polling — the dashboard reflects bus events immediately.

Phase 4: every projected frame is also persisted via `get_repository()` so the
Console can recover history after a restart and operators can audit any
command. Persistence is best-effort: a DB hiccup logs and continues, never
takes down the live feed.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyState,
    Event,
    FleetState,
    MissionPhase,
    MissionProgress,
    MissionView,
    Telemetry,
)
from swarm_core.rate_limit import DEFAULT_MAX_HZ, TelemetryRateLimiter
from swarm_core.streams import InvalidStreamURL, StreamDescriptor

from backend.app.db import get_repository
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import get_metrics
from backend.app.state import STATE
from orchestrator.swarm_orchestrator.bus import (
    Bus,
    InMemoryBus,
    InsecureBusConfiguration,
    RedisBus,
    redis_url_from_env,
    secure_bus_required,
)
from swarm_os import COORDINATOR

if TYPE_CHECKING:  # pragma: no cover
    from backend.app.ws.telemetry import WSHub

logger = get_logger("backend.bus")

_TERMINAL_MISSION_PHASES = frozenset({MissionPhase.DONE, MissionPhase.FAILED})


class BusConsumer:
    def __init__(self, hub: WSHub, *, telemetry_rate_limit_hz: float = DEFAULT_MAX_HZ) -> None:
        self._hub = hub
        self._bus: Bus | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._coordinator = COORDINATOR
        self._telemetry_limiter = TelemetryRateLimiter(max_hz=telemetry_rate_limit_hz)
        self._mission_started_at: dict[str, float] = {}
        self._persisted_autonomy_ids: set[str] = set()

    async def start(self) -> None:
        redis_url = redis_url_from_env()
        if redis_url:
            try:
                self._bus = RedisBus(redis_url)
                await self._bus.connect()
                logger.info("backend bus: %s", type(self._bus).__name__)
            except InsecureBusConfiguration:
                logger.exception("backend bus refused insecure Redis configuration")
                raise
            except Exception as e:
                if secure_bus_required():
                    logger.exception("backend Redis unavailable and secure bus is required")
                    raise
                logger.warning("backend redis unavailable (%s) — falling back to InMemoryBus", e)
                self._bus = InMemoryBus()
                await self._bus.connect()
        else:
            if secure_bus_required():
                raise InsecureBusConfiguration(
                    "secure bus required: configure REDIS_URL=rediss://... or "
                    "REDIS_HOST/REDIS_PASSWORD with Redis TLS env vars"
                )
            self._bus = InMemoryBus()
            await self._bus.connect()
            logger.info("backend bus: %s", type(self._bus).__name__)

        try:
            await get_repository().write_session(self._coordinator.state.session)
        except Exception:  # pragma: no cover — defensive
            logger.exception("session persistence failed")

        self._tasks = [
            asyncio.create_task(self._consume_telemetry()),
            asyncio.create_task(self._consume_fleet()),
            asyncio.create_task(self._consume_anomalies()),
            asyncio.create_task(self._consume_progress()),
            asyncio.create_task(self._consume_streams()),
            asyncio.create_task(self._consume_external_events()),
        ]

    async def stop(self) -> None:
        import contextlib

        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if self._bus is not None:
            await self._bus.close()

    @property
    def bus(self) -> Bus:
        if self._bus is None:
            raise RuntimeError("BusConsumer not started")
        return self._bus

    async def _consume_telemetry(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:telemetry:*"):
            try:
                telemetry = Telemetry.model_validate_json(payload)
            except Exception:
                continue
            if not self._telemetry_limiter.should_accept(telemetry.agent_id):
                logger.warning("telemetry over backend cap", agent_id=telemetry.agent_id)
                continue
            STATE.last_telemetry[telemetry.agent_id] = telemetry
            await get_repository().write_telemetry(telemetry)
            for frame in await self._coordinator.apply_telemetry(telemetry):
                await self._hub.broadcast(frame)
            self._refresh_state_gauges()
            await self._persist_frames(frame_events=True)

    async def _consume_fleet(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:fleet:state"):
            try:
                fleet_state = FleetState.model_validate_json(payload)
            except Exception:
                continue
            STATE.fleet[fleet_state.agent_id] = fleet_state
            for frame in await self._coordinator.apply_fleet_state(fleet_state):
                await self._hub.broadcast(frame)
            self._refresh_state_gauges()
            await self._persist_frames(frame_events=True)

    async def _consume_anomalies(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:anomalies"):
            try:
                anomaly = Anomaly.model_validate_json(payload)
            except Exception:
                continue
            STATE.anomalies[anomaly.id] = anomaly
            STATE.add_event("anomaly", json.loads(payload))
            for frame in await self._coordinator.apply_anomaly(anomaly):
                await self._hub.broadcast(frame)
            view = self._coordinator.state.anomalies.get(anomaly.id)
            if view is not None:
                await get_repository().write_anomaly(view)
            self._refresh_state_gauges()
            await self._persist_frames(frame_events=True)

    async def _consume_progress(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:missions:progress:*"):
            try:
                progress = MissionProgress.model_validate_json(payload)
            except Exception:
                continue
            STATE.add_event("progress", json.loads(payload))
            for frame in await self._coordinator.apply_mission_progress(progress):
                await self._hub.broadcast(frame)
            mission = self._coordinator.state.missions.get(progress.mission_id)
            if mission is not None:
                await get_repository().write_mission(mission)
                self._observe_mission_duration(mission)
            await self._persist_frames(frame_events=True)

    def _observe_mission_duration(self, mission: MissionView) -> None:
        if mission.phase in _TERMINAL_MISSION_PHASES:
            start = self._mission_started_at.pop(mission.id, None)
            if start is not None:
                get_metrics().mission_duration_seconds.observe(time.monotonic() - start)
        else:
            self._mission_started_at.setdefault(mission.id, time.monotonic())

    async def _consume_streams(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:streams:*"):
            try:
                descriptor = StreamDescriptor.model_validate_json(payload)
            except (ValueError, InvalidStreamURL):
                logger.warning("dropped malformed stream descriptor from bus: %s", payload[:200])
                continue
            self._coordinator.state.streams[descriptor.agent_id] = descriptor
            await self._hub.broadcast(
                {"kind": "stream", "data": descriptor.model_dump(mode="json")}
            )

    async def _consume_external_events(self) -> None:
        """Validate and bridge trusted subsystem events into the EventFeed."""

        async for _topic, payload in self.bus.subscribe("swarm:events:*"):
            try:
                event = Event.model_validate_json(payload)
            except Exception:
                logger.warning("dropped malformed external event from bus")
                continue
            self._coordinator.state.append_event(event)
            await self._hub.broadcast(
                {"kind": "event", "data": event.model_dump(mode="json")}
            )
            await self._persist_frames(frame_events=True)

    def _refresh_state_gauges(self) -> None:
        state = self._coordinator.state
        metrics = get_metrics()
        units = state.units.values()
        online = sum(1 for unit in units if unit.fsm_state is not AgentState.OFFLINE)
        metrics.units_online.set(online)
        pending = sum(
            1
            for anomaly in state.anomalies.values()
            if anomaly.state not in (AnomalyState.VERIFIED, AnomalyState.DISMISSED)
        )
        metrics.anomalies_pending.set(pending)

    async def _persist_frames(self, *, frame_events: bool) -> None:
        if not get_repository().enabled or not frame_events:
            return
        events = list(self._coordinator.state.events)
        await get_repository().write_events(events[-32:])
        await self._persist_new_autonomy_commands()

    async def _persist_new_autonomy_commands(self) -> None:
        for command in list(self._coordinator.state.commands.values()):
            if command.source != "autonomy":
                continue
            if command.id in self._persisted_autonomy_ids:
                continue
            try:
                await get_repository().write_operator_command(command)
                self._persisted_autonomy_ids.add(command.id)
            except Exception:  # pragma: no cover — defensive
                logger.exception("write_operator_command(autonomy) failed")
