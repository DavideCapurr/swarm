from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from pymavlink import mavutil
from swarm_core.messages import Anomaly, AnomalyKind, Geo

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.fleet_runner import boot_fleet_runner
from backend.app.fleet import FleetManager
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus


@pytest.fixture
async def runtime_fixture() -> AsyncIterator[
    tuple[InMemoryBus, FleetManager, FakeMAVLinkEndpoint, FakeMAVLinkEndpoint]
]:
    bus = InMemoryBus()
    await bus.connect()
    near_endpoint = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    far_endpoint = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    near_endpoint.state.geo = (45.0001, 10.0001, 0.0)
    far_endpoint.state.geo = (45.0200, 10.0200, 0.0)
    await near_endpoint.start()
    await far_endpoint.start()

    adapters = [
        MAVLinkAdapter(
            agent_id="mav-near",
            connection=f"udpout:127.0.0.1:{near_endpoint.port}",
            heartbeat_timeout_s=10.0,
        ),
        MAVLinkAdapter(
            agent_id="mav-far",
            connection=f"udpout:127.0.0.1:{far_endpoint.port}",
            heartbeat_timeout_s=10.0,
        ),
    ]

    async def _boot(bus_arg: Bus, registry: AdapterRegistry) -> object:
        return await boot_fleet_runner(bus_arg, registry, adapters=adapters)

    fleet = FleetManager(
        bus=bus,
        vendors=("mavlink",),
        booters={"mavlink": _boot},
        mission_ready_timeout_s=3.0,
    )
    await fleet.start()
    yield bus, fleet, near_endpoint, far_endpoint
    await fleet.stop()
    await near_endpoint.stop()
    await far_endpoint.stop()
    await bus.close()


@pytest.mark.asyncio
async def test_two_mavlink_units_are_auctioned_and_only_winner_executes_verify(
    runtime_fixture: tuple[
        InMemoryBus,
        FleetManager,
        FakeMAVLinkEndpoint,
        FakeMAVLinkEndpoint,
    ],
) -> None:
    bus, fleet, near_endpoint, far_endpoint = runtime_fixture
    assert len(fleet.registry) == 2
    assert fleet._mission_orchestrator is not None

    awards: list[dict[str, object]] = []
    progress: list[dict[str, object]] = []

    async def _watch_award() -> None:
        async for _, payload in bus.subscribe("swarm:missions:award"):
            awards.append(json.loads(payload))
            return

    async def _watch_progress() -> None:
        async for _, payload in bus.subscribe("swarm:missions:progress:*"):
            frame = json.loads(payload)
            progress.append(frame)
            if frame["phase"] in ("DONE", "FAILED"):
                return

    award_task = asyncio.create_task(_watch_award())
    progress_task = asyncio.create_task(_watch_progress())
    await asyncio.sleep(0)

    await bus.publish(
        "swarm:anomalies",
        Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=45.0, lon=10.0),
            confidence=0.95,
        ).model_dump_json(),
    )

    await asyncio.wait_for(award_task, timeout=3.0)
    await asyncio.wait_for(progress_task, timeout=5.0)

    assert awards[0]["winner_agent_id"] == "mav-near"
    assert progress[-1]["phase"] == "DONE"
    assert mavutil.mavlink.MAV_CMD_MISSION_START in near_endpoint.state.command_calls
    assert mavutil.mavlink.MAV_CMD_MISSION_START not in far_endpoint.state.command_calls
    assert mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH in near_endpoint.state.command_calls
