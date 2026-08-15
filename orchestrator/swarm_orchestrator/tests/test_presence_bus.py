from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import pytest
from swarm_core.messages import Anomaly, AnomalyKind, Geo, MissionProgress
from swarm_core.missions import VERIFY
from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadActionStatus,
    PayloadExecutionMode,
)

from adapters.base import AdapterRegistry
from adapters.payload import PayloadControllerRegistry
from orchestrator.swarm_orchestrator.presence_bus import (
    PresenceResponseBusFleetOrchestrator,
)


class RecordingBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    async def subscribe(self, _topic_pattern: str) -> AsyncIterator[tuple[str, str]]:
        if False:
            yield "", ""


class MissionAdapter:
    """Reach-aware contract: EN_ROUTE, verified ON_STATION, then DONE."""

    async def execute_mission(self, mission: Any) -> AsyncIterator[MissionProgress]:
        yield MissionProgress(mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0)
        yield MissionProgress(mission_id=mission.id, phase="ON_STATION", progress_pct=95.0)
        yield MissionProgress(mission_id=mission.id, phase="DONE", progress_pct=100.0)


class RecordingPayloadController:
    capabilities = frozenset(PayloadActionKind)

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.actions: list[PayloadActionKind] = []
        self.light_on = False
        self.speaker_active = False

    async def execute(self, action: PayloadAction) -> PayloadActionResult:
        self.actions.append(action.kind)
        if action.kind is PayloadActionKind.LIGHT_ON:
            self.light_on = True
        elif action.kind is PayloadActionKind.LIGHT_OFF:
            self.light_on = False
        elif action.kind is PayloadActionKind.PLAY_MESSAGE:
            self.speaker_active = True
        elif action.kind is PayloadActionKind.STOP_MESSAGE:
            self.speaker_active = False
        return PayloadActionResult(
            action_id=action.id,
            agent_id=self.agent_id,
            kind=action.kind,
            status=PayloadActionStatus.SIMULATED,
            execution_mode=PayloadExecutionMode.SIMULATED,
            light_on=self.light_on,
            speaker_active=self.speaker_active,
            message=action.message if self.speaker_active else None,
        )


def _build_orchestrator(
    *,
    bus: RecordingBus,
    payload: RecordingPayloadController,
    hold_s: float,
    min_confidence: float = 0.85,
) -> PresenceResponseBusFleetOrchestrator:
    payload_registry = PayloadControllerRegistry()
    payload_registry.register(payload)
    return PresenceResponseBusFleetOrchestrator(
        bus=bus,  # type: ignore[arg-type]
        registry=AdapterRegistry(),
        payload_registry=payload_registry,
        presence_min_confidence=min_confidence,
        presence_hold_s=hold_s,
    )


def _bind_presence(
    orchestrator: PresenceResponseBusFleetOrchestrator,
    *,
    confidence: float,
    kind: AnomalyKind = AnomalyKind.INTRUSION,
) -> Any:
    mission = VERIFY(geo=Geo(lat=45.0, lon=10.0), hover_s=0.0)
    orchestrator._mission_anomalies[mission.id] = Anomaly(
        kind=kind,
        geo=Geo(lat=45.0, lon=10.0),
        confidence=confidence,
    )
    return mission


@pytest.mark.asyncio
async def test_verified_intrusion_runs_response_after_on_station() -> None:
    bus = RecordingBus()
    payload = RecordingPayloadController("unit-001")
    orchestrator = _build_orchestrator(bus=bus, payload=payload, hold_s=0.0)
    mission = _bind_presence(orchestrator, confidence=0.94)

    await orchestrator._run_mission(
        "unit-001",
        MissionAdapter(),
        mission,
        is_verify=True,
    )

    assert payload.actions == [
        PayloadActionKind.LIGHT_ON,
        PayloadActionKind.PLAY_MESSAGE,
        PayloadActionKind.STOP_MESSAGE,
        PayloadActionKind.LIGHT_OFF,
    ]
    progress_topics = [
        topic
        for topic, _ in bus.published
        if topic.startswith("swarm:missions:progress:")
    ]
    assert len(progress_topics) == 3
    payload_indexes = [
        index
        for index, (topic, _) in enumerate(bus.published)
        if topic == "swarm:events:payload"
    ]
    on_station_index = next(
        index
        for index, (topic, payload_json) in enumerate(bus.published)
        if topic.startswith("swarm:missions:progress:") and '"phase":"ON_STATION"' in payload_json
    )
    assert payload_indexes
    assert on_station_index < payload_indexes[0]


@pytest.mark.asyncio
async def test_low_confidence_or_non_intrusion_does_not_activate_payload() -> None:
    for confidence, kind in [
        (0.60, AnomalyKind.INTRUSION),
        (0.99, AnomalyKind.HEAT_SPOT),
    ]:
        bus = RecordingBus()
        payload = RecordingPayloadController("unit-001")
        orchestrator = _build_orchestrator(bus=bus, payload=payload, hold_s=0.0)
        mission = _bind_presence(
            orchestrator,
            confidence=confidence,
            kind=kind,
        )
        await orchestrator._run_mission(
            "unit-001",
            MissionAdapter(),
            mission,
            is_verify=True,
        )
        assert payload.actions == []


@pytest.mark.asyncio
async def test_cancellation_during_hold_still_cleans_up_payload() -> None:
    bus = RecordingBus()
    payload = RecordingPayloadController("unit-001")
    orchestrator = _build_orchestrator(bus=bus, payload=payload, hold_s=30.0)
    mission = _bind_presence(orchestrator, confidence=0.94)

    task = asyncio.create_task(
        orchestrator._run_mission(
            "unit-001",
            MissionAdapter(),
            mission,
            is_verify=True,
        )
    )
    for _ in range(100):
        if payload.actions[:2] == [
            PayloadActionKind.LIGHT_ON,
            PayloadActionKind.PLAY_MESSAGE,
        ]:
            break
        await asyncio.sleep(0.01)

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert payload.actions[-2:] == [
        PayloadActionKind.STOP_MESSAGE,
        PayloadActionKind.LIGHT_OFF,
    ]
    assert payload.light_on is False
    assert payload.speaker_active is False
