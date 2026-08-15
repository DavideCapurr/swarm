#!/usr/bin/env python3
"""Live PX4 fault-injection probe for SwarmOS execution-group failover.

The probe observes only authoritative Redis truth frames, then kills one selected
PX4 SITL process inside the validation container. It verifies that the failed
child becomes explicit failure truth, SwarmOS replaces that role from spare
capacity, and the aggregate execution group still completes.

The probe does not call orchestrator internals and never publishes a synthetic
FAILED mission-progress frame.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redis.asyncio import from_url
from swarm_core.execution_groups import (
    ExecutionGroup,
    ExecutionGroupMemberState,
    ExecutionGroupState,
)
from swarm_core.messages import Anomaly, AnomalyKind, Award, FleetState, Geo
from swarm_core.runtime_events import MissionRuntimeEvent, MissionRuntimeEvidence


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, status: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": status, "detail": detail, "ts": _utc_now()}


def _instance_number(agent_id: str) -> int:
    match = re.search(r"(\d+)$", agent_id)
    if match is None:
        raise ValueError(f"cannot derive PX4 instance from agent id {agent_id!r}")
    return int(match.group(1))


async def _kill_px4_instance(container: str, agent_id: str) -> dict[str, Any]:
    instance = _instance_number(agent_id)
    script = f"""
set -eu
pid=$(ps -eo pid=,args= | awk '$0 ~ /bin\\/px4 -i {instance} -d/ {{print $1; exit}}')
if [ -z "$pid" ]; then
  echo "no px4 process found for instance {instance}" >&2
  exit 3
fi
printf 'killing agent={agent_id} instance={instance} pid=%s\\n' "$pid"
kill -KILL "$pid"
sleep 1
if kill -0 "$pid" 2>/dev/null; then
  echo "px4 process still alive after SIGKILL" >&2
  exit 4
