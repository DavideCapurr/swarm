"""In-process UDP MAVLink endpoint — the test fixture for the MAVLink adapter.

`FakeMAVLinkEndpoint` pretends to be a PX4 autopilot. It binds a UDP socket on
`127.0.0.1`, encodes MAVLink frames with `pymavlink`, and responds to the
messages the SwarmOS adapter sends:

  - HEARTBEAT          → mirrors back HEARTBEAT @ 2 Hz, learns the peer
                         (sysid/compid + UDP address) from the first inbound
                         packet.
  - MISSION_COUNT      → requests items via MISSION_REQUEST_INT, duplicates
                         the first request, then emits final MISSION_ACK.
  - MISSION_ITEM_INT   → accepted only when it matches the outstanding
                         request; out-of-order shortcuts are rejected.
  - COMMAND_LONG/INT   → emits COMMAND_ACK(MAV_RESULT_ACCEPTED), unless a
                         test config asks it to drop/reject the ACK.
  - SET_MODE           → emits a HEARTBEAT carrying the new custom_mode.
  - PARAM_SET          → records the parameter and echoes PARAM_VALUE.

It also emits, on a steady cadence:

  - HEARTBEAT                            @  1 Hz
  - GLOBAL_POSITION_INT (sim'd lat/lon)  @ 10 Hz
  - SYS_STATUS                           @  1 Hz
  - MISSION_CURRENT (when mission live)  @  1 Hz

Why an in-process fake (not PX4 SITL)? SITL needs Gazebo + a multi-gigabyte
runtime and is the wrong shape for `make test`. The fake covers the MAVLink
wire protocol — which is exactly what the adapter speaks — so the conformance
suite runs in milliseconds in CI. SITL remains the hardware-bench acceptance
gate (see `docs/adapters/mavlink-setup.md`).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import socket
from dataclasses import dataclass, field
from typing import Any

from pymavlink import mavutil

logger = logging.getLogger("mavlink.fake")


@dataclass
class FakeAutopilotState:
    """Mutable state the fake autopilot exposes to tests for assertions."""

    armed: bool = False
    custom_mode: int = 0
    base_mode: int = 0
    mission_items: list[tuple[float, float, float]] = field(default_factory=list)
    mission_item_receipts: list[int] = field(default_factory=list)
    mission_requests: list[int] = field(default_factory=list)
    mission_current: int = 0
    mission_total: int = 0
    params: dict[str, float] = field(default_factory=dict)
    fence_points: list[tuple[float, float]] = field(default_factory=list)
    fence_enabled: bool = False
    rtl_triggered: bool = False
    set_mode_calls: int = 0
    command_calls: list[int] = field(default_factory=list)
    protocol_errors: list[str] = field(default_factory=list)
    battery_pct: float = 87.0
    geo: tuple[float, float, float] = (44.7000, 8.0300, 0.0)  # lat, lon, alt_m AGL


class FakeMAVLinkEndpoint:
    """In-process UDP MAVLink server. One per test."""

    def __init__(
        self,
        *,
        system_id: int = 1,
        component_id: int = 1,
        heartbeat_hz: float = 1.0,
        position_hz: float = 10.0,
        emit_heartbeat: bool = True,
        send_mission_ack: bool = True,
        mission_ack_result: int | None = None,
        command_ack_results: dict[int, int] | None = None,
        drop_command_acks: set[int] | None = None,
        send_param_value: bool = True,
        duplicate_first_mission_request: bool = True,
    ) -> None:
        self._sysid = system_id
        self._compid = component_id
        # Bind first so the caller can `await connect()` and immediately know
        # the port via `.port`.
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.port = int(self._sock.getsockname()[1])
        self._peer: tuple[str, int] | None = None
        self._heartbeat_period = 1.0 / heartbeat_hz
        self._position_period = 1.0 / position_hz
        self._emit_heartbeat = emit_heartbeat
        self._emit_mission_ack = send_mission_ack
        self._mission_ack_result = mission_ack_result
        self._command_ack_results = command_ack_results or {}
        self._drop_command_acks = drop_command_acks or set()
        self._send_param_value = send_param_value
        self._duplicate_first_mission_request = duplicate_first_mission_request
        self._tasks: list[asyncio.Task[None]] = []
        self._mav = mavutil.mavlink.MAVLink(None, srcSystem=system_id, srcComponent=component_id)
        self.state = FakeAutopilotState()
        self._running = False
        self._mission_expected = 0
        self._mission_requested_seq: int | None = None
        self._mission_duplicate_pending = False
        self._mission_items_by_seq: dict[int, tuple[float, float, float]] = {}

    # ── lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._rx_loop()),
            loop.create_task(self._heartbeat_loop()),
            loop.create_task(self._position_loop()),
            loop.create_task(self._sys_status_loop()),
        ]

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await t
        self._tasks.clear()
        with contextlib.suppress(OSError):  # pragma: no cover — defensive
            self._sock.close()

    # ── tx helpers ────────────────────────────────────────────────────────────

    def _send(self, msg: Any) -> None:
        if self._peer is None:
            return
        try:
            data = msg.pack(self._mav)
            self._sock.sendto(data, self._peer)
        except OSError:  # pragma: no cover — peer disconnected mid-send
            pass

    def _make_heartbeat(self) -> Any:
        m = mavutil.mavlink
        return self._mav.heartbeat_encode(
            type=m.MAV_TYPE_QUADROTOR,
            autopilot=m.MAV_AUTOPILOT_PX4,
            base_mode=self.state.base_mode,
            custom_mode=self.state.custom_mode,
            system_status=m.MAV_STATE_ACTIVE,
        )

    # ── periodic emitters ────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        try:
            while self._running:
                if self._emit_heartbeat:
                    self._send(self._make_heartbeat())
                await asyncio.sleep(self._heartbeat_period)
        except asyncio.CancelledError:
            raise

    async def _position_loop(self) -> None:
        try:
            t = 0
            while self._running:
                lat, lon, alt = self.state.geo
                msg = self._mav.global_position_int_encode(
                    time_boot_ms=t,
                    lat=int(lat * 1e7),
                    lon=int(lon * 1e7),
                    alt=int(alt * 1000),
                    relative_alt=int(alt * 1000),
                    vx=0,
                    vy=0,
                    vz=0,
                    hdg=0,
                )
                self._send(msg)
                # If a mission is live, emit MISSION_CURRENT.
                if self.state.mission_total > 0:
                    cur = self._mav.mission_current_encode(seq=self.state.mission_current)
                    self._send(cur)
                t += int(self._position_period * 1000)
                await asyncio.sleep(self._position_period)
        except asyncio.CancelledError:
            raise

    async def _sys_status_loop(self) -> None:
        try:
            while self._running:
                msg = self._mav.sys_status_encode(
                    onboard_control_sensors_present=0,
                    onboard_control_sensors_enabled=0,
                    onboard_control_sensors_health=0,
                    load=200,
                    voltage_battery=int(self.state.battery_pct / 100.0 * 16800),
                    current_battery=-1,
                    battery_remaining=int(self.state.battery_pct),
                    drop_rate_comm=0,
                    errors_comm=0,
                    errors_count1=0,
                    errors_count2=0,
                    errors_count3=0,
                    errors_count4=0,
                )
                self._send(msg)
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            raise

    # ── rx ────────────────────────────────────────────────────────────────────

    async def _rx_loop(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while self._running:
                try:
                    data, peer = await loop.sock_recvfrom(self._sock, 2048)
                except OSError:
                    return
                self._peer = peer
                try:
                    msgs = self._mav.parse_buffer(data) or []
                except Exception:
                    msgs = []
                for msg in msgs:
                    self._handle(msg)
        except asyncio.CancelledError:
            raise

    def _handle(self, msg: Any) -> None:
        m = mavutil.mavlink
        kind = msg.get_type()
        if kind == "HEARTBEAT":
            return
        if kind == "MISSION_COUNT":
            count = int(getattr(msg, "count", 0))
            self.state.mission_items = []
            self.state.mission_item_receipts = []
            self.state.mission_requests = []
            self._mission_expected = count
            self._mission_items_by_seq = {}
            self._mission_requested_seq = None
            self._mission_duplicate_pending = self._duplicate_first_mission_request and count > 0
            if count > 0:
                self._request_mission_seq(0)
            else:
                self._send_mission_ack(m.MAV_MISSION_ACCEPTED)
            return
        if kind in {"MISSION_ITEM_INT", "MISSION_ITEM"}:
            seq = int(getattr(msg, "seq", 0))
            if self._mission_requested_seq is None:
                self._reject_mission(f"mission item {seq} arrived before any request")
                return
            if seq != self._mission_requested_seq:
                self._reject_mission(
                    f"mission item {seq} arrived while expecting {self._mission_requested_seq}"
                )
                return
            if kind == "MISSION_ITEM_INT":
                lat = float(getattr(msg, "x", 0)) / 1e7
                lon = float(getattr(msg, "y", 0)) / 1e7
            else:
                lat = float(getattr(msg, "x", 0.0))
                lon = float(getattr(msg, "y", 0.0))
            alt = float(getattr(msg, "z", 0.0))
            self.state.mission_item_receipts.append(seq)
            self._mission_items_by_seq[seq] = (lat, lon, alt)
            if self._mission_duplicate_pending:
                self._mission_duplicate_pending = False
                self._request_mission_seq(seq)
                return
            next_seq = self._next_missing_mission_seq()
            if next_seq is not None:
                self._request_mission_seq(next_seq)
                return
            self.state.mission_items = [
                self._mission_items_by_seq[i] for i in range(self._mission_expected)
            ]
            self.state.mission_total = len(self.state.mission_items)
            self.state.mission_current = 0
            self._mission_requested_seq = None
            self._send_mission_ack(m.MAV_MISSION_ACCEPTED)
            return
        if kind == "COMMAND_LONG":
            command_id = int(getattr(msg, "command", 0))
            self.state.command_calls.append(command_id)
            result = self._command_ack_results.get(command_id, m.MAV_RESULT_ACCEPTED)
            if result == m.MAV_RESULT_ACCEPTED and command_id == m.MAV_CMD_NAV_RETURN_TO_LAUNCH:
                self.state.rtl_triggered = True
            if result == m.MAV_RESULT_ACCEPTED and command_id == m.MAV_CMD_DO_FENCE_ENABLE:
                self.state.fence_enabled = bool(int(getattr(msg, "param1", 0)))
            if result == m.MAV_RESULT_ACCEPTED and command_id == m.MAV_CMD_COMPONENT_ARM_DISARM:
                self.state.armed = bool(int(getattr(msg, "param1", 0)))
            if (
                result == m.MAV_RESULT_ACCEPTED
                and command_id == m.MAV_CMD_MISSION_START
                and self.state.mission_total > 0
            ):
                # Pretend the autopilot has begun executing the mission.
                self.state.mission_current = 0
                # Auto-advance so tests don't need to drive the cursor.
                self._tasks.append(asyncio.create_task(self._advance_mission_loop()))
            if command_id not in self._drop_command_acks:
                self._send(self._mav.command_ack_encode(command_id, result))
            return
        if kind == "SET_MODE":
            self.state.set_mode_calls += 1
            self.state.base_mode = int(getattr(msg, "base_mode", 0))
            self.state.custom_mode = int(getattr(msg, "custom_mode", 0))
            self._send(self._make_heartbeat())
            return
        if kind == "PARAM_SET":
            pid = getattr(msg, "param_id", b"")
            if isinstance(pid, bytes):
                pid = pid.rstrip(b"\x00").decode("ascii", errors="replace")
            self.state.params[str(pid)] = float(getattr(msg, "param_value", 0.0))
            if self._send_param_value:
                self._send(
                    self._mav.param_value_encode(
                        str(pid).encode("ascii").ljust(16, b"\x00")[:16],
                        float(getattr(msg, "param_value", 0.0)),
                        int(getattr(msg, "param_type", m.MAV_PARAM_TYPE_REAL32)),
                        len(self.state.params),
                        max(0, len(self.state.params) - 1),
                    )
                )
            return
        if kind == "FENCE_POINT":
            lat = float(getattr(msg, "lat", 0.0))
            lon = float(getattr(msg, "lng", 0.0))
            self.state.fence_points.append((lat, lon))
            return

    def _request_mission_seq(self, seq: int) -> None:
        self._mission_requested_seq = seq
        self.state.mission_requests.append(seq)
        self._send(self._mav.mission_request_int_encode(self._sysid, self._compid, seq))

    def _next_missing_mission_seq(self) -> int | None:
        for seq in range(self._mission_expected):
            if seq not in self._mission_items_by_seq:
                return seq
        return None

    def _reject_mission(self, reason: str) -> None:
        self.state.protocol_errors.append(reason)
        self._send_mission_ack(mavutil.mavlink.MAV_MISSION_INVALID_SEQUENCE)
        self._mission_requested_seq = None

    def _send_mission_ack(self, default_result: int) -> None:
        if not self._emit_mission_ack:
            return
        result = self._mission_ack_result
        if result is None:
            result = default_result
        self._send(self._mav.mission_ack_encode(self._sysid, self._compid, result))

    async def _advance_mission_loop(self) -> None:
        """Tick the MISSION_CURRENT cursor so missions finish on their own."""
        try:
            while self._running and self.state.mission_total > 0:
                if self.state.mission_current >= self.state.mission_total - 1:
                    return
                await asyncio.sleep(0.1)
                self.state.mission_current += 1
        except asyncio.CancelledError:
            raise

    # ── test-only helpers ────────────────────────────────────────────────────

    def advance_mission_to_completion(self) -> None:
        """Skip the in-flight phase so a unit test sees the DONE phase quickly."""
        if self.state.mission_total > 0:
            self.state.mission_current = self.state.mission_total - 1


__all__ = ("FakeAutopilotState", "FakeMAVLinkEndpoint")
