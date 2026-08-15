#!/usr/bin/env python3
"""Acceptance probe for bounded payload response on the real MAVLink runtime.

The probe is deliberately external to the backend. It uses only Redis topics,
like a perception producer / audit observer would:

1. wait for all expected MAVLink fleet states;
2. publish a high-confidence INTRUSION anomaly;
3. observe SWARM's normal fleet award;
4. observe VERIFY progress to the reach-aware ON_STATION gate;
5. observe the bounded payload event sequence;
6. require cleanup before mission DONE.

A passing light event requires the configured PX4 PWM output to have been
observed in the requested state. Speaker events must explicitly report
``SIMULATED PAYLOAD``. This keeps flight-controller output proof and demo-only
side effects separate in the captured evidence.
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
from swarm_core.messages import (
    Anomaly,
    AnomalyKind,
    Award,
    Event,
    FleetState,
    Geo,
    MissionProgress,
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    expected = tuple(
        part.strip() for part in args.expected_agents.split(",") if part.strip()
    )
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
            "swarm:events:payload",
        )

        fleet: dict[str, FleetState] = {}
        while time.monotonic() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
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
                _step(
                    "fleet_ready",
                    "fail",
                    {"missing_agents": missing, "seen_agents": sorted(fleet)},
                )
            )
            return 2, report

        steps.append(
            _step(
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
            _step(
                "anomaly_published",
                "pass",
                {"anomaly_id": anomaly.id, "confidence": anomaly.confidence},
            )
        )

        award: Award | None = None
        progress: list[MissionProgress] = []
        payload_events: list[Event] = []
        sequence: list[dict[str, Any]] = []
        terminal: MissionProgress | None = None

        while time.monotonic() < deadline:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=1.0,
            )
            if message is None:
                continue
            channel = str(message.get("channel"))
            payload = str(message.get("data"))
            observed_at = _utc_now()

            if channel == "swarm:missions:award":
                try:
                    candidate = Award.model_validate_json(payload)
                except ValueError:
                    continue
                award = candidate
                sequence.append(
                    {
                        "kind": "award",
                        "ts": observed_at,
                        "mission_id": candidate.mission_id,
                        "agent_id": candidate.winner_agent_id,
                    }
                )
                continue

            if channel == "swarm:events:payload":
                try:
                    event = Event.model_validate_json(payload)
                except ValueError:
                    continue
                if event.anomaly_id != anomaly.id:
                    continue
                if award is not None and event.mission_id != award.mission_id:
                    continue
                payload_events.append(event)
                sequence.append(
                    {
                        "kind": "payload",
                        "ts": observed_at,
                        "mission_id": event.mission_id,
                        "agent_id": event.agent_id,
                        "body": event.body,
                    }
                )
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
            sequence.append(
                {
                    "kind": "progress",
                    "ts": observed_at,
                    "mission_id": frame.mission_id,
                    "phase": frame.phase,
                }
            )
            if frame.phase in {"DONE", "FAILED"}:
                terminal = frame
                break

        if award is None:
            steps.append(_step("auction", "fail", {"reason": "no award observed"}))
            return 2, report
        if award.winner_agent_id not in expected:
            steps.append(
                _step(
                    "auction",
                    "fail",
                    {
                        "winner": award.winner_agent_id,
                        "expected_agents": list(expected),
                    },
                )
            )
            return 2, report

        steps.append(
            _step(
                "auction",
                "pass",
                {
                    "mission_id": award.mission_id,
                    "winner_agent_id": award.winner_agent_id,
                    "score": award.score,
                },
            )
        )

        phases = [
            frame.phase
            for frame in progress
            if frame.mission_id == award.mission_id
        ]
        if terminal is None:
            steps.append(
                _step(
                    "mission_execution",
                    "fail",
                    {"reason": "no terminal progress", "phases": phases},
                )
            )
            return 2, report

        required_phases = {"EN_ROUTE", "ON_STATION", "DONE"}
        if terminal.phase != "DONE" or not required_phases.issubset(set(phases)):
            steps.append(
                _step(
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

        expected_bodies = (
            "light on · PX4 OUTPUT CONFIRMED",
            "restricted-area message active · SIMULATED PAYLOAD",
            "restricted-area message stopped · SIMULATED PAYLOAD",
            "light off · PX4 OUTPUT CONFIRMED",
        )
        bodies = [event.body for event in payload_events]
        missing_bodies = [
            expected_body
            for expected_body in expected_bodies
            if not any(expected_body in body for body in bodies)
        ]
        if missing_bodies:
            steps.append(
                _step(
                    "payload_response",
                    "fail",
                    {"missing": missing_bodies, "observed": bodies},
                )
            )
            return 2, report

        on_station_index = next(
            (
                index
                for index, item in enumerate(sequence)
                if item["kind"] == "progress" and item.get("phase") == "ON_STATION"
            ),
            None,
        )
        first_payload_index = next(
            (
                index
                for index, item in enumerate(sequence)
                if item["kind"] == "payload"
            ),
            None,
        )
        light_off_index = next(
            (
                index
                for index, item in enumerate(sequence)
                if item["kind"] == "payload"
                and "light off · PX4 OUTPUT CONFIRMED" in str(item.get("body", ""))
            ),
            None,
        )
        done_index = next(
            (
                index
                for index, item in enumerate(sequence)
                if item["kind"] == "progress" and item.get("phase") == "DONE"
            ),
            None,
        )
        order_ok = (
            on_station_index is not None
            and first_payload_index is not None
            and light_off_index is not None
            and done_index is not None
            and on_station_index < first_payload_index <= light_off_index < done_index
        )
        if not order_ok:
            steps.append(
                _step(
                    "payload_order",
                    "fail",
                    {"sequence": sequence},
                )
            )
            return 2, report

        steps.append(
            _step(
                "payload_response",
                "pass",
                {
                    "winner_agent_id": award.winner_agent_id,
                    "mission_id": award.mission_id,
                    "events": [
                        event.model_dump(mode="json") for event in payload_events
                    ],
                    "proof": (
                        "light ON/OFF events require the configured PX4 PWM output "
                        "to be observed in the requested state; speaker events remain "
                        "explicitly simulated"
                    ),
                },
            )
        )
        steps.append(
            _step(
                "mission_execution",
                "pass",
                {
                    "phases": phases,
                    "sequence": sequence,
                    "proof": (
                        "ON_STATION follows final MISSION_ITEM_REACHED; "
                        "payload cleanup completes before DONE/RTL closure"
                    ),
                },
            )
        )
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
