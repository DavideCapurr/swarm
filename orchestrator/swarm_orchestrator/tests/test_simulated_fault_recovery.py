from __future__ import annotations

import asyncio

import pytest
from swarm_core.disposition import DispositionDecision
from swarm_core.execution_groups import ExecutionGroup, ExecutionGroupMemberState
from swarm_core.messages import AgentState, Anomaly, AnomalyKind, Geo
from swarm_core.missions import VERIFY

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.alarm_driven import (
    AlarmDrivenExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.disposition_execution_groups import DISPOSITION_TOPIC
from sim.swarm_sim.world import World


async def _collect_dispositions(
    bus: InMemoryBus,
    out: list[DispositionDecision],
) -> None:
    async for _topic, payload in bus.subscribe(DISPOSITION_TOPIC):
        out.append(DispositionDecision.model_validate_json(payload))


async def _wait_for_alarm_group(
    orchestrator: AlarmDrivenExecutionGroupOrchestrator,
    alarm_id: str,
) -> ExecutionGroup:
    async def _wait() -> ExecutionGroup:
        while True:
            for group in orchestrator.execution_groups.values():
                if group.anomaly_id == alarm_id:
                    return group
            await asyncio.sleep(0.005)

    return await asyncio.wait_for(_wait(), timeout=2.0)


@pytest.mark.asyncio
async def test_external_failure_selects_replacement_and_recomputes_disposition() -> None:
    bus = InMemoryBus()
    await bus.connect()
    world = World.vineyard(n_drones=4, ignition_after_s=86_400.0)
    registry = AdapterRegistry()
    adapters: dict[str, SimulatedAdapter] = {}
    for drone in world.drones:
        adapter = SimulatedAdapter(agent_id=drone.agent_id, drone=drone, self_tick=True)
        await adapter.connect()
        registry.register(adapter)
        adapters[adapter.agent_id] = adapter

    orchestrator = AlarmDrivenExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=False,
        execute_disposition_retask=True,
        alarm_policy=AlarmResponsePolicy(
            cooperative_threshold=0.80,
            high_confidence_threshold=0.93,
            max_team_size=3,
            cooperative_hover_s=60.0,
        ),
    )
    dispositions: list[DispositionDecision] = []
    collector = asyncio.create_task(_collect_dispositions(bus, dispositions))
    runtime = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.02)

    alarm = Anomaly(
        id="alarm-external-failure",
        kind=AnomalyKind.INTRUSION,
        geo=Geo(lat=world.dock.lat + 0.0003, lon=world.dock.lon + 0.0003),
        confidence=0.97,
    )
    # No executor identity exists in the stimulus. SwarmOS composes three out of
    # four physical agents and leaves the fourth as spare.
    payload = alarm.model_dump_json()
    assert "mav-" not in payload
    await bus.publish("swarm:anomalies", payload)

    group = await _wait_for_alarm_group(orchestrator, alarm.id)

    async def _wait_initial_disposition() -> None:
        while not any(
            decision.objective_mission_id == group.objective_mission_id
            and decision.reason == "COMPOSITION"
            for decision in dispositions
        ):
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_initial_disposition(), timeout=2.0)
    current = orchestrator.execution_groups[group.id]
    assert len(current.members) == 3
    initially_selected = {member.agent_id for member in current.members}
    spare = set(adapters) - initially_selected
    assert len(spare) == 1

    # The failure identity is now an external fact discovered from the state that
    # SwarmOS itself produced. The test does not name or invoke a replacement.
    failed_agent = current.members[0].agent_id
    adapters[failed_agent].inject_failure("EXTERNAL_SIMULATED_FAILURE")

    async def _wait_replacement() -> None:
        while True:
            now = orchestrator.execution_groups[group.id]
            if any(member.replaces_agent_id == failed_agent for member in now.members):
                return
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_wait_replacement(), timeout=2.0)

    async def _wait_replacement_disposition() -> DispositionDecision:
        while True:
            matching = [
                decision
                for decision in dispositions
                if decision.objective_mission_id == group.objective_mission_id
                and decision.reason == "REPLACEMENT"
            ]
            if matching:
                return matching[-1]
            await asyncio.sleep(0.005)

    replacement_disposition = await asyncio.wait_for(
        _wait_replacement_disposition(), timeout=2.0
    )
    now = orchestrator.execution_groups[group.id]
    replacement = next(
        member for member in now.members if member.replaces_agent_id == failed_agent
    )
    failed = next(member for member in now.members if member.agent_id == failed_agent)

    assert failed.state is ExecutionGroupMemberState.REPLACED
    assert replacement.agent_id in spare
    assert replacement.role == failed.role
    assert replacement_disposition.revision >= 2
    assert replacement_disposition.active_members == 3
    assert replacement.agent_id in {
        assignment.agent_id for assignment in replacement_disposition.assignments
    }
    assert failed_agent not in {
        assignment.agent_id for assignment in replacement_disposition.assignments
    }

    # The physical fault must survive later fleet projection/allocation review.
    # Before this regression, the Drone object alone projected the failed unit
    # back to EN_ROUTE, and legacy airborne diversion could select it again.
    fleet_after_failure = orchestrator._snapshot_fleet()
    failed_fleet_state = next(
        state for state in fleet_after_failure if state.agent_id == failed_agent
    )
    assert failed_fleet_state.fsm_state is AgentState.OFFLINE
    probe = VERIFY(geo=failed_fleet_state.geo, hover_s=0.0, priority=100)
    assert (
        orchestrator._nearest_airborne(fleet_after_failure, probe) != failed_agent
    )

    runtime.cancel()
    collector.cancel()
    await asyncio.gather(runtime, collector, return_exceptions=True)
    for adapter in adapters.values():
        await adapter.disconnect()
    await bus.close()