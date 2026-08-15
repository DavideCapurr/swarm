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
from orchestrator.swarm_orchestrator.presence_bus import (
    PRIMARY_PRESENCE_ROLE,
    PresenceResponseBusFleetOrchestrator,
)


class RecordingBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    async def subscribe(self, _topic: str) -> AsyncIterator[tuple[str, str]]:
        if False:
            yield "", ""


class MissionAdapter:
    async def execute_mission(self, mission: Any) -> AsyncIterator[MissionProgress]:
        yield MissionProgress(
            mission_id=mission.id, phase="EN_ROUTE", progress_pct=5.0
        )
        yield MissionProgress(
            mission_id=mission.id, phase="ON_STATION", progress_pct=95.0
        )
        yield MissionProgress(
            mission_id=mission.id, phase="DONE", progress_pct=100.0
        )


class RecordingPayloadController:
    capabilities = frozenset(PayloadActionKind)

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.actions: list[PayloadActionKind] = []

    async def execute(self, action: PayloadAction) -> PayloadActionResult:
        self.actions.append(action.kind)
        return PayloadActionResult(
            action_id=action.id,
            agent_id=self.agent_id,
            kind=action.kind,
            status=PayloadActionStatus.SIMULATED,
            execution_mode=PayloadExecutionMode.SIMULATED,
            light_on=action.kind is PayloadActionKind.LIGHT_ON,
            speaker_active=action.kind is PayloadActionKind.PLAY_MESSAGE,
            message=action.message,
        )


def _orchestrator(
    bus: RecordingBus, controller: RecordingPayloadController
) -> PresenceResponseBusFleetOrchestrator:
    payloads = PayloadControllerRegistry()
    payloads.register(controller)
    return PresenceResponseBusFleetOrchestrator(
        bus=bus,  # type: ignore[arg-type]
        registry=AdapterRegistry(),
        payload_registry=payloads,
        presence_hold_s=0.0,
    )


def _bind_intrusion(
    orchestrator: PresenceResponseBusFleetOrchestrator,
    *,
    role: str,
):
    mission = VERIFY(geo=Geo(lat=45.0, lon=9.0), hover_s=0.0)
    mission.params["execution_group_id"] = "group-test"
    orchestrator._group_task_to_role[mission.id] = ("group-test", role)
    orchestrator._mission_anomalies[mission.id] = Anomaly(
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0, lon=9.0),
        confidence=0.99,
    )
    return mission


@pytest.mark.asyncio
async def test_secondary_group_role_cannot_activate_presence_payload() -> None:
    bus = RecordingBus()
    payload = RecordingPayloadController("unit-002")
    orchestrator = _orchestrator(bus, payload)
    mission = _bind_intrusion(orchestrator, role="SECONDARY_OBSERVER")

    await orchestrator._run_mission(
        "unit-002", MissionAdapter(), mission, is_verify=True
    )

    assert payload.actions == []


@pytest.mark.asyncio
async def test_primary_group_role_keeps_central_payload_authority() -> None:
    bus = RecordingBus()
    payload = RecordingPayloadController("unit-001")
    orchestrator = _orchestrator(bus, payload)
    mission = _bind_intrusion(orchestrator, role=PRIMARY_PRESENCE_ROLE)

    await orchestrator._run_mission(
        "unit-001", MissionAdapter(), mission, is_verify=True
    )

    assert payload.actions == [
        PayloadActionKind.LIGHT_ON,
        PayloadActionKind.PLAY_MESSAGE,
        PayloadActionKind.STOP_MESSAGE,
        PayloadActionKind.LIGHT_OFF,
    ]
