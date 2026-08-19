from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    FleetState,
    Geo,
    MissionProgress,
)

from adapters.base import AdapterRegistry
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.policy_bus import AlarmPolicyBusFleetOrchestrator


class _HoldingAdapter:
    vendor = "test"
    model = "thin-executor"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.executed: list[Any] = []
        self.release = asyncio.Event()

    async def execute_mission(self, mission: Any) -> AsyncIterator[MissionProgress]:
        self.executed.append(mission)
        yield MissionProgress(
            mission_id=mission.id,
            phase="EN_ROUTE",
            progress_pct=20.0,
        )
        await self.release.wait()
        yield MissionProgress(
            mission_id=mission.id,
            phase="DONE",
            progress_pct=100.0,
        )


def _state(agent_id: str, *, offset: float) -> FleetState:
    return FleetState(
        agent_id=agent_id,
        vendor="test",
        model="thin-executor",
        fsm_state=AgentState.DOCKED,
        battery_pct=90.0 - offset,
        geo=Geo(lat=45.0 + offset * 0.00001, lon=9.0),
    )


@pytest.mark.asyncio
async def test_bus_backed_policy_derives_multi_agent_response_from_alarm_only() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    adapters = [_HoldingAdapter(f"mav-{idx:03d}") for idx in range(1, 4)]
    for adapter in adapters:
        registry.register(adapter)  # type: ignore[arg-type]

    orchestrator = AlarmPolicyBusFleetOrchestrator(
        bus=bus,
        registry=registry,
        continuous_patrol=False,
        alarm_policy=AlarmResponsePolicy(max_team_size=3),
    )
    run_task = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.01)

    for idx, adapter in enumerate(adapters, start=1):
        await bus.publish(
            "swarm:fleet:state",
            _state(adapter.agent_id, offset=float(idx)).model_dump_json(),
        )
    await orchestrator.wait_for_registered_fleet(timeout_s=1.0)

    alarm = Anomaly(
        id="backend-policy-alarm",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=45.0001, lon=9.0),
        confidence=0.97,
    )
    payload = alarm.model_dump_json()
    assert "mav-" not in payload
    await bus.publish("swarm:anomalies", payload)

    async def _wait_group() -> None:
        while not any(
            group.anomaly_id == alarm.id
            for group in orchestrator.execution_groups.values()
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_group(), timeout=1.0)
    group = next(
        group
        for group in orchestrator.execution_groups.values()
        if group.anomaly_id == alarm.id
    )

    assert group.requested_members == 3
    assert len(group.members) == 3
    assert {member.agent_id for member in group.members} == {
        adapter.agent_id for adapter in adapters
    }
    assert sum(len(adapter.executed) for adapter in adapters) == 3
    assert all(
        mission.params["parent_objective_id"] == group.objective_mission_id
        for adapter in adapters
        for mission in adapter.executed
    )

    run_task.cancel()
    await asyncio.gather(run_task, return_exceptions=True)
    for adapter in adapters:
        adapter.release.set()
    tasks = list(orchestrator._background_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await bus.close()
