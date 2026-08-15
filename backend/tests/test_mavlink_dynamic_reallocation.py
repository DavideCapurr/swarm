from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import pytest
from swarm_core.messages import Anomaly, AnomalyKind, Geo

from adapters.base import AdapterRegistry
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.fleet_runner import boot_fleet_runner
from adapters.mavlink.reach_adapter import ReachAwareMAVLinkAdapter
from backend.app.fleet import FleetManager
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus


class SlowReachingEndpoint(FakeMAVLinkEndpoint):
    """Fake PX4 that stays airborne long enough to trigger a second auction."""

    def __init__(self, *, reach_delay_s: float = 1.5) -> None:
        super().__init__(heartbeat_hz=10.0, position_hz=20.0)
        self.reach_delay_s = reach_delay_s

    async def _advance_mission_loop(self) -> None:
        try:
            lat, lon, _ = self.state.geo
            self.state.geo = (lat, lon, 20.0)
            for seq in range(self.state.mission_total):
                if not self._running:
                    return
                self.state.mission_current = seq
                self._send(self._mav.mission_current_encode(seq=seq))
                await asyncio.sleep(self.reach_delay_s)
                self._send(self._mav.mission_item_reached_encode(seq=seq))
        except asyncio.CancelledError:
            raise


@pytest.fixture
async def dynamic_runtime() -> AsyncIterator[
    tuple[InMemoryBus, FleetManager, SlowReachingEndpoint, SlowReachingEndpoint]
]:
    bus = InMemoryBus()
    await bus.connect()

    near = SlowReachingEndpoint()
    far = SlowReachingEndpoint()
    near.state.geo = (45.0001, 10.0001, 0.0)
    far.state.geo = (45.0200, 10.0200, 0.0)
    await near.start()
    await far.start()

    adapters = [
        ReachAwareMAVLinkAdapter(
            agent_id="mav-near",
            connection=f"udpout:127.0.0.1:{near.port}",
            heartbeat_timeout_s=10.0,
        ),
        ReachAwareMAVLinkAdapter(
            agent_id="mav-far",
            connection=f"udpout:127.0.0.1:{far.port}",
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
    try:
        yield bus, fleet, near, far
    finally:
        await fleet.stop()
        await near.stop()
        await far.stop()
        await bus.close()


@pytest.mark.asyncio
async def test_second_event_reallocates_to_idle_vehicle_while_first_verify_is_active(
    dynamic_runtime: tuple[
        InMemoryBus,
        FleetManager,
        SlowReachingEndpoint,
        SlowReachingEndpoint,
    ],
) -> None:
    bus, fleet, _near, _far = dynamic_runtime
    assert fleet._mission_orchestrator is not None

    awards: list[dict[str, object]] = []
    terminals: dict[str, float] = {}
    first_en_route = asyncio.Event()
    near_airborne = asyncio.Event()

    async def _watch_awards() -> None:
        async for _, payload in bus.subscribe("swarm:missions:award"):
            awards.append(json.loads(payload))
            if len(awards) >= 2:
                return

    async def _watch_progress() -> None:
        async for _topic, payload in bus.subscribe("swarm:missions:progress:*"):
            frame = json.loads(payload)
            if frame["phase"] == "EN_ROUTE" and len(awards) == 1:
                first_en_route.set()
            if frame["phase"] in ("DONE", "FAILED"):
                mission_id = str(frame["mission_id"])
                terminals[mission_id] = time.monotonic()
                if len(terminals) >= 2:
                    return

    async def _watch_fleet() -> None:
        async for _, payload in bus.subscribe("swarm:fleet:state"):
            frame = json.loads(payload)
            if frame["agent_id"] == "mav-near" and frame["fsm_state"] == "EN_ROUTE":
                near_airborne.set()
                return

    award_task = asyncio.create_task(_watch_awards())
    progress_task = asyncio.create_task(_watch_progress())
    fleet_task = asyncio.create_task(_watch_fleet())
    await asyncio.sleep(0)

    await bus.publish(
        "swarm:anomalies",
        Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=45.0, lon=10.0),
            confidence=0.90,
        ).model_dump_json(),
    )

    await asyncio.wait_for(first_en_route.wait(), timeout=3.0)
    await asyncio.wait_for(near_airborne.wait(), timeout=3.0)
    assert awards[0]["winner_agent_id"] == "mav-near"
    first_mission_id = str(awards[0]["mission_id"])
    assert first_mission_id not in terminals

    second_published_at = time.monotonic()
    await bus.publish(
        "swarm:anomalies",
        Anomaly(
            kind=AnomalyKind.HEAT_SPOT,
            geo=Geo(lat=45.0201, lon=10.0201),
            confidence=0.99,
        ).model_dump_json(),
    )

    await asyncio.wait_for(award_task, timeout=3.0)
    assert awards[1]["winner_agent_id"] == "mav-far"
    second_mission_id = str(awards[1]["mission_id"])
    assert second_mission_id != first_mission_id
    assert first_mission_id not in terminals

    await asyncio.wait_for(progress_task, timeout=5.0)
    assert terminals[first_mission_id] > second_published_at
    assert terminals[second_mission_id] > second_published_at

    if not fleet_task.done():
        fleet_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await fleet_task
