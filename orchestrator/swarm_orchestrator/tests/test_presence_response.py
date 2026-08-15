from __future__ import annotations

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
from orchestrator.swarm_orchestrator.presence import PresenceResponseOrchestrator


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
    async def execute_mission(self, mission: Any) -> AsyncIterator[MissionProgress]:
        yield MissionProgress(mission_id=mission.id, phase="ON_STATION", progress_pct=90.0)
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


@pytest.mark.asyncio
async def test_verified_presence_runs_payload_sequence_before_mission_finishes() -> None:
    bus = RecordingBus()
    payload_registry = PayloadControllerRegistry()
    payload = RecordingPayloadController("unit-001")
    payload_registry.register(payload)
    orchestrator = PresenceResponseOrchestrator(
        bus=bus,  # type: ignore[arg-type]
        registry=AdapterRegistry(),
        payload_registry=payload_registry,
        presence_hold_s=0.0,
    )
    mission = VERIFY(geo=Geo(lat=45.0, lon=10.0), hover_s=0.0)
    orchestrator._mission_anomalies[mission.id] = Anomaly(
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0, lon=10.0),
        confidence=0.94,
    )

    await orchestrator._run_mission(
        "unit-001", MissionAdapter(), mission, is_verify=True
    )

    assert payload.actions == [
        PayloadActionKind.LIGHT_ON,
        PayloadActionKind.PLAY_MESSAGE,
        PayloadActionKind.STOP_MESSAGE,
        PayloadActionKind.LIGHT_OFF,
    ]
    assert any(topic == "swarm:events:payload" for topic, _ in bus.published)
    progress_topics = [topic for topic, _ in bus.published if topic.startswith("swarm:missions:progress:")]
    assert len(progress_topics) == 2


@pytest.mark.asyncio
async def test_low_confidence_presence_does_not_activate_payload() -> None:
    bus = RecordingBus()
    payload_registry = PayloadControllerRegistry()
    payload = RecordingPayloadController("unit-001")
    payload_registry.register(payload)
    orchestrator = PresenceResponseOrchestrator(
        bus=bus,  # type: ignore[arg-type]
        registry=AdapterRegistry(),
        payload_registry=payload_registry,
        presence_min_confidence=0.75,
        presence_hold_s=0.0,
    )
    mission = VERIFY(geo=Geo(lat=45.0, lon=10.0), hover_s=0.0)
    orchestrator._mission_anomalies[mission.id] = Anomaly(
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0, lon=10.0),
        confidence=0.60,
    )

    await orchestrator._run_mission(
        "unit-001", MissionAdapter(), mission, is_verify=True
    )

    assert payload.actions == []
    assert not any(topic == "swarm:events:payload" for topic, _ in bus.published)
