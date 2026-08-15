#!/usr/bin/env python3
"""PX4 SITL probe for the SWARM presence-response vertical slice.

This attaches to an already-running PX4 SITL vehicle and drives the same
production-shaped components used by the feature:

  high-confidence restricted-area presence (test input)
      -> VERIFY MissionTask
      -> MAVLinkAdapter mission execution
      -> capture-ready/on-station gate
      -> PresenceResponseOrchestrator
      -> LIGHT_ON via MAV_CMD_DO_SET_RELAY + COMMAND_ACK
      -> pre-approved speaker message as explicitly SIMULATED payload state
      -> hold
      -> STOP_MESSAGE (SIMULATED)
      -> LIGHT_OFF via MAV_CMD_DO_SET_RELAY + COMMAND_ACK
      -> mission continues to RTL and DONE

The probe does not claim a physical lamp or speaker exists. ``MAVLink ACK`` is
protocol/SITL proof only. Audio remains simulated until a real payload transport
is configured.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swarm_core.messages import Anomaly, AnomalyKind, Event, Geo, MissionProgress
from swarm_core.missions import VERIFY

from adapters.base import AdapterRegistry
from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.payload import MAVLinkPayloadController
from adapters.payload import PayloadControllerRegistry
from orchestrator.swarm_orchestrator.presence import PresenceResponseOrchestrator


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


class EvidenceBus:
    """Minimal Bus implementation that retains every frame for the report."""

    def __init__(self) -> None:
        self.published: list[tuple[str, str]] = []

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def publish(self, topic: str, payload: str) -> None:
        self.published.append((topic, payload))

    async def subscribe(self, _topic_pattern: str) -> AsyncIterator[tuple[str, str]]:
        if False:
            yield "", ""


def _payload_events(bus: EvidenceBus) -> list[Event]:
    return [
        Event.model_validate_json(payload)
        for topic, payload in bus.published
        if topic == "swarm:events:payload"
    ]


def _mission_progress(bus: EvidenceBus) -> list[MissionProgress]:
    return [
        MissionProgress.model_validate_json(payload)
        for topic, payload in bus.published
        if topic.startswith("swarm:missions:progress:")
    ]


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    started = time.monotonic()
    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _utc_now(),
        "command": [Path(sys.argv[0]).name, *sys.argv[1:]],
        "connection": args.connection,
        "agent_id": args.agent_id,
        "proof_level": {
            "flight": "PX4 SITL",
            "light": "MAVLink COMMAND_ACK only; no physical lamp claimed",
            "speaker": "SIMULATED PAYLOAD",
        },
        "steps": [],
    }
    steps: list[dict[str, Any]] = report["steps"]

    bus = EvidenceBus()
    registry = AdapterRegistry()
    payload_registry = PayloadControllerRegistry()
    adapter = MAVLinkAdapter(
        agent_id=args.agent_id,
        connection=args.connection,
        model=args.model,
        connect_timeout_s=args.connect_timeout_s,
        response_timeout_s=args.response_timeout_s,
        heartbeat_timeout_s=max(3.0, args.connect_timeout_s),
    )
    payload = MAVLinkPayloadController(
        adapter=adapter,
        light_relay_index=args.light_relay_index,
        simulate_speaker=True,
    )
    registry.register(adapter)
    payload_registry.register(payload)
    orchestrator = PresenceResponseOrchestrator(
        bus=bus,
        registry=registry,
        payload_registry=payload_registry,
        presence_min_confidence=args.confidence_threshold,
        presence_hold_s=args.hold_s,
        presence_ready_progress_pct=args.ready_progress_pct,
    )

    mission = VERIFY(
        geo=Geo(lat=args.verify_lat, lon=args.verify_lon, alt_m=args.verify_alt_m),
        hover_s=args.verify_hover_s,
        altitude_m=args.verify_alt_m,
        priority=99,
    )
    anomaly = Anomaly(
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=args.verify_lat, lon=args.verify_lon, alt_m=0.0),
        confidence=args.anomaly_confidence,
    )
    orchestrator._mission_anomalies[mission.id] = anomaly

    try:
        await adapter.connect()
        health = await adapter.health()
        steps.append(
            _step(
                "connect",
                "pass" if health.online else "fail",
                {
                    "online": health.online,
                    "battery_pct": health.battery_pct,
                    "link_quality": health.link_quality,
                },
            )
        )

        await asyncio.wait_for(
            orchestrator._run_mission(
                args.agent_id,
                adapter,
                mission,
                is_verify=True,
            ),
            timeout=args.mission_timeout_s,
        )

        progress = _mission_progress(bus)
        phases = [item.phase for item in progress]
        steps.append(
            _step(
                "verify_mission",
                "pass" if phases and phases[-1] == "DONE" else "fail",
                {"phases": phases, "mission_id": mission.id},
            )
        )

        events = _payload_events(bus)
        bodies = [event.body for event in events]
        light_on_ack = any("light on · MAVLink ACK" in body for body in bodies)
        light_off_ack = any("light off · MAVLink ACK" in body for body in bodies)
        speaker_on_sim = any(
            "restricted-area message active · SIMULATED PAYLOAD" in body
            for body in bodies
        )
        speaker_off_sim = any(
            "restricted-area message stopped · SIMULATED PAYLOAD" in body
            for body in bodies
        )
        payload_failed = any("payload action" in body and "failed" in body for body in bodies)

        steps.append(
            _step(
                "light_on",
                "pass" if light_on_ack and not payload_failed else "fail",
                {
                    "command": "MAV_CMD_DO_SET_RELAY",
                    "relay_index": args.light_relay_index,
                    "ack": light_on_ack,
                    "physical_lamp": False,
                },
            )
        )
        steps.append(
            _step(
                "speaker_message",
                "pass" if speaker_on_sim and speaker_off_sim else "fail",
                {
                    "message_id": "restricted_area",
                    "execution": "SIMULATED PAYLOAD",
                    "started": speaker_on_sim,
                    "stopped": speaker_off_sim,
                },
            )
        )
        steps.append(
            _step(
                "light_off",
                "pass" if light_off_ack and not payload_failed else "fail",
                {
                    "command": "MAV_CMD_DO_SET_RELAY",
                    "relay_index": args.light_relay_index,
                    "ack": light_off_ack,
                    "physical_lamp": False,
                },
            )
        )
        steps.append(
            _step(
                "presence_sequence",
                "pass"
                if light_on_ack and speaker_on_sim and speaker_off_sim and light_off_ack
                else "fail",
                {"event_bodies": bodies},
            )
        )

        if all(step["status"] == "pass" for step in steps):
            report["status"] = "pass"
            return 0, report
        return 2, report
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
    parser.add_argument(
        "--connection",
        default=os.getenv("MAVLINK_CONNECTION", "udp:localhost:14540"),
    )
    parser.add_argument(
        "--agent-id",
        default=os.getenv("MAVLINK_AGENT_ID", "mav-px4-sitl"),
    )
    parser.add_argument("--model", default=os.getenv("MAVLINK_MODEL", "px4-x500"))
    parser.add_argument("--verify-lat", type=float, default=44.7)
    parser.add_argument("--verify-lon", type=float, default=8.03)
    parser.add_argument("--verify-alt-m", type=float, default=40.0)
    parser.add_argument("--verify-hover-s", type=float, default=0.1)
    parser.add_argument("--anomaly-confidence", type=float, default=0.94)
    parser.add_argument("--confidence-threshold", type=float, default=0.75)
    parser.add_argument("--ready-progress-pct", type=float, default=85.0)
    parser.add_argument("--hold-s", type=float, default=2.0)
    parser.add_argument("--light-relay-index", type=int, default=0)
    parser.add_argument("--connect-timeout-s", type=float, default=5.0)
    parser.add_argument("--response-timeout-s", type=float, default=5.0)
    parser.add_argument("--mission-timeout-s", type=float, default=60.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    if not 0.0 <= args.anomaly_confidence <= 1.0:
        parser.error("--anomaly-confidence must be in [0, 1]")
    if not 0.0 <= args.confidence_threshold <= 1.0:
        parser.error("--confidence-threshold must be in [0, 1]")
    if args.light_relay_index < 0:
        parser.error("--light-relay-index must be >= 0")
    if args.hold_s < 0:
        parser.error("--hold-s must be >= 0")
    return args


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
