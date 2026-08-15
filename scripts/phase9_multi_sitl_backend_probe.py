#!/usr/bin/env python3
"""Acceptance probe for the real backend + multiple PX4 SITL instances.

This script is deliberately outside the backend process. It talks to the same
Redis bus as any external perception producer would:

1. wait until all expected real adapter FleetState frames are visible;
2. publish one anomaly;
3. observe SWARM's auction award;
4. observe the winning adapter's mission progress through DONE.

For the backend's reach-aware MAVLink VERIFY path:

- `EN_ROUTE` is emitted only after mission upload, ARM, AUTO.MISSION and
  MAV_CMD_MISSION_START have succeeded;
- `ON_STATION` is emitted only after PX4 sends `MISSION_ITEM_REACHED` for the
  final waypoint;
- `DONE` is emitted only after SWARM then sends RTL and receives an accepted
  COMMAND_ACK.

Against live PX4 SITL this therefore proves the complete backend-owned dispatch,
arrival and return-command path without importing backend internals into the
probe.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import from_url
from swarm_core.messages import Anomaly, AnomalyKind, Award, FleetState, Geo, MissionProgress


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _report_step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    expected = tuple(part.strip() for part in args.expected_agents.split(",") if part.strip())
    if not expected:
        raise ValueError("--expected-agents must contain at least one agent id")

    started = time.monotonic()
    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _utc_now(),
        "redis_url": args.redis_url,
        "expected_agents": list(expected),
        "target": {"lat": args.target_lat, "lon": args.target_lon},
        "steps": [],
    }
    steps: list[dict[str, Any]] = report["steps"]
    client = from_url(args.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    deadline = time.monotonic() + args.timeout_s

    try:
        await client.ping()
        await pubsub.psubscribe(
            "swarm:fleet:state",
            "swarm:missions:award",
            "swarm:missions:progress:*",
        )

        fleet: dict[str, FleetState] = {}
        while time.monotonic() < deadline:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            if str(message.get("channel")) != "swarm:fleet:state":
                continue
            try:
                state = FleetState.model_validate_json(str(message["data"]))
            except ValueError:
                continue
            if state.agent_id in expected:
                fleet[state.agent_id] = state
            if all(agent_id in fleet for agent_id in expected):
                break

        missing = [agent_id for agent_id in expected if agent_id not in fleet]
        if missing:
            steps.append(
                _report_step(
                    "fleet_ready",
                    "fail",
                    {"missing_agents": missing, "seen_agents": sorted(fleet)},
                )
            )
            return 2, report

        steps.append(
            _report_step(
                "fleet_ready",
                "pass",
                {
                    "agents": {
                        agent_id: fleet[agent_id].model_dump(mode="json")
                        for agent_id in expected
                    }
                },
            )
        )

        anomaly = Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=args.target_lat, lon=args.target_lon),
            confidence=args.confidence,
        )
        await client.publish("swarm:anomalies", anomaly.model_dump_json())
        steps.append(
            _report_step(
                "anomaly_published",
                "pass",
                {"anomaly_id": anomaly.id, "confidence": anomaly.confidence},
            )
        )

        award: Award | None = None
        progress: list[MissionProgress] = []
        terminal: MissionProgress | None = None

        while time.monotonic() < deadline:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is None:
                continue
            channel = str(message.get("channel"))
            payload = str(message.get("data"))

            if channel == "swarm:missions:award":
                try:
                    candidate = Award.model_validate_json(payload)
                except ValueError:
                    continue
                award = candidate
                continue

            if not channel.startswith("swarm:missions:progress:"):
                continue
            try:
                frame = MissionProgress.model_validate_json(payload)
            except ValueError:
                continue
            if award is not None and frame.mission_id != award.mission_id:
                continue
            progress.append(frame)
            if frame.phase in {"DONE", "FAILED"}:
                terminal = frame
                break

        if award is None:
            steps.append(_report_step("auction", "fail", {"reason": "no award observed"}))
            return 2, report
        if award.winner_agent_id not in expected:
            steps.append(
                _report_step(
                    "auction",
                    "fail",
                    {"winner": award.winner_agent_id, "expected_agents": list(expected)},
                )
            )
            return 2, report

        steps.append(
            _report_step(
                "auction",
                "pass",
                {
                    "mission_id": award.mission_id,
                    "winner_agent_id": award.winner_agent_id,
                    "score": award.score,
                },
            )
        )

        phases = [frame.phase for frame in progress if frame.mission_id == award.mission_id]
        if terminal is None:
            steps.append(
                _report_step(
                    "mission_execution",
                    "fail",
                    {"reason": "no terminal progress", "phases": phases},
                )
            )
            return 2, report

        required_phases = {"EN_ROUTE", "ON_STATION", "DONE"}
        if terminal.phase != "DONE" or not required_phases.issubset(set(phases)):
            steps.append(
                _report_step(
                    "mission_execution",
                    "fail",
                    {
                        "terminal_phase": terminal.phase,
                        "error": terminal.error,
                        "phases": phases,
                    },
                )
            )
            return 2, report

        steps.append(
            _report_step(
                "mission_execution",
                "pass",
                {
                    "winner_agent_id": award.winner_agent_id,
                    "mission_id": award.mission_id,
                    "phases": phases,
                    "proof": (
                        "EN_ROUTE follows mission upload+ARM+AUTO.MISSION+MISSION_START; "
                        "ON_STATION follows final MISSION_ITEM_REACHED; "
                        "DONE follows RTL COMMAND_ACK"
                    ),
                },
            )
        )
        report["status"] = "pass"
        return 0, report
    except Exception as exc:
        steps.append(
            _report_step(
                "probe_error",
                "fail",
                {"type": type(exc).__name__, "message": str(exc)},
            )
        )
        return 2, report
    finally:
        await pubsub.close()
        await client.close()
        report["finished_at"] = _utc_now()
        report["duration_s"] = round(time.monotonic() - started, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    parser.add_argument("--expected-agents", default="mav-001,mav-002")
    parser.add_argument("--target-lat", type=float, default=47.3980)
    parser.add_argument("--target-lon", type=float, default=8.5460)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--timeout-s", type=float, default=120.0)
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
