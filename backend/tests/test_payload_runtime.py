from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
from pymavlink import mavutil
from swarm_core.messages import Anomaly, AnomalyKind, Geo

from adapters.base import AdapterRegistry
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.fleet_runner import boot_fleet_runner
from adapters.mavlink.payload import MAV_CMD_DO_SET_ACTUATOR
from adapters.mavlink.reach_adapter import ReachAwareMAVLinkAdapter
from backend.app.fleet import FleetManager, VendorBootError
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus
from orchestrator.swarm_orchestrator.presence_bus import (
    PresenceResponseBusFleetOrchestrator,
)


class ReachingFakeMAVLinkEndpoint(FakeMAVLinkEndpoint):
    async def _advance_mission_loop(self) -> None:
        try:
            for seq in range(self.state.mission_total):
                if not self._running:
                    return
                self.state.mission_current = seq
                self._send(self._mav.mission_current_encode(seq=seq))
                await asyncio.sleep(0.1)
                self._send(self._mav.mission_item_reached_encode(seq=seq))
        except asyncio.CancelledError:
            raise


@pytest.fixture
async def payload_runtime() -> AsyncIterator[
    tuple[InMemoryBus, FleetManager, FakeMAVLinkEndpoint]
]:
    bus = InMemoryBus()
    await bus.connect()
    endpoint = ReachingFakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    endpoint.state.geo = (45.0001, 10.0001, 0.0)
    await endpoint.start()

    adapter = ReachAwareMAVLinkAdapter(
        agent_id="mav-001",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )

    async def _boot(bus_arg: Bus, registry: AdapterRegistry) -> object:
        return await boot_fleet_runner(bus_arg, registry, adapters=[adapter])

    fleet = FleetManager(
        bus=bus,
        vendors=("mavlink",),
        booters={"mavlink": _boot},
        mission_ready_timeout_s=3.0,
        presence_response_enabled=True,
        presence_min_confidence=0.85,
        presence_hold_s=0.0,
        light_actuator_number=1,
        simulate_speaker=True,
    )
    await fleet.start()
    yield bus, fleet, endpoint
    await fleet.stop()
    await endpoint.stop()
    await bus.close()


@pytest.mark.asyncio
async def test_intrusion_runs_payload_before_verify_returns_done(
    payload_runtime: tuple[InMemoryBus, FleetManager, FakeMAVLinkEndpoint],
) -> None:
    bus, fleet, endpoint = payload_runtime
    assert isinstance(fleet._mission_orchestrator, PresenceResponseBusFleetOrchestrator)
    assert len(fleet.payload_registry) == 1

    payload_events: list[dict[str, object]] = []
    progress: list[dict[str, object]] = []

    async def _watch_payload() -> None:
        async for _, payload in bus.subscribe("swarm:events:payload"):
            payload_events.append(json.loads(payload))
            if len(payload_events) == 4:
                return

    async def _watch_progress() -> None:
        async for _, payload in bus.subscribe("swarm:missions:progress:*"):
            frame = json.loads(payload)
            progress.append(frame)
            if frame["phase"] in ("DONE", "FAILED"):
                return

    payload_task = asyncio.create_task(_watch_payload())
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

    await asyncio.wait_for(payload_task, timeout=6.0)
    await asyncio.wait_for(progress_task, timeout=6.0)

    assert progress[-1]["phase"] == "DONE"
    assert any(frame["phase"] == "ON_STATION" for frame in progress)
    bodies = [str(event["body"]) for event in payload_events]
    assert any("light on · MAVLink ACK" in body for body in bodies)
    assert any(
        "restricted-area message active · SIMULATED PAYLOAD" in body
        for body in bodies
    )
    assert any(
        "restricted-area message stopped · SIMULATED PAYLOAD" in body
        for body in bodies
    )
    assert any("light off · MAVLink ACK" in body for body in bodies)
    assert endpoint.state.command_calls.count(MAV_CMD_DO_SET_ACTUATOR) == 2
    assert mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH in endpoint.state.command_calls


@pytest.mark.asyncio
async def test_presence_runtime_fails_closed_without_payload_capability() -> None:
    bus = InMemoryBus()
    await bus.connect()

    class StubRunner:
        async def stop(self) -> None:
            return None

    async def _boot(_bus: Bus, _registry: AdapterRegistry) -> object:
        return StubRunner()

    fleet = FleetManager(
        bus=bus,
        vendors=("mavlink",),
        booters={"mavlink": _boot},
        presence_response_enabled=True,
    )
    with pytest.raises(VendorBootError):
        await fleet.start()
    await fleet.stop()
    await bus.close()
