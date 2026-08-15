from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.fleet_runner import (
    MAVLinkFleetConfigError,
    adapters_from_env,
    boot_fleet_runner,
    parse_mavlink_fleet,
)
from orchestrator.swarm_orchestrator.bus import InMemoryBus


def test_parse_mavlink_fleet() -> None:
    units = parse_mavlink_fleet(
        "mav-001=udp:localhost:14540, mav-002=udp:localhost:14541"
    )
    assert [(u.agent_id, u.connection) for u in units] == [
        ("mav-001", "udp:localhost:14540"),
        ("mav-002", "udp:localhost:14541"),
    ]


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "mav-001",
        "=udp:localhost:14540",
        "mav-001=",
        "mav-001=udp:localhost:14540,mav-001=udp:localhost:14541",
    ],
)
def test_parse_mavlink_fleet_rejects_invalid_config(raw: str) -> None:
    with pytest.raises(MAVLinkFleetConfigError):
        parse_mavlink_fleet(raw)


def test_adapters_from_env_preserves_legacy_single_unit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MAVLINK_FLEET", raising=False)
    monkeypatch.setenv("MAVLINK_AGENT_ID", "legacy-001")
    monkeypatch.setenv("MAVLINK_CONNECTION", "udp:localhost:14599")
    adapters = adapters_from_env()
    assert len(adapters) == 1
    assert adapters[0].agent_id == "legacy-001"
    assert adapters[0]._connection_str == "udp:localhost:14599"


def test_adapters_from_env_builds_multiple_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MAVLINK_FLEET",
        "mav-001=udp:localhost:14540,mav-002=udp:localhost:14541",
    )
    monkeypatch.setenv("MAVLINK_MODEL", "px4-x500")
    adapters = adapters_from_env()
    assert [a.agent_id for a in adapters] == ["mav-001", "mav-002"]
    assert [a._connection_str for a in adapters] == [
        "udp:localhost:14540",
        "udp:localhost:14541",
    ]


@pytest.fixture
async def bus_and_endpoints() -> AsyncIterator[
    tuple[InMemoryBus, FakeMAVLinkEndpoint, FakeMAVLinkEndpoint]
]:
    bus = InMemoryBus()
    await bus.connect()
    first = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    second = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    await first.start()
    await second.start()
    yield bus, first, second
    await first.stop()
    await second.stop()
    await bus.close()


@pytest.mark.asyncio
async def test_boot_fleet_runner_registers_two_live_adapters(
    bus_and_endpoints: tuple[InMemoryBus, FakeMAVLinkEndpoint, FakeMAVLinkEndpoint],
) -> None:
    bus, first, second = bus_and_endpoints
    adapters = [
        MAVLinkAdapter(
            agent_id="mav-001",
            connection=f"udpout:127.0.0.1:{first.port}",
            heartbeat_timeout_s=10.0,
        ),
        MAVLinkAdapter(
            agent_id="mav-002",
            connection=f"udpout:127.0.0.1:{second.port}",
            heartbeat_timeout_s=10.0,
        ),
    ]
    registry = AdapterRegistry()
    fleet = await boot_fleet_runner(bus, registry, adapters=adapters)
    try:
        assert [a.agent_id for a in registry.all()] == ["mav-001", "mav-002"]
        assert all((await a.health()).online for a in adapters)
    finally:
        await fleet.stop()