fi
"""
    proc = await asyncio.create_subprocess_exec(
        "docker",
        "exec",
        container,
        "bash",
        "-lc",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    detail = {
        "agent_id": agent_id,
        "instance": instance,
        "returncode": proc.returncode,
        "stdout": stdout.decode(errors="replace").strip(),
        "stderr": stderr.decode(errors="replace").strip(),
    }
    if proc.returncode != 0:
        raise RuntimeError(f"PX4 fault injection failed: {detail}")
    return detail


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
        "victim_role": args.victim_role,
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
        steps.append(_step("fleet_ready", "pass", {"agents": list(expected)}))

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
            steps.append(_step("group_formed", "fail", {"reason": "group missing"}))
            return 2, report

        group = next(group for group in groups.values() if group.anomaly_id == anomaly.id)
        initial_members = list(group.members)
        if len(initial_members) != args.team_size:
            steps.append(
                _step(
                    "group_formed",
                    "fail",
                    {"members": [m.model_dump(mode="json") for m in initial_members]},
                )
            )
            return 2, report

        victim = next(
            (member for member in initial_members if member.role == args.victim_role),
            None,
        )
        if victim is None:
            steps.append(
                _step(
                    "victim_selected",
                    "fail",
                    {"requested_role": args.victim_role, "roles": [m.role for m in initial_members]},
                )
            )
            return 2, report

        initial_agents = {member.agent_id for member in initial_members}
        spares = sorted(set(expected) - initial_agents)
        if not spares:
            steps.append(_step("spare_capacity", "fail", {"initial_agents": sorted(initial_agents)}))
            return 2, report
        steps.append(
            _step(
                "group_formed",
                "pass",
                {
                    "group_id": group.id,
                    "objective_mission_id": group.objective_mission_id,
                    "members": [m.model_dump(mode="json") for m in initial_members],
                    "spares": spares,
                    "victim": victim.model_dump(mode="json"),
                },
            )
        )

        child_ids = [member.mission_id for member in initial_members]
        awards_ready = await _pump_until(lambda: all(mid in awards for mid in child_ids))
        if not awards_ready or group.objective_mission_id in awards:
            steps.append(
                _step(
                    "authority_boundary",
                    "fail",
                    {
                        "child_ids": child_ids,
                        "awards": sorted(awards),
                        "parent_awarded": group.objective_mission_id in awards,
                    },
                )
            )
            return 2, report
        steps.append(
            _step(
                "authority_boundary",
                "pass",
                {"parent_awarded": False, "child_awards": child_ids},
            )
        )

        victim_en_route = await _pump_until(
            lambda: any(
                event.phase == "EN_ROUTE"
                for event in runtime.get(victim.mission_id, [])
            )
        )
        if not victim_en_route:
            steps.append(
                _step(
                    "victim_en_route",
                    "fail",
                    {"runtime": [e.model_dump(mode="json") for e in runtime.get(victim.mission_id, [])]},
                )
            )
            return 2, report
        steps.append(
            _step(
                "victim_en_route",
                "pass",
                {"agent_id": victim.agent_id, "mission_id": victim.mission_id},
            )
        )

        kill_detail = await _kill_px4_instance(args.px4_container, victim.agent_id)
        steps.append(_step("physical_executor_killed", "pass", kill_detail))

        victim_failed = await _pump_until(
            lambda: any(
                event.phase == "FAILED"
                for event in runtime.get(victim.mission_id, [])
            )
        )
        if not victim_failed:
            steps.append(
                _step(
                    "failure_detected",
                    "fail",
                    {"runtime": [e.model_dump(mode="json") for e in runtime.get(victim.mission_id, [])]},
                )
            )
            return 2, report
        failure_event = next(
            event
            for event in runtime[victim.mission_id]
            if event.phase == "FAILED"
        )
        steps.append(
            _step(
                "failure_detected",
                "pass",
                {"event": failure_event.model_dump(mode="json")},
            )
        )

        def _replacement_member() -> Any:
            current = groups.get(group.id)
            if current is None:
                return None
            return next(
                (
                    member
                    for member in current.members
                    if member.role == victim.role
                    and member.replaces_agent_id == victim.agent_id
                ),
                None,
            )

        replaced = await _pump_until(lambda: _replacement_member() is not None)
        replacement = _replacement_member()
        if not replaced or replacement is None:
            steps.append(
                _step(
                    "replacement_selected",
                    "fail",
                    {"group": groups[group.id].model_dump(mode="json")},
                )
            )
            return 2, report

        if replacement.agent_id not in spares or replacement.agent_id == victim.agent_id:
            steps.append(
                _step(
                    "replacement_selected",
                    "fail",
                    {
                        "replacement": replacement.model_dump(mode="json"),
                        "spares": spares,
                    },
                )
            )
            return 2, report

        current_group = groups[group.id]
        original = next(
            member
            for member in current_group.members
            if member.mission_id == victim.mission_id
        )
        if original.state is not ExecutionGroupMemberState.REPLACED:
            steps.append(
                _step(
                    "replacement_selected",
                    "fail",
                    {"original": original.model_dump(mode="json")},
                )
            )
            return 2, report

        steps.append(
            _step(
                "replacement_selected",
                "pass",
                {
                    "failed_agent": victim.agent_id,
                    "replacement": replacement.model_dump(mode="json"),
                    "selection_source": "SwarmOS execution-group truth",
                },
            )
        )

        replacement_awarded = await _pump_until(
            lambda: replacement.mission_id in awards
            and awards[replacement.mission_id].winner_agent_id == replacement.agent_id
        )
        if not replacement_awarded:
            steps.append(
                _step(
                    "replacement_awarded",
                    "fail",
                    {"replacement": replacement.model_dump(mode="json")},
                )
            )
            return 2, report
        steps.append(
            _step(
                "replacement_awarded",
                "pass",
                {"award": awards[replacement.mission_id].model_dump(mode="json")},
            )
        )

        replacement_on_station = await _pump_until(
            lambda: any(
                event.phase == "ON_STATION"
                and event.evidence is MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED
                for event in runtime.get(replacement.mission_id, [])
            )
        )
        if not replacement_on_station:
            steps.append(
                _step(
                    "replacement_on_station",
                    "fail",
                    {"runtime": [e.model_dump(mode="json") for e in runtime.get(replacement.mission_id, [])]},
                )
            )
            return 2, report
        steps.append(
            _step(
                "replacement_on_station",
                "pass",
                {
                    "agent_id": replacement.agent_id,
                    "mission_id": replacement.mission_id,
                    "evidence": MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED.value,
                },
            )
        )

        completed = await _pump_until(
            lambda: (
                groups.get(group.id) is not None
                and groups[group.id].state is ExecutionGroupState.COMPLETED
                and any(
                    event.phase == "DONE"
                    and event.evidence is MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED
                    for event in runtime.get(replacement.mission_id, [])
                )
            )
        )
        final_group = groups[group.id]
        if not completed:
            steps.append(
                _step(
                    "group_recovered",
                    "fail",
                    {
                        "group": final_group.model_dump(mode="json"),
                        "replacement_runtime": [
                            e.model_dump(mode="json")
                            for e in runtime.get(replacement.mission_id, [])
                        ],
                    },
                )
            )
            return 2, report

        steps.append(
            _step(
                "group_recovered",
                "pass",
                {
                    "state": final_group.state.value,
                    "failed_agent": victim.agent_id,
                    "replacement_agent": replacement.agent_id,
                    "replacement_done_evidence": MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED.value,
                    "group": final_group.model_dump(mode="json"),
                },
            )
        )

        report["status"] = "pass"
        report["group"] = final_group.model_dump(mode="json")
        report["victim"] = victim.model_dump(mode="json")
        report["replacement"] = replacement.model_dump(mode="json")
        report["runtime"] = {
            mission_id: [event.model_dump(mode="json") for event in events]
            for mission_id, events in runtime.items()
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
    parser.add_argument("--expected-agents", default="mav-001,mav-002,mav-003,mav-004")
    parser.add_argument("--team-size", type=int, default=3)
    parser.add_argument("--victim-role", default="SECONDARY_OBSERVER")
    parser.add_argument("--px4-container", default="px4-execution-group-failover")
    parser.add_argument("--lat", type=float, default=47.3980)
    parser.add_argument("--lon", type=float, default=8.5460)
    parser.add_argument("--confidence", type=float, default=0.99)
    parser.add_argument("--timeout-s", type=float, default=360.0)
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
