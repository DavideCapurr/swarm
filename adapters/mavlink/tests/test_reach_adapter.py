from __future__ import annotations

import asyncio

import pytest
from swarm_core.messages import Geo, MissionProgress
from swarm_core.missions import VERIFY

from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.reach_adapter import ReachAwareMAVLinkAdapter


class ReachingFakeMAVLinkEndpoint(FakeMAVLinkEndpoint):
    """Fake autopilot that reports current first, then actual item reached."""

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


async def _collect_mission(
    adapter: ReachAwareMAVLinkAdapter,
) -> list[MissionProgress]:
    mission = VERIFY(
        geo=Geo(lat=44.7001, lon=8.0301),
        hover_s=0.0,
        altitude_m=20.0,
    )
    return [frame async for frame in adapter.execute_mission(mission)]


@pytest.mark.asyncio
async def test_verify_completes_only_after_mission_item_reached() -> None:
    endpoint = ReachingFakeMAVLinkEndpoint(
        heartbeat_hz=10.0,
        position_hz=20.0,
    )
    await endpoint.start()
    adapter = ReachAwareMAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        frames = await _collect_mission(adapter)
        assert [frame.phase for frame in frames] == ["EN_ROUTE", "ON_STATION", "DONE"]
        assert adapter._mission_reached == 0
        assert endpoint.state.rtl_triggered is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()


@pytest.mark.asyncio
async def test_mission_current_zero_does_not_complete_single_waypoint_verify() -> None:
    # The base fake emits MISSION_CURRENT=0 for a live single-item mission but
    # intentionally never emits MISSION_ITEM_REACHED. This reproduces the
    # false-completion condition discovered in live multi-PX4 validation.
    endpoint = FakeMAVLinkEndpoint(
        heartbeat_hz=10.0,
        position_hz=20.0,
    )
    await endpoint.start()
    adapter = ReachAwareMAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        task = asyncio.create_task(_collect_mission(adapter))
        await asyncio.sleep(0.5)

        assert task.done() is False
        assert adapter._mission_current == 0
        assert adapter._mission_reached == -1
        assert endpoint.state.rtl_triggered is False

        await adapter.cancel_mission()
        frames = await asyncio.wait_for(task, timeout=2.0)
        assert frames[-1].phase == "FAILED"
        assert frames[-1].error == "cancelled"
        assert endpoint.state.rtl_triggered is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()


@pytest.mark.asyncio
async def test_deadline_expiry_fails_closed_into_rtl() -> None:
    endpoint = FakeMAVLinkEndpoint(
        heartbeat_hz=10.0,
        position_hz=20.0,
    )
    await endpoint.start()
    adapter = ReachAwareMAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    # Test seam: keep the production minimum deadline untouched while making
    # this failure-path test deterministic and fast.
    adapter._mission_deadline_s = lambda _mission, _waypoints: 0.25  # type: ignore[method-assign]
    try:
        await adapter.connect()
        frames = await _collect_mission(adapter)
        assert frames[-1].phase == "FAILED"
        assert frames[-1].error == "mission deadline exceeded before final waypoint reached"
        assert not any(frame.phase == "DONE" for frame in frames)
        assert endpoint.state.rtl_triggered is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()
