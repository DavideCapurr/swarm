from __future__ import annotations

import asyncio
import contextlib

import pytest

from backend.app.bus_consumer import BusConsumer
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from swarm_core.messages import Event, EventKind


class RecordingHub:
    def __init__(self) -> None:
        self.frames: list[dict[str, object]] = []

    async def broadcast(self, frame: dict[str, object]) -> None:
        self.frames.append(frame)


class RecordingState:
    def __init__(self) -> None:
        self.events: list[Event] = []

    def append_event(self, event: Event) -> None:
        self.events.append(event)


class RecordingCoordinator:
    def __init__(self) -> None:
        self.state = RecordingState()


@pytest.mark.asyncio
async def test_external_payload_event_is_validated_and_broadcast_as_event() -> None:
    hub = RecordingHub()
    consumer = BusConsumer(hub)  # type: ignore[arg-type]
    bus = InMemoryBus()
    await bus.connect()
    consumer._bus = bus  # type: ignore[attr-defined]
    coordinator = RecordingCoordinator()
    consumer._coordinator = coordinator  # type: ignore[assignment]

    async def no_persist(*, frame_events: bool) -> None:
        assert frame_events is True

    consumer._persist_frames = no_persist  # type: ignore[method-assign]
    task = asyncio.create_task(consumer._consume_external_events())
    await asyncio.sleep(0)
    event = Event(
        kind=EventKind.MISSION,
        agent_id="unit-001",
        body="unit-001 light on · SIMULATED PAYLOAD",
        action_label="presence response",
        source="autonomy",
    )
    await bus.publish("swarm:events:payload", event.model_dump_json())

    for _ in range(20):
        if hub.frames:
            break
        await asyncio.sleep(0.01)

    assert len(hub.frames) == 1
    assert hub.frames[0]["kind"] == "event"
    assert coordinator.state.events == [event]

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await bus.close()
