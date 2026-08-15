#!/usr/bin/env python3
"""Safely map a PX4 main output to MAVLink actuator set 1 for demo payload proof.

The presence-response light controller uses MAV_CMD_DO_SET_ACTUATOR. PX4 SITL
needs the selected PWM main function mapped to Offboard Actuator Set 1 before
that command can be confirmed. This helper refuses to overwrite any unrelated
existing function and verifies the PARAM_VALUE readback after the write.
"""

from __future__ import annotations

import argparse
import struct
import time

from pymavlink import mavutil

OFFBOARD_ACTUATOR_SET_1 = 301
DISABLED = 0


def _param_name(message: object) -> str:
    value = getattr(message, "param_id")
    if isinstance(value, bytes):
        value = value.decode(errors="ignore")
    return str(value).rstrip("\x00")


def _decode_int32(message: object) -> int:
    param_type = getattr(message, "param_type")
    if param_type != mavutil.mavlink.MAV_PARAM_TYPE_INT32:
        raise RuntimeError(f"unexpected MAV_PARAM type {param_type}")
    value = float(getattr(message, "param_value"))
    return struct.unpack("<i", struct.pack("<f", value))[0]


def _encode_int32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<i", value))[0]


def _read_param(connection: object, target_system: int, param: str, timeout_s: float) -> object:
    connection.mav.param_request_read_send(target_system, 1, param.encode(), -1)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        message = connection.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if message is not None and _param_name(message) == param:
            return message
    raise TimeoutError(f"no PARAM_VALUE for {param} on sysid={target_system}")


def _set_param(
    connection: object,
    target_system: int,
    param: str,
    value: int,
    timeout_s: float,
) -> object:
    connection.mav.param_set_send(
        target_system,
        1,
        param.encode(),
        _encode_int32(value),
        mavutil.mavlink.MAV_PARAM_TYPE_INT32,
    )
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        message = connection.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.5)
        if message is None or _param_name(message) != param:
            continue
        if _decode_int32(message) == value:
            return message
    raise TimeoutError(f"failed to confirm {param}={value} on sysid={target_system}")


def configure(endpoint: str, *, param: str, timeout_s: float) -> None:
    connection = mavutil.mavlink_connection(endpoint)
    try:
        heartbeat = connection.wait_heartbeat(timeout=timeout_s)
        if heartbeat is None:
            raise TimeoutError(f"no PX4 heartbeat on {endpoint}")
        target_system = int(connection.target_system)
        current_message = _read_param(connection, target_system, param, timeout_s)
        current = _decode_int32(current_message)
        if current not in {DISABLED, OFFBOARD_ACTUATOR_SET_1}:
            raise RuntimeError(
                f"refusing to replace active {param}={current} on sysid={target_system}"
            )
        confirmed = _set_param(
            connection,
            target_system,
            param,
            OFFBOARD_ACTUATOR_SET_1,
            timeout_s,
        )
        print(
            f"PX4 sysid={target_system} endpoint={endpoint} mapped {param}: "
            f"{current} -> {_decode_int32(confirmed)}"
        )
    finally:
        connection.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--connections",
        default="udpin:0.0.0.0:14541,udpin:0.0.0.0:14542",
        help="comma-separated pymavlink endpoints",
    )
    parser.add_argument("--output-channel", type=int, default=5)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output_channel < 1:
        raise SystemExit("--output-channel must be >= 1")
    endpoints = tuple(item.strip() for item in args.connections.split(",") if item.strip())
    if not endpoints:
        raise SystemExit("--connections must contain at least one endpoint")
    param = f"PWM_MAIN_FUNC{args.output_channel}"
    for endpoint in endpoints:
        configure(endpoint, param=param, timeout_s=args.timeout_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
