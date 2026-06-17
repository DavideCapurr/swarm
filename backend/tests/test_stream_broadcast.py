"""Tests for the WS `stream` frame fan-out.

Phase 5: an adapter runner publishes `swarm:streams:<agent_id>` with a
`StreamDescriptor`; the backend bus consumer subscribes, re-validates the
URL allowlist (defense in depth), and re-emits a `{"kind": "stream"}` frame
to every WS client.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import pytest
from swarm_core.messages import Geo, Telemetry
from swarm_core.streams import StreamDescriptor

from backend.app.bus_consumer import BusConsumer


class _CapturingHub:
    """In-memory `WSHub` substitute for tests."""

    def __init__(self) -> None:
        self.frames: list[dict[str, Any]] = []

    async def broadcast(self, msg: dict[str, Any]) -> None:
        self.frames.append(msg)


@pytest.fixture
async def consumer(monkeypatch: pytest.MonkeyPatch) -> Any:
    # Force the InMemoryBus path so no redis is required.
    monkeypatch.delenv("REDIS_URL", raising=False)
    hub = _CapturingHub()
    bc = BusConsumer(hub)  # type: ignore[arg-type]
    await bc.start()
    yield bc, hub
    await bc.stop()


@pytest.mark.asyncio
async def test_stream_descriptor_offline_is_rebroadcast(consumer: Any) -> None:
    bc, hub = consumer
    descriptor = StreamDescriptor.offline("mav-001")
    await bc.bus.publish("swarm:streams:mav-001", descriptor.model_dump_json())

    async def wait_for_frame() -> dict[str, Any]:
        while True:
            for frame in hub.frames:
                if frame.get("kind") == "stream":
                    return dict(frame)
            await asyncio.sleep(0.05)

    frame = await asyncio.wait_for(wait_for_frame(), timeout=2.0)
    assert frame["data"]["available"] is False
    assert frame["data"]["url"] is None


@pytest.mark.asyncio
async def test_backend_telemetry_rate_cap_drops_excess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    hub = _CapturingHub()
    bc = BusConsumer(hub, telemetry_rate_limit_hz=1.0)  # type: ignore[arg-type]
    await bc.start()
    try:
        await asyncio.sleep(0.1)
        for i in range(5):
            t = Telemetry(
                agent_id="rate-capped",
                geo=Geo(lat=44.7 + i * 0.0001, lon=8.03),
            )
            await bc.bus.publish("swarm:telemetry:rate-capped", t.model_dump_json())

        async def wait_for_drop() -> None:
            while bc._telemetry_limiter.stats["dropped_total"] < 1:
                await asyncio.sleep(0.05)

        await asyncio.wait_for(wait_for_drop(), timeout=2.0)
        unit_frames = [
            f
            for f in hub.frames
            if f.get("kind") == "unit" and f["data"]["agent_id"] == "rate-capped"
        ]
        assert len(unit_frames) == 1
    finally:
        await bc.stop()


@pytest.mark.asyncio
async def test_stream_descriptor_https_is_rebroadcast(consumer: Any) -> None:
    bc, hub = consumer
    descriptor = StreamDescriptor(
        agent_id="mav-002",
        available=True,
        url="https://stream.example.com/hls/m2.m3u8",
        protocol="https",
        codec="h264",
    )
    await bc.bus.publish("swarm:streams:mav-002", descriptor.model_dump_json())

    async def wait_for_frame() -> dict[str, Any]:
        while True:
            for frame in hub.frames:
                if frame.get("kind") == "stream" and frame["data"]["agent_id"] == "mav-002":
                    return dict(frame)
            await asyncio.sleep(0.05)

    frame = await asyncio.wait_for(wait_for_frame(), timeout=2.0)
    assert frame["data"]["available"] is True
    assert frame["data"]["url"] == "https://stream.example.com/hls/m2.m3u8"
    assert frame["data"]["protocol"] == "https"


@pytest.mark.asyncio
async def test_simulated_stream_descriptor_is_rebroadcast(consumer: Any) -> None:
    """CV-live video sub-step: a simulated (`/sim-feed/…`) feed survives the
    backend re-validation and reaches the Console with `simulated=true`."""
    bc, hub = consumer
    descriptor = StreamDescriptor.simulated_feed(
        "sim-003", "/sim-feed/drone-pov.mp4", codec="h264"
    )
    await bc.bus.publish("swarm:streams:sim-003", descriptor.model_dump_json())

    async def wait_for_frame() -> dict[str, Any]:
        while True:
            for frame in hub.frames:
                if frame.get("kind") == "stream" and frame["data"]["agent_id"] == "sim-003":
                    return dict(frame)
            await asyncio.sleep(0.05)

    frame = await asyncio.wait_for(wait_for_frame(), timeout=2.0)
    assert frame["data"]["available"] is True
    assert frame["data"]["simulated"] is True
    assert frame["data"]["url"] == "/sim-feed/drone-pov.mp4"
    assert frame["data"]["protocol"] is None


@pytest.mark.asyncio
async def test_forged_simulated_descriptor_with_external_url_is_dropped(
    consumer: Any,
) -> None:
    """Re-validation rejects a `simulated` descriptor whose url is not a
    same-origin `/sim-feed/` path — a forged external/SSRF target must not be
    re-broadcast just because it set `simulated=true`."""
    bc, hub = consumer
    forged = json.dumps(
        {
            "agent_id": "forged-sim",
            "available": True,
            "simulated": True,
            "url": "https://evil.example.com/sim-feed/x.mp4",
        }
    )
    await bc.bus.publish("swarm:streams:forged-sim", forged)
    await asyncio.sleep(0.2)
    assert not any(
        f.get("kind") == "stream" and f["data"]["agent_id"] == "forged-sim"
        for f in hub.frames
    )


@pytest.mark.asyncio
async def test_stream_descriptor_malformed_payload_is_dropped(consumer: Any) -> None:
    """Defense in depth: an adapter publishing junk must not poison the WS."""
    bc, hub = consumer
    await bc.bus.publish("swarm:streams:bad", "{not valid json")
    await bc.bus.publish("swarm:streams:bad", "{}")
    # Give the consumer a turn to swallow both payloads.
    await asyncio.sleep(0.2)
    stream_frames = [f for f in hub.frames if f.get("kind") == "stream"]
    assert stream_frames == []


@pytest.mark.asyncio
async def test_stream_descriptor_with_plaintext_url_is_dropped(consumer: Any) -> None:
    """Re-validation on the backend rejects URLs the adapter shouldn't have
    been allowed to publish in the first place."""
    bc, hub = consumer
    # Craft a JSON blob that bypasses the adapter's init check.
    forged = json.dumps(
        {
            "agent_id": "bad-mav",
            "available": True,
            "url": "http://insecure.example.com/u1",
            "protocol": "https",
        }
    )
    await bc.bus.publish("swarm:streams:bad-mav", forged)
    await asyncio.sleep(0.2)
    assert not any(f.get("kind") == "stream" for f in hub.frames)


@pytest.mark.asyncio
async def test_stream_descriptor_lands_in_coordinator_state(consumer: Any) -> None:
    bc, _hub = consumer
    descriptor = StreamDescriptor.offline("mav-state")
    await bc.bus.publish("swarm:streams:mav-state", descriptor.model_dump_json())

    async def wait_for_state() -> StreamDescriptor:
        while True:
            stream = bc._coordinator.state.streams.get("mav-state")
            if stream is not None:
                assert isinstance(stream, StreamDescriptor)
                return stream
            await asyncio.sleep(0.05)

    stored = await asyncio.wait_for(wait_for_state(), timeout=2.0)
    assert stored.agent_id == "mav-state"


@pytest.mark.asyncio
async def test_snapshot_frames_include_streams(consumer: Any) -> None:
    bc, _hub = consumer
    descriptor = StreamDescriptor.offline("mav-snap")
    await bc.bus.publish("swarm:streams:mav-snap", descriptor.model_dump_json())
    # Wait for the consumer to land the frame.
    for _ in range(40):
        if bc._coordinator.state.streams.get("mav-snap") is not None:
            break
        await asyncio.sleep(0.05)
    frames = await bc._coordinator.snapshot_frames()
    stream_frames = [f for f in frames if f["kind"] == "stream"]
    assert any(f["data"]["agent_id"] == "mav-snap" for f in stream_frames)


# Re-export contextlib so the `from __future__` lint doesn't trip on the
# fixture pattern even when no test imports it.
_ = contextlib
