#!/usr/bin/env python3
"""Live Redis-only acceptance probe for SwarmOS execution groups.

The probe intentionally imports no backend/orchestrator implementation. It
observes only authoritative bus frames and proves that one cooperative parent
objective becomes multiple centrally assigned child missions on distinct PX4
executors while the parent itself is never dispatched.
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
from swarm_core.execution_groups import ExecutionGroup, ExecutionGroupState
from swarm_core.messages import Anomaly, AnomalyKind, Award, FleetState, Geo
from swarm_core.runtime_events import MissionRuntimeEvent, MissionRuntimeEvidence


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


async def run_probe(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    expected = tuple(
        part.strip() for part in args.expected_agents.split(",") if part.strip()
    )
    if len(expected) < args.team_size + 1:
        raise ValueError("expected fleet must include the requested team plus a spare")

    started = time.monotonic()
    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _utc_now(),
        "expected_agents": list(expected),
        "team_size": args.team_size,
        "steps": [],
    }
    steps: list[dict[str, Any]] = report["steps"]

    client = from_url(args.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    deadline = time.monotonic() + args.timeout_s

    fleet: dict[str, FleetState] = {}
    groups: dict[str, ExecutionGroup] = {}
    awards: dict[str, Award] = {}
    runtime: dict[str, list[MissionRuntimeEvent]] = {}

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

        if channel == "swarm:execution-groups":
            try:
                group = ExecutionGroup.model_validate_json(payload)
            except ValueError:
                return
            groups[group.id] = group
            return

        if channel == "swarm:missions:award":
            try:
                award = Award.model_validate_json(payload)
            except ValueError:
                return
            awards[award.mission_id] = award
            return

        if channel == "swarm:missions:runtime":
            try:
                event = MissionRuntimeEvent.model_validate_json(payload)
            except ValueError:
                return
            runtime.setdefault(event.mission_id, []).append(event)

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
            "swarm:execution-groups",
            "swarm:missions:award",
            "swarm:missions:runtime",
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

        anomaly = Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=args.lat, lon=args.lon),
            confidence=args.confidence,
        )
        await client.publish("swarm:anomalies", anomaly.model_dump_json())
        steps.append(
            _step(
                "cooperative_event_published",
                "pass",
                {"anomaly_id": anomaly.id, "confidence": anomaly.confidence},
            )
        )

        formed = await _pump_until(
            lambda: any(group.anomaly_id == anomaly.id for group in groups.values())
        )
        if not formed:
            steps.append(
                _step(
                    "group_formed",
                    "fail",
                    {"reason": "no execution group for published anomaly"},
                )
            )
            return 2, report

        group = next(group for group in groups.values() if group.anomaly_id == anomaly.id)
        initial_members = list(group.members)
        if group.requested_members != args.team_size or len(initial_members) != args.team_size:
            steps.append(
                _step(
                    "group_formed",
                    "fail",
                    {
                        "requested_members": group.requested_members,
                        "observed_members": len(initial_members),
                    },
                )
            )
            return 2, report

        agent_ids = [member.agent_id for member in initial_members]
        mission_ids = [member.mission_id for member in initial_members]
        roles = [member.role for member in initial_members]
        if len(set(agent_ids)) != args.team_size or len(set(mission_ids)) != args.team_size:
            steps.append(
                _step(
                    "group_formed",
                    "fail",
                    {"agents": agent_ids, "missions": mission_ids},
                )
            )
            return 2, report
        if not set(agent_ids).issubset(expected):
            steps.append(
                _step(
                    "group_formed",
                    "fail",
                    {"agents": agent_ids, "expected": list(expected)},
                )
            )
            return 2, report

        spare_agents = sorted(set(expected) - set(agent_ids))
        steps.append(
            _step(
                "group_formed",
                "pass",
                {
                    "group_id": group.id,
                    "objective_mission_id": group.objective_mission_id,
                    "roles": roles,
                    "members": [member.model_dump(mode="json") for member in initial_members],
                    "spares": spare_agents,
                },
            )
        )

        awards_ready = await _pump_until(
            lambda: all(mission_id in awards for mission_id in mission_ids)
        )
        if not awards_ready:
            steps.append(
                _step(
                    "child_awards",
                    "fail",
                    {
                        "expected_child_missions": mission_ids,
                        "seen_awards": sorted(awards),
                    },
                )
            )
            return 2, report

        if group.objective_mission_id in awards:
            steps.append(
                _step(
                    "parent_not_dispatched",
                    "fail",
                    {"objective_mission_id": group.objective_mission_id},
                )
            )
            return 2, report

        mismatched_awards = [
            {
                "mission_id": member.mission_id,
                "expected_agent": member.agent_id,
                "awarded_agent": awards[member.mission_id].winner_agent_id,
            }
            for member in initial_members
            if awards[member.mission_id].winner_agent_id != member.agent_id
        ]
        if mismatched_awards:
            steps.append(_step("child_awards", "fail", {"mismatches": mismatched_awards}))
            return 2, report

        steps.append(
            _step(
                "parent_not_dispatched",
                "pass",
                {
                    "objective_mission_id": group.objective_mission_id,
                    "child_awards": {
                        mission_id: awards[mission_id].model_dump(mode="json")
                        for mission_id in mission_ids
                    },
                },
            )
        )

        def _all_have_verified_on_station() -> bool:
            return all(
                any(
                    event.phase == "ON_STATION"
                    and event.evidence
                    is MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED
                    for event in runtime.get(mission_id, [])
                )
                for mission_id in mission_ids
            )

        verified = await _pump_until(_all_have_verified_on_station)
        if not verified:
            steps.append(
                _step(
                    "verified_on_station",
                    "fail",
                    {
                        "runtime": {
                            mission_id: [
                                event.model_dump(mode="json")
                                for event in runtime.get(mission_id, [])
                            ]
                            for mission_id in mission_ids
                        }
                    },
                )
            )
            return 2, report

        steps.append(
            _step(
                "verified_on_station",
                "pass",
                {
                    "missions": mission_ids,
                    "evidence": MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED.value,
                },
            )
        )

        def _all_done_with_rtl_ack() -> bool:
            return all(
                any(
                    event.phase == "DONE"
                    and event.evidence
                    is MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED
                    for event in runtime.get(mission_id, [])
                )
                for mission_id in mission_ids
            )

        completed = await _pump_until(
            lambda: (
                _all_done_with_rtl_ack()
                and group.id in groups
                and groups[group.id].state is ExecutionGroupState.COMPLETED
            )
        )
        group = groups[group.id]
        if not completed:
            steps.append(
                _step(
                    "group_completed",
                    "fail",
                    {
                        "group": group.model_dump(mode="json"),
                        "runtime": {
                            mission_id: [
                                event.model_dump(mode="json")
                                for event in runtime.get(mission_id, [])
                            ]
                            for mission_id in mission_ids
                        },
                    },
                )
            )
            return 2, report

        steps.append(
            _step(
                "group_completed",
                "pass",
                {
                    "group": group.model_dump(mode="json"),
                    "done_evidence": MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED.value,
                    "spares": spare_agents,
                },
            )
        )

        report["status"] = "pass"
        report["group"] = group.model_dump(mode="json")
        report["runtime"] = {
            mission_id: [event.model_dump(mode="json") for event in runtime[mission_id]]
            for mission_id in mission_ids
        }
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
        await pubsub.aclose()
        await client.aclose()
        report["finished_at"] = _utc_now()
        report["duration_s"] = round(time.monotonic() - started, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    parser.add_argument(
        "--expected-agents",
        default="mav-001,mav-002,mav-003,mav-004",
    )
    parser.add_argument("--team-size", type=int, default=3)
    parser.add_argument("--lat", type=float, default=47.3980)
    parser.add_argument("--lon", type=float, default=8.5460)
    parser.add_argument("--confidence", type=float, default=0.99)
    parser.add_argument("--timeout-s", type=float, default=210.0)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, report = asyncio.run(run_probe(args))
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
