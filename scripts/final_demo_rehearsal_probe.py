#!/usr/bin/env python3
"""Final recording rehearsal probe against the real Redis/backend/PX4 path.

This probe is deliberately external to SwarmOS. It observes only authoritative
bus frames and publishes two anomalies in the exact recording order:

clean fleet -> intrusion -> allocation/dispatch -> EN_ROUTE -> verified
ON_STATION -> payload -> second event while mission 1 is still active ->
BUSY exclusion with active mission id -> different winner -> concurrent
missions -> payload cleanup -> accepted RTL acknowledgements.
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
from swarm_core.allocations import AllocationDecision
from swarm_core.messages import Anomaly, AnomalyKind, Award, FleetState, Geo, MissionProgress
from swarm_core.payloads import PayloadEvent
from swarm_core.runtime_events import MissionRuntimeEvent, MissionRuntimeEvidence


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _step(name: str, detail: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "status": "pass", "detail": detail, "ts": _now()}


async def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    expected = tuple(x.strip() for x in args.expected_agents.split(",") if x.strip())
    if len(expected) < 2:
        raise ValueError("need at least two expected agents")

    report: dict[str, Any] = {
        "status": "fail",
        "started_at": _now(),
        "expected_agents": list(expected),
        "steps": [],
    }
    steps: list[dict[str, Any]] = report["steps"]
    started = time.monotonic()
    deadline = started + args.timeout_s

    client = from_url(args.redis_url, decode_responses=True)
    pubsub = client.pubsub()

    fleet: dict[str, FleetState] = {}
    allocations: dict[str, AllocationDecision] = {}
    awards: dict[str, Award] = {}
    progress: dict[str, list[MissionProgress]] = {}
    runtime: dict[str, list[MissionRuntimeEvent]] = {}
    payload: dict[str, list[PayloadEvent]] = {}

    def terminal(mission_id: str) -> bool:
        return any(frame.phase in {"DONE", "FAILED"} for frame in progress.get(mission_id, []))

    def latest_runtime(mission_id: str, phase: str) -> MissionRuntimeEvent | None:
        for frame in reversed(runtime.get(mission_id, [])):
            if frame.phase == phase:
                return frame
        return None

    async def consume_one() -> None:
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
        if message is None:
            return
        channel = str(message.get("channel"))
        raw = str(message.get("data"))
        try:
            if channel == "swarm:fleet:state":
                frame = FleetState.model_validate_json(raw)
                if frame.agent_id in expected:
                    fleet[frame.agent_id] = frame
            elif channel == "swarm:allocations":
                frame = AllocationDecision.model_validate_json(raw)
                allocations[frame.anomaly_id or frame.mission_id] = frame
            elif channel == "swarm:missions:award":
                frame = Award.model_validate_json(raw)
                awards[frame.mission_id] = frame
            elif channel.startswith("swarm:missions:progress:"):
                frame = MissionProgress.model_validate_json(raw)
                progress.setdefault(frame.mission_id, []).append(frame)
            elif channel == "swarm:missions:runtime":
                frame = MissionRuntimeEvent.model_validate_json(raw)
                runtime.setdefault(frame.mission_id, []).append(frame)
            elif channel == "swarm:payload:events":
                frame = PayloadEvent.model_validate_json(raw)
                payload.setdefault(frame.mission_id, []).append(frame)
        except ValueError:
            return

    async def wait_for(predicate, label: str):
        while time.monotonic() < deadline:
            if predicate():
                return
            await consume_one()
        raise TimeoutError(label)

    def assert_decision_truth(decision: AllocationDecision, *, expected_busy: str | None = None) -> None:
        if decision.mode != "auction":
            raise AssertionError(f"unexpected allocation mode {decision.mode}")
        if decision.winner_agent_id is None or decision.winner_score is None:
            raise AssertionError("allocation has no winner")
        eligible = {row.agent_id: row for row in decision.eligible_units}
        if decision.winner_agent_id not in eligible:
            raise AssertionError("winner is not in eligible set")
        winner = eligible[decision.winner_agent_id]
        if abs(winner.score - decision.winner_score) > 1e-9:
            raise AssertionError("winner score differs from eligible score")
        for row in decision.eligible_units:
            reason = row.score_breakdown
            numeric = (
                reason.distance_m,
                reason.distance_score,
                reason.battery_pct,
                reason.battery_score,
                reason.priority,
                reason.priority_score,
                reason.busy_penalty,
            )
            if not all(isinstance(value, (int, float)) for value in numeric):
                raise AssertionError(f"incomplete score breakdown for {row.agent_id}")
        if expected_busy is not None:
            excluded = {row.agent_id: row for row in decision.excluded_units}
            if expected_busy not in excluded:
                raise AssertionError(f"{expected_busy} missing from excluded set")
            busy = excluded[expected_busy]
            if busy.reason.value != "BUSY":
                raise AssertionError(f"{expected_busy} exclusion is {busy.reason.value}, not BUSY")

    try:
        await client.ping()
        await pubsub.psubscribe(
            "swarm:fleet:state",
            "swarm:allocations",
            "swarm:missions:award",
            "swarm:missions:progress:*",
            "swarm:missions:runtime",
            "swarm:payload:events",
        )

        await wait_for(lambda: all(agent in fleet for agent in expected), "fleet presence")
        clean = {agent: fleet[agent].model_dump(mode="json") for agent in expected}
        dirty = [
            agent
            for agent in expected
            if fleet[agent].fsm_state.value != "DOCKED" or fleet[agent].current_mission_id is not None
        ]
        if dirty:
            raise AssertionError(f"startup fleet not clean: {dirty}")
        steps.append(_step("clean_startup", {"fleet": clean}))

        event_a = Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=Geo(lat=args.event_a_lat, lon=args.event_a_lon),
            confidence=args.event_a_confidence,
        )
        await client.publish("swarm:anomalies", event_a.model_dump_json())
        steps.append(_step("event_1", {"anomaly": event_a.model_dump(mode="json")}))

        await wait_for(lambda: event_a.id in allocations, "event 1 allocation")
        decision_a = allocations[event_a.id]
        assert_decision_truth(decision_a)
        if set(row.agent_id for row in decision_a.eligible_units) != set(expected):
            raise AssertionError("event 1 did not evaluate every expected unit as eligible")
        if decision_a.excluded_units:
            raise AssertionError("event 1 unexpectedly excluded a clean unit")
        mission_a = decision_a.mission_id
        owner_a = decision_a.winner_agent_id
        assert owner_a is not None
        steps.append(_step("event_1_allocation", {"decision": decision_a.model_dump(mode="json")}))

        await wait_for(lambda: mission_a in awards, "event 1 award")
        award_a = awards[mission_a]
        if award_a.winner_agent_id != owner_a or abs(award_a.score - decision_a.winner_score) > 1e-9:
            raise AssertionError("event 1 award disagrees with allocation decision")
        steps.append(_step("event_1_dispatch", {"award": award_a.model_dump(mode="json")}))

        await wait_for(
            lambda: any(frame.phase == "EN_ROUTE" for frame in progress.get(mission_a, [])),
            "event 1 EN_ROUTE",
        )
        steps.append(_step("event_1_en_route", {"mission_id": mission_a, "owner": owner_a}))

        await wait_for(lambda: latest_runtime(mission_a, "ON_STATION") is not None, "event 1 ON_STATION")
        on_station_a = latest_runtime(mission_a, "ON_STATION")
        assert on_station_a is not None
        if on_station_a.agent_id != owner_a:
            raise AssertionError("ON_STATION ownership mismatch")
        if on_station_a.evidence is not MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED:
            raise AssertionError(f"ON_STATION missing MISSION_ITEM_REACHED: {on_station_a.evidence}")
        if terminal(mission_a):
            raise AssertionError("mission 1 terminated before payload")
        steps.append(_step("event_1_verified_on_station", {"runtime": on_station_a.model_dump(mode="json")}))

        def payload_started() -> bool:
            events = payload.get(mission_a, [])
            light = any(
                item.kind.value == "light_on"
                and item.execution_mode is not None
                and item.execution_mode.value == "mavlink_output_confirmed"
                and item.status.value == "confirmed"
                for item in events
            )
            speaker = any(
                item.kind.value == "play_message"
                and item.execution_mode is not None
                and item.execution_mode.value == "simulated"
                and item.status.value == "simulated"
                for item in events
            )
            return light and speaker

        await wait_for(payload_started, "event 1 payload start")
        if terminal(mission_a):
            raise AssertionError("mission 1 terminated before event 2 trigger")
        started_payload = [item.model_dump(mode="json") for item in payload[mission_a]]
        steps.append(_step("event_1_payload_active", {"events": started_payload}))

        event_b = Anomaly(
            kind=AnomalyKind.HEAT_SPOT,
            geo=Geo(lat=args.event_b_lat, lon=args.event_b_lon),
            confidence=args.event_b_confidence,
        )
        await client.publish("swarm:anomalies", event_b.model_dump_json())
        steps.append(
            _step(
                "event_2_while_mission_1_active",
                {"anomaly": event_b.model_dump(mode="json"), "mission_1": mission_a, "owner_1": owner_a},
            )
        )

        await wait_for(lambda: event_b.id in allocations, "event 2 allocation")
        decision_b = allocations[event_b.id]
        assert_decision_truth(decision_b, expected_busy=owner_a)
        mission_b = decision_b.mission_id
        owner_b = decision_b.winner_agent_id
        assert owner_b is not None
        if owner_b == owner_a:
            raise AssertionError("event 2 reused BUSY owner")
        busy_row = next(row for row in decision_b.excluded_units if row.agent_id == owner_a)
        if busy_row.active_mission_id != mission_a:
            raise AssertionError(
                f"BUSY exclusion mission mismatch: {busy_row.active_mission_id} != {mission_a}"
            )
        if terminal(mission_a):
            raise AssertionError("mission 1 terminated before event 2 allocation")
        steps.append(_step("event_2_busy_reallocation", {"decision": decision_b.model_dump(mode="json")}))

        await wait_for(lambda: mission_b in awards, "event 2 award")
        award_b = awards[mission_b]
        if award_b.winner_agent_id != owner_b or abs(award_b.score - decision_b.winner_score) > 1e-9:
            raise AssertionError("event 2 award disagrees with allocation decision")

        await wait_for(
            lambda: any(frame.phase == "EN_ROUTE" for frame in progress.get(mission_b, [])),
            "event 2 EN_ROUTE",
        )
        if terminal(mission_a):
            raise AssertionError("mission 1 terminated before concurrent-mission proof")
        steps.append(
            _step(
                "concurrent_missions_visible_truth",
                {
                    "mission_1": {
                        "mission_id": mission_a,
                        "owner": owner_a,
                        "runtime": on_station_a.model_dump(mode="json"),
                        "active": True,
                    },
                    "mission_2": {
                        "mission_id": mission_b,
                        "owner": owner_b,
                        "phase": "EN_ROUTE",
                        "active": True,
                    },
                },
            )
        )

        def cleanup_complete() -> bool:
            events = payload.get(mission_a, [])
            light_off = any(
                item.kind.value == "light_off"
                and item.execution_mode is not None
                and item.execution_mode.value == "mavlink_output_confirmed"
                and item.status.value == "confirmed"
                for item in events
            )
            speaker_stop = any(
                item.kind.value == "stop_message"
                and item.execution_mode is not None
                and item.execution_mode.value == "simulated"
                and item.status.value == "simulated"
                for item in events
            )
            return light_off and speaker_stop

        await wait_for(cleanup_complete, "mission 1 payload cleanup")
        if terminal(mission_a):
            raise AssertionError("mission 1 terminal frame arrived before payload cleanup observation")
        steps.append(
            _step(
                "payload_cleanup",
                {"events": [item.model_dump(mode="json") for item in payload[mission_a]]},
            )
        )

        await wait_for(lambda: latest_runtime(mission_a, "DONE") is not None, "mission 1 RTL/DONE")
        done_a = latest_runtime(mission_a, "DONE")
        assert done_a is not None
        if done_a.evidence is not MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED:
            raise AssertionError(f"mission 1 missing accepted RTL ack: {done_a.evidence}")
        steps.append(_step("mission_1_rtl", {"runtime": done_a.model_dump(mode="json")}))

        await wait_for(lambda: latest_runtime(mission_b, "ON_STATION") is not None, "mission 2 ON_STATION")
        on_station_b = latest_runtime(mission_b, "ON_STATION")
        assert on_station_b is not None
        if on_station_b.evidence is not MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED:
            raise AssertionError(f"mission 2 missing MISSION_ITEM_REACHED: {on_station_b.evidence}")

        await wait_for(lambda: latest_runtime(mission_b, "DONE") is not None, "mission 2 RTL/DONE")
        done_b = latest_runtime(mission_b, "DONE")
        assert done_b is not None
        if done_b.evidence is not MissionRuntimeEvidence.MAVLINK_RTL_COMMAND_ACKNOWLEDGED:
            raise AssertionError(f"mission 2 missing accepted RTL ack: {done_b.evidence}")
        steps.append(
            _step(
                "mission_2_closure",
                {
                    "on_station": on_station_b.model_dump(mode="json"),
                    "done": done_b.model_dump(mode="json"),
                },
            )
        )

        report["status"] = "pass"
        report["mission_1"] = {"anomaly_id": event_a.id, "mission_id": mission_a, "owner": owner_a}
        report["mission_2"] = {"anomaly_id": event_b.id, "mission_id": mission_b, "owner": owner_b}
        return 0, report
    except Exception as exc:
        report["steps"].append(
            {
                "name": "failure",
                "status": "fail",
                "detail": {"type": type(exc).__name__, "message": str(exc)},
                "ts": _now(),
            }
        )
        return 2, report
    finally:
        await pubsub.aclose()
        await client.aclose()
        report["finished_at"] = _now()
        report["duration_s"] = round(time.monotonic() - started, 3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    parser.add_argument("--expected-agents", default="mav-001,mav-002")
    parser.add_argument("--event-a-lat", type=float, default=47.3980)
    parser.add_argument("--event-a-lon", type=float, default=8.5460)
    parser.add_argument("--event-b-lat", type=float, default=47.39775)
    parser.add_argument("--event-b-lon", type=float, default=8.54559)
    parser.add_argument("--event-a-confidence", type=float, default=0.95)
    parser.add_argument("--event-b-confidence", type=float, default=0.99)
    parser.add_argument("--timeout-s", type=float, default=180.0)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    code, report = asyncio.run(run(args))
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
