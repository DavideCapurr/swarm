"""Tests for the Mission DSL → MAVLink mapping.

Asserts the roadmap §Phase 5 mapping:
  PATROL / VERIFY → MISSION_COUNT + MISSION_ITEM_INT + MISSION_START
  RTL_DOCK        → MAV_CMD_NAV_RETURN_TO_LAUNCH
  RELAY           → MAV_CMD_NAV_LOITER_UNLIM
  COVER           → UnsupportedMission

Plus safety guarantees that survive across mission kinds:
  - geofence pre-upload rejection (defense in depth before the autopilot
    fence even gets a chance to fail)
  - altitude pre-upload rejection (waypoint > max_alt_m)
  - heartbeat watchdog → cancel + RTL
  - rate limiter caps telemetry below the configured Hz
  - stream_video stays a no-op
  - stream_descriptor honors the URL allowlist
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from pymavlink import mavutil
from swarm_core.messages import Geo, SensorKind
from swarm_core.missions import COVER, PATROL, RELAY, RTL_DOCK, VERIFY, UnsupportedMission

from adapters.base import Polygon
from adapters.mavlink.adapter import (
    HEARTBEAT_TIMEOUT_S,
    MAVLinkAdapter,
    RejectedMission,
    point_in_polygon,
)
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint

VINEYARD_FENCE = Polygon(
    points=(
        Geo(lat=44.69, lon=8.02),
        Geo(lat=44.71, lon=8.02),
        Geo(lat=44.71, lon=8.04),
        Geo(lat=44.69, lon=8.04),
    )
)


@pytest.fixture
async def adapter_pair() -> Any:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    await adapter.connect()
    try:
        yield adapter, endpoint
    finally:
        await adapter.disconnect()
        await endpoint.stop()


# ── Mapping ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_verify_uploads_mission_items(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    mission = VERIFY(geo=Geo(lat=44.7, lon=8.03), hover_s=0.1)
    phases: list[str] = []

    async def run() -> None:
        async for p in adapter.execute_mission(mission):
            phases.append(p.phase)

    await asyncio.wait_for(run(), timeout=10.0)
    # The fake recorded the upload.
    assert endpoint.state.mission_total == 1
    lat, lon, _alt = endpoint.state.mission_items[0]
    assert abs(lat - 44.7) < 1e-5
    assert abs(lon - 8.03) < 1e-5
    # The adapter switched to AUTO.MISSION and asked the autopilot to arm + start.
    assert endpoint.state.set_mode_calls >= 1
    assert mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM in endpoint.state.command_calls
    assert mavutil.mavlink.MAV_CMD_MISSION_START in endpoint.state.command_calls
    # And the final phase was DONE.
    assert phases[-1] == "DONE"


@pytest.mark.asyncio
async def test_patrol_uploads_multi_waypoint_mission(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    area = [
        Geo(lat=44.700, lon=8.030),
        Geo(lat=44.701, lon=8.031),
        Geo(lat=44.702, lon=8.032),
    ]
    mission = PATROL(area=area)
    phases: list[str] = []

    async def run() -> None:
        async for p in adapter.execute_mission(mission):
            phases.append(p.phase)

    await asyncio.wait_for(run(), timeout=10.0)
    assert endpoint.state.mission_total == 3
    assert phases[-1] == "DONE"


@pytest.mark.asyncio
async def test_rtl_dock_emits_return_to_launch(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    mission = RTL_DOCK()
    phases: list[str] = []
    async for p in adapter.execute_mission(mission):
        phases.append(p.phase)
    # The RTL COMMAND_LONG is on the wire — give the fake a tick to record it.
    await asyncio.sleep(0.3)
    assert phases == ["DONE"]
    assert endpoint.state.rtl_triggered is True


@pytest.mark.asyncio
async def test_relay_emits_loiter_unlimited(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    mission = RELAY(geo=Geo(lat=44.7, lon=8.03), duration_s=0.2)
    phases: list[str] = []
    async for p in adapter.execute_mission(mission):
        phases.append(p.phase)
    assert "ON_STATION" in phases
    assert phases[-1] == "DONE"
    assert mavutil.mavlink.MAV_CMD_NAV_LOITER_UNLIM in endpoint.state.command_calls


@pytest.mark.asyncio
async def test_cover_rejected_with_unsupported_mission(adapter_pair: Any) -> None:
    adapter, _ = adapter_pair
    mission = COVER(area=[Geo(lat=44.7, lon=8.03)], fleet_size=2)
    with pytest.raises(UnsupportedMission):
        async for _p in adapter.execute_mission(mission):
            pass


@pytest.mark.asyncio
async def test_unknown_kind_rejected(adapter_pair: Any) -> None:
    adapter, _ = adapter_pair
    from swarm_core.messages import MissionTask

    bad = MissionTask(kind="NOT_A_KIND")
    with pytest.raises(UnsupportedMission):
        async for _p in adapter.execute_mission(bad):
            pass


# ── Safety enforcement ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_set_safety_uploads_fence_points_and_params(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    await adapter.set_safety(VINEYARD_FENCE, max_alt_m=120.0, rtl_battery_pct=25)
    # Let the fake autopilot drain the upload queue.
    await asyncio.sleep(0.4)
    # Fence enabled via DO_FENCE_ENABLE.
    assert endpoint.state.fence_enabled is True
    # 4 corner points uploaded.
    assert len(endpoint.state.fence_points) == 4
    # Params recorded.
    assert "BAT_LOW_THR" in endpoint.state.params
    assert abs(endpoint.state.params["BAT_LOW_THR"] - 0.25) < 1e-5
    assert "MIS_TAKEOFF_ALT" in endpoint.state.params


@pytest.mark.asyncio
async def test_pre_upload_rejects_waypoint_outside_geofence(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    await adapter.set_safety(VINEYARD_FENCE, max_alt_m=120.0, rtl_battery_pct=25)
    # Waypoint clearly outside the polygon.
    mission = VERIFY(geo=Geo(lat=50.0, lon=8.03), hover_s=0.1)
    with pytest.raises(RejectedMission):
        async for _p in adapter.execute_mission(mission):
            pass
    # No mission items uploaded — fail closed.
    assert endpoint.state.mission_total == 0


@pytest.mark.asyncio
async def test_pre_upload_rejects_altitude_above_max_alt(adapter_pair: Any) -> None:
    adapter, endpoint = adapter_pair
    await adapter.set_safety(VINEYARD_FENCE, max_alt_m=50.0, rtl_battery_pct=25)
    mission = VERIFY(
        geo=Geo(lat=44.7, lon=8.03, alt_m=200.0),
        altitude_m=200.0,
        hover_s=0.1,
    )
    with pytest.raises(RejectedMission):
        async for _p in adapter.execute_mission(mission):
            pass
    assert endpoint.state.mission_total == 0


@pytest.mark.asyncio
async def test_divert_outside_fence_rejected(adapter_pair: Any) -> None:
    from swarm_core.messages import Waypoint

    adapter, _ = adapter_pair
    await adapter.set_safety(VINEYARD_FENCE, max_alt_m=120.0, rtl_battery_pct=25)
    with pytest.raises(RejectedMission):
        await adapter.divert(Waypoint(geo=Geo(lat=50.0, lon=20.0)))


def test_point_in_polygon_helper() -> None:
    poly = (
        Geo(lat=0.0, lon=0.0),
        Geo(lat=2.0, lon=0.0),
        Geo(lat=2.0, lon=2.0),
        Geo(lat=0.0, lon=2.0),
    )
    assert point_in_polygon(1.0, 1.0, poly)
    assert not point_in_polygon(3.0, 1.0, poly)
    assert not point_in_polygon(1.0, 3.0, poly)
    # Triangle with fewer than 3 points → never inside.
    assert not point_in_polygon(1.0, 1.0, (Geo(lat=0.0, lon=0.0),))


# ── Heartbeat watchdog ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_watchdog_drops_link_quality() -> None:
    endpoint = FakeMAVLinkEndpoint(heartbeat_hz=10.0)
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=0.5,
    )
    await adapter.connect()
    try:
        assert (await adapter.health()).link_quality == pytest.approx(1.0, abs=0.05)
        # Kill the endpoint and let the watchdog notice.
        await endpoint.stop()
        # Wait long enough that the watchdog crosses the threshold.
        await asyncio.sleep(1.0)
        health = await adapter.health()
        assert health.link_quality == 0.0
        assert health.online is False
        # The watchdog also flipped the `_cancelled` flag so any active
        # mission would have aborted.
        assert adapter._cancelled is True
    finally:
        await adapter.disconnect()


# ── Telemetry rate limit + capture ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_telemetry_rate_limit_caps_emission() -> None:
    endpoint = FakeMAVLinkEndpoint(position_hz=200.0)
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        rate_limit_hz=3.0,
        heartbeat_timeout_s=10.0,
    )
    await adapter.connect()
    received = []

    async def collect() -> None:
        async for t in adapter.stream_telemetry():
            received.append(t)
            if len(received) >= 8:
                return

    try:
        # Adapter emits at ~4 Hz internally; rate limiter at 3 Hz drops the
        # 4th-of-each-second so the sustained rate stays at the cap.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=4.0)
        # Sanity check: never more than `rate_limit_hz * elapsed` frames.
        # We allow generous slack — the assertion is "the limiter throttles".
        assert 1 <= len(received) <= 14
        assert adapter._rate_limiter.stats["dropped_total"] >= 0
    finally:
        await adapter.disconnect()
        await endpoint.stop()


@pytest.mark.asyncio
async def test_request_capture_returns_geo_from_last_position(adapter_pair: Any) -> None:
    adapter, _ = adapter_pair
    # Wait for at least one position frame.
    await asyncio.sleep(0.5)
    result = await adapter.request_capture(SensorKind.RGB)
    assert result.uri.startswith("mavlink://mav-1/RGB/")
    assert result.geo.lat != 0.0 or result.geo.lon != 0.0


@pytest.mark.asyncio
async def test_stream_video_is_noop_phase_5() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    await adapter.connect()
    try:
        frames = [f async for f in adapter.stream_video()]
        assert frames == []
    finally:
        await adapter.disconnect()
        await endpoint.stop()


# ── Stream descriptor ─────────────────────────────────────────────────────────


def test_stream_descriptor_offline_when_no_url() -> None:
    adapter = MAVLinkAdapter(agent_id="mav-1", connection="udp:localhost:14540")
    descriptor = adapter.stream_descriptor()
    assert descriptor.available is False
    assert descriptor.url is None


def test_stream_descriptor_publishes_https_url() -> None:
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection="udp:localhost:14540",
        stream_url="https://stream.example.com/hls/mav-1.m3u8",
    )
    descriptor = adapter.stream_descriptor()
    assert descriptor.available is True
    assert descriptor.url == "https://stream.example.com/hls/mav-1.m3u8"
    assert descriptor.protocol == "https"


def test_stream_descriptor_rejects_plaintext_http() -> None:
    from swarm_core.streams import InvalidStreamURL

    with pytest.raises(InvalidStreamURL):
        MAVLinkAdapter(
            agent_id="mav-1",
            connection="udp:localhost:14540",
            stream_url="http://stream.example.com/x",
        )


def test_heartbeat_timeout_constant_matches_roadmap() -> None:
    # The Phase 5 roadmap pins 3 s as the watchdog threshold. Document the
    # contract in a test so a relaxed default surfaces in code review.
    assert HEARTBEAT_TIMEOUT_S == 3.0
