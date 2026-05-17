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
import os
import time
from typing import TYPE_CHECKING

from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyState,
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
    secure_bus_required,
)
from swarm_os import COORDINATOR

if TYPE_CHECKING:  # pragma: no cover
    from backend.app.ws.telemetry import WSHub

logger = get_logger("backend.bus")

# Mission phases that close out a duration sample. Anything else is
# treated as in-flight and only records the start time.
_TERMINAL_MISSION_PHASES = frozenset({MissionPhase.DONE, MissionPhase.FAILED})


class BusConsumer:
    def __init__(self, hub: WSHub, *, telemetry_rate_limit_hz: float = DEFAULT_MAX_HZ) -> None:
        self._hub = hub
        self._bus: Bus | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._coordinator = COORDINATOR
        self._telemetry_limiter = TelemetryRateLimiter(max_hz=telemetry_rate_limit_hz)
        # Monotonic start time per mission_id. Populated on first non-terminal
        # sighting, popped on terminal sighting to feed the histogram.
        self._mission_started_at: dict[str, float] = {}

    async def start(self) -> None:
        redis_url = os.getenv("REDIS_URL")
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
                    "secure bus required: REDIS_URL must be set and use rediss://"
                )
            self._bus = InMemoryBus()
            await self._bus.connect()
            logger.info("backend bus: %s", type(self._bus).__name__)

        # Phase 4: persist session bootstrap row so /events?from=...&to=...
        # joins against a known session for audit.
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
            if not self._telemetry_limiter.should_accept(t.agent_id):
                logger.warning("telemetry over backend cap", agent_id=t.agent_id)
                continue
            STATE.last_telemetry[t.agent_id] = t
            await get_repository().write_telemetry(t)
            for frame in await self._coordinator.apply_telemetry(t):
                await self._hub.broadcast(frame)
            self._refresh_state_gauges()
            await self._persist_frames(frame_events=True)

    async def _consume_fleet(self) -> None:
        async for _topic, payload in self.bus.subscribe("swarm:fleet:state"):
            try:
                fs = FleetState.model_validate_json(payload)
            except Exception:
                continue
            STATE.fleet[fs.agent_id] = fs
            for frame in await self._coordinator.apply_fleet_state(fs):
                await self._hub.broadcast(frame)
            self._refresh_state_gauges()
            await self._persist_frames(frame_events=True)

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
            # Persist the projected anomaly view, plus any events the
            # coordinator generated as a side effect.
            view = self._coordinator.state.anomalies.get(a.id)
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
        """Feed the ``swarm_mission_duration_seconds`` histogram.

        Records a monotonic start time on the first non-terminal sighting
        of a mission and observes the elapsed seconds when the same
        mission next appears in a terminal phase. Missions first seen
        already terminal contribute no sample (we have no start to
        subtract from) — better an empty bucket than a fabricated one.
        """

        if mission.phase in _TERMINAL_MISSION_PHASES:
            start = self._mission_started_at.pop(mission.id, None)
            if start is not None:
                elapsed = time.monotonic() - start
                get_metrics().mission_duration_seconds.observe(elapsed)
        else:
            self._mission_started_at.setdefault(mission.id, time.monotonic())

    async def _consume_streams(self) -> None:
        """Re-broadcast `StreamDescriptor` frames published by adapter runners.

        Phase 5 separation of concerns: the adapter publishes the URL it
        knows; the backend re-validates against the allowlist (defense in
        depth) and forwards to every WS client. The Console renders a real
        `<video>` element when `available=True`, otherwise keeps the
        "VIEWPORT PENDING / STREAM OFFLINE" placard.
        """
        async for _topic, payload in self.bus.subscribe("swarm:streams:*"):
            try:
                descriptor = StreamDescriptor.model_validate_json(payload)
            except (ValueError, InvalidStreamURL):
                # An adapter that misbehaves (or a malicious one) gets its
                # frame dropped at the backend, not re-broadcast. We log
                # the event so it surfaces in audit.
                logger.warning("dropped malformed stream descriptor from bus: %s", payload[:200])
                continue
            self._coordinator.state.streams[descriptor.agent_id] = descriptor
            await self._hub.broadcast(
                {"kind": "stream", "data": descriptor.model_dump(mode="json")}
            )

    # ── Metrics helpers ──────────────────────────────────────────────────────

    def _refresh_state_gauges(self) -> None:
        """Re-sample the gauges that derive from coordinator state.

        Cheap (two filtered counts) so we can do it on every relevant
        bus event. Counters live elsewhere — this only refreshes gauges
        that snapshot "current world".
        """
        state = self._coordinator.state
        metrics = get_metrics()
        # Units online: anything not currently OFFLINE. DOCKED units are
        # still "online" (battery-charging but reachable on the link).
        units = state.units.values()
        online = sum(1 for u in units if u.fsm_state is not AgentState.OFFLINE)
        metrics.units_online.set(online)
        # Pending anomalies: anything not yet verified or dismissed.
        pending = sum(
            1
            for a in state.anomalies.values()
            if a.state not in (AnomalyState.VERIFIED, AnomalyState.DISMISSED)
        )
        metrics.anomalies_pending.set(pending)

    # ── Persistence helpers ──────────────────────────────────────────────────

    async def _persist_frames(self, *, frame_events: bool) -> None:
        """Persist any new events the coordinator just appended.

        Reading directly from `state.events` (a bounded deque) means we may
        re-write events the DB already has — the upsert on primary key makes
        this safe and the constant-factor cost is small relative to bus rate.
        """
        if not get_repository().enabled:
            return
        if not frame_events:
            return
        events = list(self._coordinator.state.events)
        # Only persist the tail to bound write rate — older events are already
        # in the DB from earlier ticks.
        await get_repository().write_events(events[-32:])
