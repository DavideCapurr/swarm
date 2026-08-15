from __future__ import annotations

import asyncio
import contextlib
from collections import deque

import pytest
from swarm_core.allocations import AllocationDecision
from swarm_core.payloads import (
    PayloadActionKind,
    PayloadActionStatus,
    PayloadEvent,
    PayloadExecutionMode,
)
from swarm_core.runtime_events import (
    MissionRuntimeEvent,
    MissionRuntimeEvidence,
)

from backend.app.bus_consumer import BusConsumer
from orchestrator.swarm_orchestrator.bus import InMemoryBus


class RecordingHub:
    def __init__(self) -> None:
        self.frames: list[dict[str, object]] = []

    async def broadcast(self, frame: dict[str, object]) -> None:
        self.frames.append(frame)


class TruthState:
    def __init__(self) -> None:
        self.allocations: dict[str, AllocationDecision] = {}
        self.mission_runtime: dict[str, MissionRuntimeEvent] = {}
        self.payload_events: deque[PayloadEvent] = deque(maxlen=500)
        self.lock = asyncio.Lock()


class RecordingCoordinator:
    def __init__(self) -> None:
        self.state = TruthState()


@pytest.mark.asyncio
async def test_structured_console_truth_is_validated_stored_and_broadcast() -> None:
    hub = RecordingHub()
    consumer = BusConsumer(hub)  # type: ignore[arg-type]
    bus = InMemoryBus()
    await bus.connect()
    consumer._bus = bus
    coordinator = RecordingCoordinator()
    consumer._coordinator = coordinator  # type: ignore[assignment]

    tasks = [
        asyncio.create_task(consumer._consume_allocations()),
        asyncio.create_task(consumer._consume_mission_runtime()),
        asyncio.create_task(consumer._consume_payload_events()),
    ]
    await asyncio.sleep(0)

    decision = AllocationDecision(
        mission_id="mission-1",
        mission_kind="VERIFY",
        anomaly_id="anomaly-1",
        winner_agent_id="mav-002",
        winner_score=2.64,
    )
    runtime = MissionRuntimeEvent(
        mission_id="mission-1",
        agent_id="mav-002",
        phase="ON_STATION",
        progress_pct=95.0,
        evidence=MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED,
    )
    payload = PayloadEvent(
        mission_id="mission-1",
        anomaly_id="anomaly-1",
        action_id="action-1",
        agent_id="mav-002",
        kind=PayloadActionKind.LIGHT_ON,
        status=PayloadActionStatus.CONFIRMED,
        execution_mode=PayloadExecutionMode.MAVLINK_OUTPUT_CONFIRMED,
        light_on=True,
        speaker_active=False,
    )

    await bus.publish("swarm:allocations", decision.model_dump_json())
    await bus.publish("swarm:missions:runtime", runtime.model_dump_json())
    await bus.publish("swarm:payload:events", payload.model_dump_json())

    for _ in range(50):
        if len(hub.frames) >= 3:
            break
        await asyncio.sleep(0.01)

    assert {frame["kind"] for frame in hub.frames} == {
        "allocation",
        "mission_runtime",
        "payload",
    }
    assert coordinator.state.allocations["mission-1"] == decision
    assert coordinator.state.mission_runtime["mission-1"] == runtime
    assert list(coordinator.state.payload_events) == [payload]

    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    await bus.close()
