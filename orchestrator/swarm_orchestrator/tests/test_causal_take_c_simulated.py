from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest
from swarm_core.disposition import DispositionDecision
from swarm_core.execution_groups import ExecutionGroupMemberState, ExecutionGroupState
from swarm_core.messages import AgentState, Anomaly, AnomalyKind, Geo, MissionTask
from swarm_core.missions import COVER
from swarm_core.objectives import demand_for_mission

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


async def _wait_until(predicate: Callable[[], bool], *, timeout: float = 4.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_poll(), timeout=timeout)


def _coverage_objective(dock: Geo) -> MissionTask:
    return COVER(
        area=[
            Geo(lat=dock.lat + 0.006, lon=dock.lon - 0.006),
            Geo(lat=dock.lat + 0.006, lon=dock.lon + 0.006),
            Geo(lat=dock.lat - 0.006, lon=dock.lon + 0.006),
            Geo(lat=dock.lat - 0.006, lon=dock.lon - 0.006),
        ],
        fleet_size=3,
        minimum_capacity=2,
        preemptible=True,
        priority=10,
    )


@pytest.mark.asyncio
async def test_take_c_behavior_emerges_only_from_world_facts() -> None:
    """Causal simulator proof: the scenario supplies facts, never responses."""

    bus = InMemoryBus()
    await bus.connect()
    world = World.vineyard(n_drones=6, ignition_after_s=86_400.0)
    registry = AdapterRegistry()
    adapters: dict[str, SimulatedAdapter] = {}
    drones = {drone.agent_id: drone for drone in world.drones}

    for index, drone in enumerate(world.drones):
        # Faster kinematics keep the proof short without changing policy.
        drone.speed_mps = 140.0
        drone.climb_mps = 120.0
        adapter = SimulatedAdapter(
            agent_id=drone.agent_id,
            drone=drone,
            self_tick=True,
            tick_hz=100.0,
        )
        registry.register(adapter)
        adapters[adapter.agent_id] = adapter
        # Initial world fact: four executors are available and two are offline.
        if index < 4:
            await adapter.connect()

    orchestrator = AlarmDrivenExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=False,
        execute_disposition_retask=True,
        reinforcement_review_period_s=0.02,
        max_reinforcements_per_objective=1,
        alarm_policy=AlarmResponsePolicy(
            cooperative_threshold=0.80,
            high_confidence_threshold=0.93,
            max_team_size=3,
            cooperative_hover_s=2.0,
        ),
    )
    dispositions: list[DispositionDecision] = []
    collector = asyncio.create_task(_collect_dispositions(bus, dispositions))
    runtime = asyncio.create_task(orchestrator.run())
    await asyncio.sleep(0.02)

    try:
        # Scripted input 1: a baseline coverage objective exists. SwarmOS chooses
        # its executors and owns its minimum-capacity/preemption contract.
        coverage = _coverage_objective(world.dock)
        donor = await orchestrator.dispatch_execution_group(coverage)
        assert len(donor.members) == 3

        await _wait_until(
            lambda: all(
                not drones[member.agent_id].is_docked for member in donor.members
            )
        )

        # Scripted input 2: an intrusion appears. The alarm contains no executor,
        # swarm, role, reinforcement, replacement or geometry instruction.
        alarm = Anomaly(
            id="causal-take-c-alarm",
            kind=AnomalyKind.INTRUSION,
            geo=Geo(
                lat=world.dock.lat + 0.0004,
                lon=world.dock.lon + 0.0004,
            ),
            confidence=0.99,
        )
        payload = alarm.model_dump_json()
        assert "sim-" not in payload
        await bus.publish("swarm:anomalies", payload)

        await _wait_until(
            lambda: any(
                group.anomaly_id == alarm.id
                and group.reinforces_group_id is None
                for group in orchestrator.execution_groups.values()
            )
        )
        response = next(
            group
            for group in orchestrator.execution_groups.values()
            if group.anomaly_id == alarm.id
            and group.reinforces_group_id is None
        )
        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "COMPOSITION"
                for decision in dispositions
            )
        )
        composition = next(
            decision
            for decision in dispositions
            if decision.objective_mission_id == response.objective_mission_id
            and decision.reason == "COMPOSITION"
        )

        # Demand came from alarm policy. Capacity was constrained, so SwarmOS
        # admitted minimum viable strength using idle + safe donor capacity.
        assert response.requested_members == 3
        assert len(response.members) == 2
        assert composition.active_members == 2
        await _wait_until(
            lambda: sum(
                member.state is ExecutionGroupMemberState.DIVERTED
                for member in orchestrator.execution_groups[donor.id].members
            )
            >= 1
        )
        donor_now = orchestrator.execution_groups[donor.id]
        donor_demand = demand_for_mission(coverage)
        donor_live = sum(
            member.state
            not in {
                ExecutionGroupMemberState.DIVERTED,
                ExecutionGroupMemberState.FAILED,
                ExecutionGroupMemberState.REPLACED,
                ExecutionGroupMemberState.COMPLETED,
            }
            for member in donor_now.members
        )
        assert donor_live >= donor_demand.minimum_capacity
        assert donor_now.state is ExecutionGroupState.DEGRADED

        # Scripted input 3: unavailable physical capacity becomes available.
        # No executor is nominated for reinforcement; the periodic SwarmOS loop
        # observes the new state and decides whether the objective needs it.
        unavailable = [adapter for adapter in adapters.values() if not adapter.connected]
        assert len(unavailable) == 2
        for adapter in unavailable:
            await adapter.connect()

        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "REINFORCEMENT"
                for decision in dispositions
            )
        )
        reinforcement = next(
            decision
            for decision in dispositions
            if decision.objective_mission_id == response.objective_mission_id
            and decision.reason == "REINFORCEMENT"
        )
        assert reinforcement.revision > composition.revision
        assert reinforcement.active_members == 3
        assert reinforcement.radius_m > composition.radius_m
        assert any(
            group.reinforces_group_id == response.id
            for group in orchestrator.execution_groups.values()
        )

        # This is simulator execution evidence, not UI geometry: every physical
        # drone reaches its server-issued 3D disposition slot.
        await _wait_until(
            lambda: all(
                drones[assignment.agent_id].at_target(assignment.geo)
                for assignment in reinforcement.assignments
            )
        )

        # Scripted input 4: one currently active physical executor fails. The
        # identity is observed from SwarmOS output; the stimulus never names a
        # replacement or asks for replacement review.
        failed_assignment = reinforcement.assignments[0]
        failed_agent = failed_assignment.agent_id
        failed_role = failed_assignment.role
        adapters[failed_agent].inject_failure("EXTERNAL_SIMULATED_FAILURE")

        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "REPLACEMENT"
                for decision in dispositions
            )
        )
        replacement = next(
            decision
            for decision in dispositions
            if decision.objective_mission_id == response.objective_mission_id
            and decision.reason == "REPLACEMENT"
        )
        assert replacement.revision > reinforcement.revision
        assert replacement.active_members == reinforcement.active_members
        assert failed_agent not in {
            assignment.agent_id for assignment in replacement.assignments
        }
        replacement_for_role = next(
            assignment
            for assignment in replacement.assignments
            if assignment.role == failed_role
        )
        assert replacement_for_role.agent_id != failed_agent
        assert replacement_for_role.agent_id not in {
            assignment.agent_id
            for assignment in reinforcement.assignments
            if assignment.agent_id != failed_agent
        }

        failed_state = next(
            state
            for state in orchestrator._snapshot_fleet()
            if state.agent_id == failed_agent
        )
        assert failed_state.fsm_state is AgentState.OFFLINE

        await _wait_until(
            lambda: all(
                drones[assignment.agent_id].at_target(assignment.geo)
                for assignment in replacement.assignments
            )
        )

        # Capture every group serving the same objective before terminal cleanup
        # can remove its reinforcement record, then require all roles to verify.
        objective_group_ids = {
            group.id
            for group in orchestrator.execution_groups.values()
            if group.objective_mission_id == response.objective_mission_id
        }
        assert len(objective_group_ids) >= 2
        await _wait_until(
            lambda: all(
                orchestrator.execution_groups[group_id].state
                is ExecutionGroupState.COMPLETED
                for group_id in objective_group_ids
            ),
            timeout=6.0,
        )
    finally:
        runtime.cancel()
        collector.cancel()
        await asyncio.gather(runtime, collector, return_exceptions=True)
        for adapter in adapters.values():
            await adapter.disconnect()
        await bus.close()
