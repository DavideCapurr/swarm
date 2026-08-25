#!/usr/bin/env python3
"""Record the authority frames used by the development replay.

The output is produced by the real ``ExecutionGroupOrchestrator`` decision
pipeline.  The fake adapters only close the physical execution loop; they do
not construct authority, decision, review, or objective-state records.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from swarm_core.authority import (
    MissionAuthorityConstraints,
    MissionAuthorityEffect,
    MissionAuthorityGrant,
    MissionAuthorityRule,
    MissionDecisionKind,
)
from swarm_core.execution_groups import ExecutionGroupState
from swarm_core.messages import (
    AgentState,
    FleetState,
    Geo,
    MissionProgress,
    MissionTask,
    ObjectiveApprovalCommand,
)
from swarm_core.missions import COOPERATIVE_VERIFY, COOPERATIVE_VERIFY_KIND, VERIFY

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.execution_groups import (
    ExecutionGroupOrchestrator,
    ExecutionRolePlan,
)

OBJECTIVE_ID = "8582edb3f2984289ab756602ac03aad5"
ANOMALY_ID = "d3e97452bda44cbc99cd5e16d67aed2f"
GRANT_ID = "georgios-demo-grant"
ROLE_MISSIONS = {
    "PRIMARY_OBSERVER": "0a224497d6384724aa3ee4043dcffc26",
    "SECONDARY_OBSERVER": "b9a64ed080bc47e498ea18e4d8655069",
    "OVERWATCH": "3dbd3eeaee6f43d29f6498a8042990ab",
}
REPLACEMENT_MISSION_ID = "a03fd8ddc5c140e89ec0eeb717296c42"
AUTHORITY_TOPICS = {
    "swarm:mission-decisions",
    "swarm:mission-decision-reviews",
    "swarm:mission-objective-states",
}
_use_recorded_replacement_id = False


class ReplayAdapter:
    vendor = "fake"
    model = "recorded-authority-executor"

    def __init__(
        self,
        agent_id: str,
        *,
        fail_gate: asyncio.Event,
        finish_gate: asyncio.Event,
        fail_once: bool = False,
    ) -> None:
        self.agent_id = agent_id
        self.fail_gate = fail_gate
        self.finish_gate = finish_gate
        self.fail_once = fail_once
        self.failed = False

    async def execute_mission(
        self, mission: MissionTask
    ) -> AsyncIterator[MissionProgress]:
        yield MissionProgress(
            mission_id=mission.id,
            phase="EN_ROUTE",
            progress_pct=25.0,
        )
        if self.fail_once and not self.failed:
            await self.fail_gate.wait()
            self.failed = True
            yield MissionProgress(
                mission_id=mission.id,
                phase="FAILED",
                progress_pct=25.0,
                error="recorded relay loss",
            )
            return
        await self.finish_gate.wait()
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


@dataclass
class ReplayOrchestrator(ExecutionGroupOrchestrator):
    fleet_fixture: list[FleetState] = field(default_factory=list)

    def _snapshot_fleet(self) -> list[FleetState]:
        return list(self.fleet_fixture)

    @staticmethod
    def _clone_mission(template: MissionTask) -> MissionTask:
        global _use_recorded_replacement_id
        clone = ExecutionGroupOrchestrator._clone_mission(template)
        if (
            _use_recorded_replacement_id
            and template.params.get("execution_role") == "SECONDARY_OBSERVER"
        ):
            clone.id = REPLACEMENT_MISSION_ID
            _use_recorded_replacement_id = False
        return clone


def _fleet() -> list[FleetState]:
    batteries = {
        "mav-004": 99.0,
        "mav-003": 90.0,
        "mav-002": 80.0,
        "mav-001": 70.0,
    }
    capabilities = {
        "mav-004": ["thermal_observation", "visual_observation"],
        "mav-003": ["visual_observation", "relay"],
        "mav-002": ["wide_area_observation", "visual_observation"],
        "mav-001": ["visual_observation", "relay"],
    }
    return [
        FleetState(
            agent_id=agent_id,
            vendor="fake",
            model="recorded-authority-executor",
            fsm_state=AgentState.DOCKED,
            battery_pct=battery,
            geo=Geo(lat=47.39778, lon=8.54561),
            capabilities=capabilities[agent_id],
        )
        for agent_id, battery in batteries.items()
    ]


def _plans(objective: MissionTask) -> list[ExecutionRolePlan]:
    geo = Geo.model_validate(objective.params["geo"])
    roles = ["PRIMARY_OBSERVER", "SECONDARY_OBSERVER", "OVERWATCH"]
    plans: list[ExecutionRolePlan] = []
    for index, role in enumerate(roles):
        mission = VERIFY(
            geo=geo,
            hover_s=0.0,
            altitude_m=40.0 + index * 15.0,
            priority=99,
            authority_grant_id=GRANT_ID,
            authority_grant_revision=1,
        )
        mission.id = ROLE_MISSIONS[role]
        mission.params["execution_role"] = role
        mission.params["parent_objective_id"] = objective.id
        plans.append(ExecutionRolePlan(role=role, mission=mission))
    return plans


async def _wait_for_replacement(orchestrator: ReplayOrchestrator) -> None:
    for _ in range(400):
        if any(
            decision.decision_kind
            is MissionDecisionKind.REPLACE_FAILED_EXECUTOR
            for decision in orchestrator.mission_decisions.values()
        ):
            return
        await asyncio.sleep(0.005)
    raise TimeoutError("replacement decision was not produced")


async def _wait_for_terminal(
    orchestrator: ReplayOrchestrator, group_id: str
) -> None:
    for _ in range(400):
        state = orchestrator.execution_groups[group_id].state
        if state in {ExecutionGroupState.COMPLETED, ExecutionGroupState.FAILED}:
            if state is not ExecutionGroupState.COMPLETED:
                raise RuntimeError(f"recording group ended as {state.value}")
            return
        await asyncio.sleep(0.005)
    raise TimeoutError("recording group did not complete")


async def record() -> dict[str, Any]:
    global _use_recorded_replacement_id
    bus = InMemoryBus()
    await bus.connect()
    records: list[dict[str, Any]] = []

    async def collect() -> None:
        async for topic, payload in bus.subscribe("swarm:mission-*"):
            if topic in AUTHORITY_TOPICS:
                records.append(
                    {
                        "sequence": len(records) + 1,
                        "topic": topic,
                        "data": json.loads(payload),
                    }
                )

    collector = asyncio.create_task(collect())
    await asyncio.sleep(0)

    fail_gate = asyncio.Event()
    finish_gate = asyncio.Event()
    registry = AdapterRegistry()
    for state in _fleet():
        adapter = ReplayAdapter(
            state.agent_id,
            fail_gate=fail_gate,
            finish_gate=finish_gate,
            fail_once=state.agent_id == "mav-003",
        )
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = ReplayOrchestrator(
        bus=bus,
        registry=registry,
        fleet_fixture=_fleet(),
        max_group_replacements_per_role=1,
    )
    progress = asyncio.create_task(orchestrator._execution_group_progress_loop())
    orchestrator._background_tasks.add(progress)
    await asyncio.sleep(0)

    objective = COOPERATIVE_VERIFY(
        geo=Geo(lat=47.39805, lon=8.546),
        team_size=3,
        hover_s=0.0,
        priority=99,
        authority_grant_id=GRANT_ID,
        authority_grant_revision=1,
    )
    objective.id = OBJECTIVE_ID
    grant = MissionAuthorityGrant(
        grant_id=GRANT_ID,
        revision=1,
        objective_id=objective.id,
        holder_id="risk-owner",
        default_effect=MissionAuthorityEffect.REVIEW_REQUIRED,
        delegated_rules=[
            MissionAuthorityRule(
                decision_kind=MissionDecisionKind.REPLACE_FAILED_EXECUTOR,
                effect=MissionAuthorityEffect.AUTO_AUTHORIZE,
                constraints=MissionAuthorityConstraints(
                    max_agents=1,
                    allowed_agent_ids=["mav-001"],
                    allowed_mission_kinds=[COOPERATIVE_VERIFY_KIND],
                    max_altitude_m=70.0,
                ),
            )
        ],
    )
    orchestrator.register_authority_grant(grant)

    group = await orchestrator.dispatch_execution_group(
        objective,
        anomaly_id=ANOMALY_ID,
        plans=_plans(objective),
    )
    if group.decision_id is None:
        raise RuntimeError("launch decision was not produced")

    _use_recorded_replacement_id = True
    await orchestrator.approve_objective(
        ObjectiveApprovalCommand(
            objective_id=objective.id,
            decision_id=group.decision_id,
            approved_by="risk-owner",
            action="approve",
        )
    )
    fail_gate.set()
    await _wait_for_replacement(orchestrator)
    finish_gate.set()
    await _wait_for_terminal(orchestrator, group.id)
    await asyncio.sleep(0)

    progress.cancel()
    await asyncio.gather(progress, return_exceptions=True)
    await bus.close()
    await collector

    decisions = [
        record["data"]
        for record in records
        if record["topic"] == "swarm:mission-decisions"
    ]
    if [decision["decision_kind"] for decision in decisions] != [
        "LAUNCH_COMPOSITION",
        "REPLACE_FAILED_EXECUTOR",
    ]:
        raise RuntimeError("recording did not produce the expected D1/D2 sequence")

    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "generator": "scripts/record_mission_authority_replay.py",
        "runtime": "ExecutionGroupOrchestrator + InMemoryBus + fake physical adapters",
        "objective_id": OBJECTIVE_ID,
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("frontend/lib/fixtures/mission-authority-replay.json"),
    )
    args = parser.parse_args()
    payload = asyncio.run(record())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
