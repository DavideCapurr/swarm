"""Sanity tests for the in-process MAVLink fake autopilot."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import pytest
from pymavlink import mavutil

from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint


async def _read_one(sock: socket.socket, *, deadline_s: float = 2.0) -> Any | None:
    """Decode one frame from the fake endpoint."""
    parser = mavutil.mavlink.MAVLink(None, srcSystem=254)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_s
    while loop.time() < deadline:
        try:
            data = await asyncio.wait_for(loop.sock_recv(sock, 4096), 0.5)
        except TimeoutError:
            continue
        msgs = parser.parse_buffer(data) or []
        if msgs:
            return msgs[0]
    return None


async def _recv_match(mav_conn: Any, types: set[str], *, deadline_s: float = 2.0) -> Any | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_s
    while loop.time() < deadline:
        msg = mav_conn.recv_match(blocking=False)
        if msg is not None and msg.get_type() in types:
            return msg
        await asyncio.sleep(0.02)
    return None


@pytest.mark.asyncio
async def test_fake_emits_heartbeat_to_peer() -> None:
    endpoint = FakeMAVLinkEndpoint(heartbeat_hz=10.0, position_hz=20.0)
    await endpoint.start()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setblocking(False)
        sock.bind(("127.0.0.1", 0))
        # Trigger peer discovery on the fake.
        mav = mavutil.mavlink.MAVLink(None, srcSystem=200)
        hb = mav.heartbeat_encode(
            type=mavutil.mavlink.MAV_TYPE_GCS,
            autopilot=mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            base_mode=0,
            custom_mode=0,
            system_status=mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        sock.sendto(hb.pack(mav), ("127.0.0.1", endpoint.port))
        # Drain a few frames and confirm we see a heartbeat.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 2.0
        saw_heartbeat = False
        saw_position = False
        while loop.time() < deadline and not (saw_heartbeat and saw_position):
            msg = await _read_one(sock, deadline_s=0.5)
            if msg is None:
                continue
            kind = msg.get_type()
            if kind == "HEARTBEAT":
                saw_heartbeat = True
            if kind == "GLOBAL_POSITION_INT":
                saw_position = True
        sock.close()
        assert saw_heartbeat, "fake autopilot did not emit HEARTBEAT"
        assert saw_position, "fake autopilot did not emit GLOBAL_POSITION_INT"
    finally:
        await endpoint.stop()


@pytest.mark.asyncio
async def test_fake_accepts_mission_upload() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    try:
        mav_conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{endpoint.port}",
            source_system=254,
            input=False,
        )
        # Initial HB so the fake learns our address.
        mav_conn.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        # Wait for HB back.
        await asyncio.sleep(0.5)
        # Upload 3 mission items. The fake duplicates the first request to
        # prove the client waits for requests instead of firehosing items.
        mav_conn.mav.mission_count_send(1, 1, 3)
        items = [(45.001, 10.001), (45.002, 10.002), (45.003, 10.003)]
        while True:
            request = await _recv_match(
                mav_conn,
                {"MISSION_REQUEST_INT", "MISSION_ACK"},
                deadline_s=2.0,
            )
            assert request is not None, "fake did not request/ack mission"
            if request.get_type() == "MISSION_ACK":
                assert int(request.type) == mavutil.mavlink.MAV_MISSION_ACCEPTED
                break
            seq = int(request.seq)
            mav_conn.mav.mission_item_int_send(
                1,
                1,
                seq,
                mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                0,
                1,
                0.0,
                2.0,
                0.0,
                float("nan"),
                int(items[seq][0] * 1e7),
                int(items[seq][1] * 1e7),
                60.0,
            )
        # Give the fake time to record items.
        await asyncio.sleep(0.5)
        assert len(endpoint.state.mission_items) == 3
        assert endpoint.state.mission_requests[:2] == [0, 0]
        assert endpoint.state.mission_item_receipts[:2] == [0, 0]
        # Compare with tolerance — fixed-point round-trip introduces 1e-7 noise.
        for actual, expected in zip(endpoint.state.mission_items, items, strict=True):
            assert abs(actual[0] - expected[0]) < 1e-5
            assert abs(actual[1] - expected[1]) < 1e-5
        mav_conn.close()
    finally:
        await endpoint.stop()


@pytest.mark.asyncio
async def test_fake_rejects_mission_items_sent_before_requested_sequence() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    try:
        mav_conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{endpoint.port}",
            source_system=254,
            input=False,
        )
        mav_conn.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        await asyncio.sleep(0.3)
        mav_conn.mav.mission_count_send(1, 1, 2)
        first_request = await _recv_match(mav_conn, {"MISSION_REQUEST_INT"}, deadline_s=2.0)
        assert first_request is not None
        assert int(first_request.seq) == 0
        # Wrong item while the fake is still expecting seq 0.
        mav_conn.mav.mission_item_int_send(
            1,
            1,
            1,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            0,
            1,
            0.0,
            2.0,
            0.0,
            float("nan"),
            int(45.002 * 1e7),
            int(10.002 * 1e7),
            60.0,
        )
        ack = await _recv_match(mav_conn, {"MISSION_ACK"}, deadline_s=2.0)
        assert ack is not None
        assert int(ack.type) == mavutil.mavlink.MAV_MISSION_INVALID_SEQUENCE
        assert endpoint.state.protocol_errors
        assert endpoint.state.mission_total == 0
        mav_conn.close()
    finally:
        await endpoint.stop()


@pytest.mark.asyncio
async def test_fake_acks_command_long() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    try:
        mav_conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{endpoint.port}",
            source_system=254,
            input=False,
        )
        mav_conn.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        await asyncio.sleep(0.3)
        mav_conn.mav.command_long_send(
            1,
            1,
            mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        # Spin until COMMAND_ACK arrives or 2 s elapses.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 2.0
        ack: object | None = None
        while loop.time() < deadline:
            msg = mav_conn.recv_match(blocking=False)
            if msg is not None and msg.get_type() == "COMMAND_ACK":
                ack = msg
                break
            await asyncio.sleep(0.05)
        assert ack is not None, "no COMMAND_ACK received"
        assert int(ack.command) == mavutil.mavlink.MAV_CMD_NAV_RETURN_TO_LAUNCH  # type: ignore[attr-defined]
        assert int(ack.result) == mavutil.mavlink.MAV_RESULT_ACCEPTED  # type: ignore[attr-defined]
        assert endpoint.state.rtl_triggered is True
        mav_conn.close()
    finally:
        await endpoint.stop()


@pytest.mark.asyncio
async def test_fake_records_param_set() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    try:
        mav_conn = mavutil.mavlink_connection(
            f"udpout:127.0.0.1:{endpoint.port}",
            source_system=254,
            input=False,
        )
        mav_conn.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_GCS,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            mavutil.mavlink.MAV_STATE_ACTIVE,
        )
        await asyncio.sleep(0.3)
        mav_conn.mav.param_set_send(
            1,
            1,
            b"BAT_LOW_THR".ljust(16, b"\x00")[:16],
            0.25,
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
        )
        await asyncio.sleep(0.4)
        assert "BAT_LOW_THR" in endpoint.state.params
        assert abs(endpoint.state.params["BAT_LOW_THR"] - 0.25) < 1e-5
        mav_conn.close()
    finally:
        await endpoint.stop()
