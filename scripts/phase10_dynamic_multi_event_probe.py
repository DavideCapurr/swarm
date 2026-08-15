#!/usr/bin/env python3
"""Acceptance probe for changing-condition coordination across live MAVLink units.

The probe talks only to the Redis bus. It proves the behavior that matters for
SWARM's multi-agent demo without importing backend/orchestrator internals:

1. wait for two or more fleet units;
2. publish event A and observe its fleet-level award + EN_ROUTE progress;
3. wait until the winning unit is visibly airborne in canonical FleetState;
4. while mission A is still active, publish event B;
5. require event B to be awarded to a *different* still-available unit;
6. require both missions to finish successfully.

A pass therefore proves concurrent fleet reallocation under a changing world:
the second event changes the fleet plan while the first response is still in
flight. It does not claim same-aircraft preemption or mid-flight diversion.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import from_url
from swarm_core.messages import Anomaly, AnomalyKind, Award, FleetState, Geo, MissionProgress


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    expected = tuple(part.strip() for part in args.expected_agents.split(",") if part.strip())
    if len(expected) < 2:
        raise ValueError("--expected-agents must contain at least two agent ids")

    started = time.monotonic()
    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _utc_now(),
        "expected_agents": list(expected),
        "event_a_target": {"lat": args.event_a_lat, "lon": args.event_a_lon},
        "event_b_target": {"lat": args.event_b_lat, "lon": args.event_b_lon},
        "steps": [],
    }
    steps: list[dict[str, Any]] = report["steps"]

    client = from_url(args.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    deadline = time.monotonic() + args.timeout_s

    fleet: dict[str, FleetState] = {}
    awards: list[Award] = []
    progress_by_mission: dict[str, list[MissionProgress]] = {}
    terminal_at: dict[str, float] = {}

    async def _next_message() -> tuple[str, str] | None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        message = await pubsub.get_message(
            ignore_subscribe_messages=True,
            timeout=min(1.0, remaining),
        )
        if message is None:
            return None
        return str(message.get("channel")), str(message.get("data"))

    def _consume(channel: str, payload: str) -> None:
        if channel == "swarm:fleet:state":
            try:
                state = FleetState.model_validate_json(payload)
            except ValueError:
                return
            if state.agent_id in expected:
                fleet[state.agent_id] = state
            return

        if channel == "swarm:missions:award":
            try:
                award = Award.model_validate_json(payload)
            except ValueError:
                return
            if all(existing.mission_id != award.mission_id for existing in awards):
                awards.append(award)
            return

        if channel.startswith("swarm:missions:progress:"):
            try:
                frame = MissionProgress.model_validate_json(payload)
            except ValueError:
                return
            frames = progress_by_mission.setdefault(frame.mission_id, [])
            frames.append(frame)
            if frame.phase in {"DONE", "FAILED"}:
                terminal_at.setdefault(frame.mission_id, time.monotonic())

    async def _pump_until(predicate: Callable[[], bool]) -> bool:
        while time.monotonic() < deadline:
            if predicate():
                return True
            item = await _next_message()
            if item is not None:
                _consume(*item)
        return predicate()

    try:
        await client.ping()
        await pubsub.psubscribe(
            "swarm:fleet:state",
            "swarm:missions:award",
            "swarm:missions:progress:*",
        )

        ready = await _pump_until(lambda: all(agent_id in fleet for agent_id in expected))
        if not ready:
            steps.append(
                _step(
                    "fleet_ready",
                    "fail",
                    {"seen": sorted(fleet), "missing": sorted(set(expected) - set(fleet))},
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

        event_a = Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=args.event_a_lat, lon=args.event_a_lon),
            confidence=args.event_a_confidence,
        )
        await client.publish("swarm:anomalies", event_a.model_dump_json())
        steps.append(
            _step(
                "event_a_published",
                "pass",
                {"anomaly_id": event_a.id, "confidence": event_a.confidence},
            )
        )

        first_awarded = await _pump_until(lambda: len(awards) >= 1)
        if not first_awarded:
            steps.append(_step("event_a_award", "fail", {"reason": "no award"}))
            return 2, report

        award_a = awards[0]
        if award_a.winner_agent_id not in expected:
            steps.append(
                _step(
                    "event_a_award",
                    "fail",
                    {"winner": award_a.winner_agent_id, "expected": list(expected)},
                )
            )
            return 2, report

        first_en_route = await _pump_until(
            lambda: any(
                frame.phase == "EN_ROUTE"
                for frame in progress_by_mission.get(award_a.mission_id, [])
            )
        )
        if not first_en_route:
            steps.append(
                _step(
                    "event_a_en_route",
                    "fail",
                    {"mission_id": award_a.mission_id},
                )
            )
            return 2, report

        winner_airborne = await _pump_until(
            lambda: (
                award_a.winner_agent_id in fleet
                and fleet[award_a.winner_agent_id].fsm_state.value == "EN_ROUTE"
            )
        )
        if not winner_airborne:
            steps.append(
                _step(
                    "event_a_airborne",
                    "fail",
                    {
                        "winner": award_a.winner_agent_id,
                        "last_state": (
                            fleet[award_a.winner_agent_id].model_dump(mode="json")
                            if award_a.winner_agent_id in fleet
                            else None
                        ),
                    },
                )
            )
            return 2, report

        if award_a.mission_id in terminal_at:
            steps.append(
                _step(
                    "overlap_gate",
                    "fail",
                    {"reason": "mission A already terminal before event B"},
                )
            )
            return 2, report

        steps.append(
            _step(
                "event_a_active",
                "pass",
                {
                    "mission_id": award_a.mission_id,
                    "winner": award_a.winner_agent_id,
                    "fleet_state": fleet[award_a.winner_agent_id].fsm_state.value,
                },
            )
        )

        event_b_published_at = time.monotonic()
        event_b = Anomaly(
            kind=AnomalyKind.HEAT_SPOT,
            geo=Geo(lat=args.event_b_lat, lon=args.event_b_lon),
            confidence=args.event_b_confidence,
        )
        await client.publish("swarm:anomalies", event_b.model_dump_json())
        steps.append(
            _step(
                "event_b_published_while_a_active",
                "pass",
                {
                    "anomaly_id": event_b.id,
                    "mission_a_id": award_a.mission_id,
                    "mission_a_winner": award_a.winner_agent_id,
                },
            )
        )

        second_awarded = await _pump_until(lambda: len(awards) >= 2)
        if not second_awarded:
            steps.append(_step("event_b_award", "fail", {"reason": "no second award"}))
            return 2, report

        award_b = awards[1]
        if award_b.winner_agent_id == award_a.winner_agent_id:
            steps.append(
                _step(
                    "event_b_reallocation",
                    "fail",
                    {
                        "reason": "second event reused already-airborne winner",
                        "winner_a": award_a.winner_agent_id,
                        "winner_b": award_b.winner_agent_id,
                    },
                )
            )
            return 2, report
        if award_b.winner_agent_id not in expected:
            steps.append(
                _step(
                    "event_b_reallocation",
                    "fail",
                    {"winner_b": award_b.winner_agent_id, "expected": list(expected)},
                )
            )
            return 2, report
        if award_a.mission_id in terminal_at:
            steps.append(
                _step(
                    "event_b_reallocation",
                    "fail",
                    {"reason": "mission A finished before second award"},
                )
            )
            return 2, report

        steps.append(
            _step(
                "event_b_reallocation",
                "pass",
                {
                    "mission_a": {
                        "mission_id": award_a.mission_id,
                        "winner": award_a.winner_agent_id,
                        "still_active": True,
                    },
                    "mission_b": {
                        "mission_id": award_b.mission_id,
                        "winner": award_b.winner_agent_id,
                    },
                    "proof": (
                        "winner A was EN_ROUTE and non-eligible; second event was awarded "
                        "to a different available fleet unit before mission A terminated"
                    ),
                },
            )
        )

        both_terminal = await _pump_until(
            lambda: award_a.mission_id in terminal_at and award_b.mission_id in terminal_at
        )
        if not both_terminal:
            steps.append(
                _step(
                    "concurrent_completion",
                    "fail",
                    {
                        "terminal_missions": sorted(terminal_at),
                        "expected": [award_a.mission_id, award_b.mission_id],
                    },
                )
            )
            return 2, report

        phases_a = [frame.phase for frame in progress_by_mission[award_a.mission_id]]
        phases_b = [frame.phase for frame in progress_by_mission[award_b.mission_id]]
        if phases_a[-1] != "DONE" or phases_b[-1] != "DONE":
            steps.append(
                _step(
                    "concurrent_completion",
                    "fail",
                    {"phases_a": phases_a, "phases_b": phases_b},
                )
            )
            return 2, report

        steps.append(
            _step(
                "concurrent_completion",
                "pass",
                {
                    "mission_a": {
                        "winner": award_a.winner_agent_id,
                        "phases": phases_a,
                    },
                    "mission_b": {
                        "winner": award_b.winner_agent_id,
                        "phases": phases_b,
                    },
                    "event_b_to_a_terminal_s": round(
                        terminal_at[award_a.mission_id] - event_b_published_at, 3
                    ),
                    "event_b_to_b_terminal_s": round(
                        terminal_at[award_b.mission_id] - event_b_published_at, 3
                    ),
                },
            )
        )

        report["status"] = "pass"
        report["mission_a"] = award_a.model_dump(mode="json")
        report["mission_b"] = award_b.model_dump(mode="json")
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
    parser.add_argument("--event-a-lat", type=float, default=47.3980)
    parser.add_argument("--event-a-lon", type=float, default=8.5460)
    parser.add_argument("--event-b-lat", type=float, default=47.39795)
    parser.add_argument("--event-b-lon", type=float, default=8.54590)
    parser.add_argument("--event-a-confidence", type=float, default=0.90)
    parser.add_argument("--event-b-confidence", type=float, default=0.99)
    parser.add_argument("--timeout-s", type=float, default=150.0)
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
