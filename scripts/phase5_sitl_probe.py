#!/usr/bin/env python3
"""PX4 SITL acceptance probe for the Phase 5 MAVLink adapter.

The script attaches to an already-running PX4 SITL endpoint and records
pass/fail evidence. It does not install or launch PX4; the runbook in
`docs/adapters/mavlink-setup.md` owns that step so humans can choose jMAVSim
or Gazebo based on their workstation.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swarm_core.messages import Geo, Telemetry
from swarm_core.missions import VERIFY

from adapters.mavlink.adapter import MAVLinkAdapter


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail or {}, "ts": _utc_now()}


async def _one_telemetry(adapter: MAVLinkAdapter, timeout_s: float) -> Telemetry:
    async def _collect() -> Telemetry:
        async for telemetry in adapter.stream_telemetry():
            return telemetry
        raise RuntimeError("telemetry stream ended before yielding")

    return await asyncio.wait_for(_collect(), timeout=timeout_s)


async def _exercise_verify(adapter: MAVLinkAdapter, lat: float, lon: float) -> list[str]:
    phases: list[str] = []
    mission = VERIFY(geo=Geo(lat=lat, lon=lon), hover_s=0.1)
    async for progress in adapter.execute_mission(mission):
        phases.append(progress.phase)
    return phases


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _utc_now(),
        "command": [Path(sys.argv[0]).name, *sys.argv[1:]],
        "connection": args.connection,
        "agent_id": args.agent_id,
        "exercise_verify": args.exercise_verify,
        "steps": [],
    }
    steps = report["steps"]
    adapter = MAVLinkAdapter(
        agent_id=args.agent_id,
        connection=args.connection,
        model=args.model,
        stream_url=args.stream_url,
        heartbeat_timeout_s=max(3.0, args.connect_timeout_s),
        connect_timeout_s=args.connect_timeout_s,
        response_timeout_s=args.response_timeout_s,
    )
    try:
        await adapter.connect()
        steps.append(_step("heartbeat", "pass", {"message": "autopilot HEARTBEAT received"}))

        health = await adapter.health()
        steps.append(
            _step(
                "health",
                "pass" if health.online and health.link_quality > 0 else "fail",
                {
                    "online": health.online,
                    "battery_pct": health.battery_pct,
                    "link_quality": health.link_quality,
                    "last_telemetry_age_s": health.last_telemetry_age_s,
                },
            )
        )

        telemetry = await _one_telemetry(adapter, args.telemetry_timeout_s)
        steps.append(
            _step(
                "telemetry",
                "pass",
                {
                    "agent_id": telemetry.agent_id,
                    "lat": telemetry.geo.lat,
                    "lon": telemetry.geo.lon,
                    "alt_m": telemetry.geo.alt_m,
                    "battery_pct": telemetry.battery_pct,
                    "link_quality": telemetry.link_quality,
                },
            )
        )

        if args.exercise_verify:
            phases = await asyncio.wait_for(
                _exercise_verify(adapter, args.verify_lat, args.verify_lon),
                timeout=args.mission_timeout_s,
            )
            steps.append(_step("verify_mission", "pass", {"phases": phases}))

        report["status"] = "pass"
        return 0, report
    except Exception as exc:
        steps.append(
            _step(
                "probe_error",
                "fail",
                {"type": type(exc).__name__, "message": str(exc)},
            )
        )
        return 2, report
    finally:
        await adapter.disconnect()
        report["finished_at"] = _utc_now()
        report["duration_s"] = round(time.monotonic() - started, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", default=os.getenv("MAVLINK_CONNECTION", "udp:localhost:14540"))
    parser.add_argument("--agent-id", default=os.getenv("MAVLINK_AGENT_ID", "mav-px4-sitl"))
    parser.add_argument("--model", default=os.getenv("MAVLINK_MODEL", "px4-x500"))
    parser.add_argument("--stream-url", default=os.getenv("MAVLINK_STREAM_URL") or None)
    parser.add_argument("--connect-timeout-s", type=float, default=5.0)
    parser.add_argument("--response-timeout-s", type=float, default=5.0)
    parser.add_argument("--telemetry-timeout-s", type=float, default=8.0)
    parser.add_argument("--mission-timeout-s", type=float, default=45.0)
    parser.add_argument("--exercise-verify", action="store_true")
    parser.add_argument("--verify-lat", type=float, default=44.7)
    parser.add_argument("--verify-lon", type=float, default=8.03)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, report = asyncio.run(run_probe(args))
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
