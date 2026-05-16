"""Tests for the out-of-process MAVLink runner."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator

import pytest

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.runner import (
    MAVLinkRunner,
    adapter_from_env,
    boot_runner,
)
from orchestrator.swarm_orchestrator.bus import InMemoryBus


@pytest.fixture
async def bus_and_endpoint() -> AsyncIterator[tuple[InMemoryBus, FakeMAVLinkEndpoint]]:
    bus = InMemoryBus()
    await bus.connect()
    endpoint = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    await endpoint.start()
    yield bus, endpoint
    await endpoint.stop()
    await bus.close()


@pytest.mark.asyncio
async def test_runner_publishes_telemetry_to_bus(
    bus_and_endpoint: tuple[InMemoryBus, FakeMAVLinkEndpoint],
) -> None:
    bus, endpoint = bus_and_endpoint
    adapter = MAVLinkAdapter(
        agent_id="mav-test",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    runner = MAVLinkRunner(adapter=adapter, bus=bus)
    await runner.start()
    try:
        received: list[str] = []

        async def collect() -> None:
            async for _topic, payload in bus.subscribe("swarm:telemetry:mav-test"):
                received.append(payload)
                if len(received) >= 2:
                    return

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=3.0)
        assert len(received) >= 1
        msg = json.loads(received[0])
        assert msg["agent_id"] == "mav-test"
        assert 0.0 <= float(msg["battery_pct"]) <= 100.0
    finally:
        await runner.stop()


@pytest.mark.asyncio
async def test_runner_publishes_fleet_state(
    bus_and_endpoint: tuple[InMemoryBus, FakeMAVLinkEndpoint],
) -> None:
    bus, endpoint = bus_and_endpoint
    adapter = MAVLinkAdapter(
        agent_id="mav-test",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    runner = MAVLinkRunner(adapter=adapter, bus=bus, fleet_state_hz=10.0)
    await runner.start()
    try:
        received: list[str] = []

        async def collect() -> None:
            async for _topic, payload in bus.subscribe("swarm:fleet:state"):
                received.append(payload)
                if len(received) >= 1:
                    return

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=3.0)
        assert len(received) >= 1
        msg = json.loads(received[0])
        assert msg["agent_id"] == "mav-test"
        assert msg["vendor"] == "mavlink"
    finally:
        await runner.stop()


@pytest.mark.asyncio
async def test_runner_publishes_stream_descriptor_offline(
    bus_and_endpoint: tuple[InMemoryBus, FakeMAVLinkEndpoint],
) -> None:
    bus, endpoint = bus_and_endpoint
    adapter = MAVLinkAdapter(
        agent_id="mav-test",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    runner = MAVLinkRunner(adapter=adapter, bus=bus)
    await runner.start()
    try:
        received: list[str] = []

        async def collect() -> None:
            async for _topic, payload in bus.subscribe("swarm:streams:mav-test"):
                received.append(payload)
                if len(received) >= 1:
                    return

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=3.0)
        assert len(received) >= 1
        msg = json.loads(received[0])
        assert msg["available"] is False
        assert msg["url"] is None
    finally:
        await runner.stop()


@pytest.mark.asyncio
async def test_runner_publishes_stream_descriptor_https(
    bus_and_endpoint: tuple[InMemoryBus, FakeMAVLinkEndpoint],
) -> None:
    bus, endpoint = bus_and_endpoint
    adapter = MAVLinkAdapter(
        agent_id="mav-test",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
        stream_url="https://stream.example.com/hls/mav-test.m3u8",
    )
    runner = MAVLinkRunner(adapter=adapter, bus=bus)
    await runner.start()
    try:
        received: list[str] = []

        async def collect() -> None:
            async for _topic, payload in bus.subscribe("swarm:streams:mav-test"):
                received.append(payload)
                if len(received) >= 1:
                    return

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=3.0)
        assert len(received) >= 1
        msg = json.loads(received[0])
        assert msg["available"] is True
        assert msg["url"] == "https://stream.example.com/hls/mav-test.m3u8"
        assert msg["protocol"] == "https"
    finally:
        await runner.stop()


def test_adapter_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("MAVLINK_AGENT_ID", "MAVLINK_CONNECTION", "MAVLINK_MODEL",
                "MAVLINK_STREAM_URL", "MAVLINK_RATE_LIMIT_HZ"):
        monkeypatch.delenv(var, raising=False)
    adapter = adapter_from_env()
    assert adapter.agent_id == "mav-001"
    assert adapter._connection_str == "udp:localhost:14540"
    assert adapter._stream_url is None


def test_adapter_from_env_with_stream_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAVLINK_AGENT_ID", "mav-042")
    monkeypatch.setenv("MAVLINK_STREAM_URL", "rtsps://camera.example.com:8554/u1")
    monkeypatch.setenv("MAVLINK_RATE_LIMIT_HZ", "12")
    adapter = adapter_from_env()
    assert adapter.agent_id == "mav-042"
    assert adapter._stream_url == "rtsps://camera.example.com:8554/u1"
    assert adapter._rate_limiter.max_hz == 12.0


def test_adapter_from_env_rejects_plaintext_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAVLINK_STREAM_URL", "http://insecure.example.com/u1")
    from swarm_core.streams import InvalidStreamURL

    with pytest.raises(InvalidStreamURL):
        adapter_from_env()


@pytest.mark.asyncio
async def test_boot_runner_registers_adapter(
    bus_and_endpoint: tuple[InMemoryBus, FakeMAVLinkEndpoint],
) -> None:
    bus, endpoint = bus_and_endpoint
    adapter = MAVLinkAdapter(
        agent_id="mav-boot",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    registry = AdapterRegistry()
    runner = await boot_runner(bus, registry, adapter=adapter)
    try:
        assert registry.get("mav-boot") is adapter
    finally:
        await runner.stop()
