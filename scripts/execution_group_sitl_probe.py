"""External Redis probe for one logical objective executed by multiple PX4 agents.

This script deliberately does not import backend or orchestrator implementation
modules. It injects one high-confidence anomaly and validates only public bus
truth: FleetState, ExecutionGroup and MissionRuntimeEvent frames.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
from time import monotonic

import redis.asyncio as redis
from swarm_core.execution_groups import ExecutionGroup, ExecutionGroupMemberState, ExecutionGroupState
from swarm_core.messages import Anomaly, AnomalyKind, FleetState, Geo
from swarm_core.runtime_events import MissionRuntimeEvent, MissionRuntimeEvidence

EXPECTED_AGENTS = {"mav-001", "mav-002", "mav-003", "mav-004"}
EXPECTED_ROLES = {"PRIMARY_OBSERVER", "SECONDARY_OBSERVER", "OVERWATCH"}
TARGET = Geo(lat=47.3980, lon=8.5460, alt_m=0.0)


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


async def _next_message(pubsub, timeout_s: float = 1.0):
    try:
        return await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True, timeout=timeout_s), timeout=timeout_s + 0.2)
    except TimeoutError:
        return None


async def main() -> None:
    client = redis.from_url(_redis_url(), decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(
        "swarm:fleet:state",
        "swarm:execution-groups",
        "swarm:missions:runtime",
    )

    fleet: dict[str, FleetState] = {}
    deadline = monotonic() + 120.0
    while monotonic() < deadline and set(fleet) != EXPECTED_AGENTS:
        msg = await _next_message(pubsub)
        if not msg or msg.get("channel") != "swarm:fleet:state":
            continue
        try:
            state = FleetState.model_validate_json(msg["data"])
        except Exception:
            continue
        if state.agent_id in EXPECTED_AGENTS:
            fleet[state.agent_id] = state

    assert set(fleet) == EXPECTED_AGENTS, f"fleet readiness failed: {sorted(fleet)}"
    print("FLEET_READY", sorted(fleet))

    anomaly = Anomaly(
        id="sitl-cooperative-intrusion",
        kind=AnomalyKind.INTRUSION,
        geo=TARGET,
        confidence=0.99,
    )
    await client.publish("swarm:anomalies", anomaly.model_dump_json())
    print("ANOMALY_PUBLISHED", anomaly.id)

    group: ExecutionGroup | None = None
    phases: dict[str, list[str]] = defaultdict(list)
    evidence: dict[str, set[str]] = defaultdict(set)
    runtime_agents: dict[str, str] = {}
    observed_groups: list[dict[str, object]] = []
    deadline = monotonic() + 240.0

    while monotonic() < deadline:
        msg = await _next_message(pubsub)
        if not msg:
            continue
        channel = msg.get("channel")
        payload = msg.get("data")
        if not isinstance(payload, str):
            continue

        if channel == "swarm:execution-groups":
            candidate = ExecutionGroup.model_validate_json(payload)
            if candidate.anomaly_id != anomaly.id:
                continue
            group = candidate
            observed_groups.append(candidate.model_dump(mode="json"))
            print(
                "GROUP",
                candidate.state.value,
                [(m.role, m.agent_id, m.state.value) for m in candidate.members],
            )
        elif channel == "swarm:missions:runtime":
            event = MissionRuntimeEvent.model_validate_json(payload)
            if group is None:
                continue
            child_ids = {member.mission_id for member in group.members}
            if event.mission_id not in child_ids:
                continue
            phases[event.mission_id].append(event.phase)
            runtime_agents[event.mission_id] = event.agent_id
            if event.evidence is not None:
                evidence[event.mission_id].add(event.evidence.value)
            print(
                "RUNTIME",
                event.mission_id[:8],
                event.agent_id,
                event.phase,
                event.evidence.value if event.evidence else "-",
            )

        if group is not None and group.state in {
            ExecutionGroupState.COMPLETED,
            ExecutionGroupState.FAILED,
        }:
            if group.state is ExecutionGroupState.COMPLETED:
                # Give the runtime subscriber a short window to receive the final
                # DONE event published just before the aggregate group transition.
                await asyncio.sleep(0.5)
                while True:
                    tail = await _next_message(pubsub, timeout_s=0.15)
                    if not tail:
                        break
                    if tail.get("channel") != "swarm:missions:runtime":
                        continue
                    event = MissionRuntimeEvent.model_validate_json(tail["data"])
                    child_ids = {member.mission_id for member in group.members}
                    if event.mission_id in child_ids:
                        phases[event.mission_id].append(event.phase)
                        runtime_agents[event.mission_id] = event.agent_id
                        if event.evidence is not None:
                            evidence[event.mission_id].add(event.evidence.value)
            break

    assert group is not None, "no ExecutionGroup observed"
    assert group.state is ExecutionGroupState.COMPLETED, (
        f"group terminal state={group.state.value} reason={group.failure_reason}"
    )
    assert group.requested_members == 3

    completed_by_role: dict[str, object] = {}
    for member in group.members:
        if member.state is ExecutionGroupMemberState.COMPLETED:
            completed_by_role[member.role] = member
    assert set(completed_by_role) == EXPECTED_ROLES, completed_by_role

    final_members = [completed_by_role[role] for role in sorted(EXPECTED_ROLES)]
    member_agents = {member.agent_id for member in final_members}  # type: ignore[attr-defined]
    assert len(member_agents) == 3, member_agents
    assert member_agents.issubset(EXPECTED_AGENTS)
    spare = EXPECTED_AGENTS - member_agents
    assert len(spare) == 1, spare

    reached_evidence = MissionRuntimeEvidence.MAVLINK_MISSION_ITEM_REACHED.value
    for member in final_members:
        mission_id = member.mission_id  # type: ignore[attr-defined]
        observed = phases[mission_id]
        assert "EN_ROUTE" in observed, (mission_id, observed)
        assert "ON_STATION" in observed, (mission_id, observed)
        assert "DONE" in observed, (mission_id, observed)
        assert reached_evidence in evidence[mission_id], (mission_id, evidence[mission_id])
        assert runtime_agents[mission_id] == member.agent_id  # type: ignore[attr-defined]

    proof = {
        "status": "PASS",
        "anomaly_id": anomaly.id,
        "group_id": group.id,
        "objective_mission_id": group.objective_mission_id,
        "state": group.state.value,
        "requested_members": group.requested_members,
        "members": [member.model_dump(mode="json") for member in group.members],
        "spare_agents": sorted(spare),
        "runtime_phases": dict(phases),
        "runtime_evidence": {k: sorted(v) for k, v in evidence.items()},
        "group_frames": observed_groups,
    }
    out = Path(os.getenv("SWARM_PROBE_OUTPUT", "artifacts/execution-group-sitl-proof.json"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(proof, indent=2, default=str))
    print(json.dumps(proof, indent=2, default=str))

    await pubsub.close()
    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
