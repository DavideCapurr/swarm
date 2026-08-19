"""Capture a causal Take-C-level simulator run as replayable runtime frames.

This script deliberately does not contain response choreography. Its only
scenario inputs are world facts:

1. a continuous coverage objective exists;
2. an intrusion appears;
3. reserve physical capacity becomes available;
4. one active physical executor fails.

SwarmOS chooses composition, donor preemption, reinforcement, disposition,
replacement and completion. The capture records SwarmOS bus truth plus sampled
physical simulator state. It never computes formation geometry in presentation
code and it makes no PX4/MAVLink claim for disposition execution.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from swarm_core.disposition import DispositionDecision
from swarm_core.execution_groups import ExecutionGroup, ExecutionGroupState
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyEvidence,
    AnomalyKind,
    AnomalySource,
    AnomalyState,
    AnomalyView,
    Geo,
    MissionTask,
    SensorKind,
    UnitState,
)
from swarm_core.missions import COVER
from swarm_core.runtime_events import MissionRuntimeEvent
from swarm_core.voice import band, evidence_headline

from adapters.base import AdapterRegistry
from adapters.simulated import SimulatedAdapter
from orchestrator.swarm_orchestrator.alarm_driven import (
    AlarmDrivenExecutionGroupOrchestrator,
)
from orchestrator.swarm_orchestrator.alarm_policy import AlarmResponsePolicy
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.disposition_execution_groups import DISPOSITION_TOPIC
from orchestrator.swarm_orchestrator.execution_groups import EXECUTION_GROUP_TOPIC
from sim.swarm_sim.external_events import (
    CAPACITY_AVAILABLE_TOPIC,
    CapacityAvailable,
    consume_capacity_availability,
)
from sim.swarm_sim.world import World

# These pauses schedule only later EXTERNAL WORLD FACTS. They do not name or
# request a SwarmOS response. They exist so the real under-strength and
# reinforced states are legible in a recorded demo instead of occurring within
# a few tens of milliseconds of each other.
WORLD_FACT_PAUSE_S = 1.0


@dataclass
class CaptureRecorder:
    started_monotonic: float = field(default_factory=time.monotonic)
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    frames: list[dict[str, Any]] = field(default_factory=list)

    def elapsed_ms(self) -> int:
        return max(0, round((time.monotonic() - self.started_monotonic) * 1000))

    def append(self, kind: str, data: BaseModel) -> None:
        self.frames.append(
            {
                "at": self.elapsed_ms(),
                "kind": kind,
                "data": data.model_dump(mode="json"),
            }
        )


async def _wait_until(predicate: Any, *, within_s: float = 5.0) -> None:
    async def _poll() -> None:
        while not predicate():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(_poll(), timeout=within_s)


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


def _unit_state(
    *,
    adapter: SimulatedAdapter,
    drone: Any,
    orchestrator: AlarmDrivenExecutionGroupOrchestrator,
) -> UnitState:
    if not adapter.connected:
        state = AgentState.OFFLINE
    elif drone.is_docked:
        state = AgentState.DOCKED
    elif drone._mode == "LANDING":
        state = AgentState.LANDING
    elif drone._mode == "HOVER":
        state = AgentState.ON_STATION
    elif drone._mode == "TAKEOFF":
        state = AgentState.TAKEOFF
    else:
        state = AgentState.EN_ROUTE

    return UnitState(
        agent_id=drone.agent_id,
        vendor=adapter.vendor,
        model=adapter.model,
        fsm_state=state,
        battery_pct=drone.battery_pct,
        geo=Geo(lat=drone.geo.lat, lon=drone.geo.lon, alt_m=drone.geo.alt_m),
        current_mission_id=orchestrator._agent_mission_ids.get(drone.agent_id),
        current_sector_id=None,
        link_quality=1.0 if adapter.connected else 0.0,
        heading_deg=drone.yaw_deg,
        altitude_agl_m=drone.geo.alt_m,
        dock_id=None,
    )


async def _sample_units(
    *,
    recorder: CaptureRecorder,
    world: World,
    adapters: dict[str, SimulatedAdapter],
    orchestrator: AlarmDrivenExecutionGroupOrchestrator,
    stop: asyncio.Event,
) -> None:
    while not stop.is_set():
        for drone in world.drones:
            recorder.append(
                "unit",
                _unit_state(
                    adapter=adapters[drone.agent_id],
                    drone=drone,
                    orchestrator=orchestrator,
                ),
            )
        await asyncio.sleep(0.10)


async def _collect_groups(
    *,
    bus: InMemoryBus,
    recorder: CaptureRecorder,
    observed: list[ExecutionGroup],
) -> None:
    async for _topic, payload in bus.subscribe(EXECUTION_GROUP_TOPIC):
        group = ExecutionGroup.model_validate_json(payload)
        observed.append(group)
        recorder.append("group", group)


async def _collect_dispositions(
    *,
    bus: InMemoryBus,
    recorder: CaptureRecorder,
    observed: list[DispositionDecision],
) -> None:
    async for _topic, payload in bus.subscribe(DISPOSITION_TOPIC):
        decision = DispositionDecision.model_validate_json(payload)
        observed.append(decision)
        recorder.append("disposition", decision)


async def _collect_runtime(
    *,
    bus: InMemoryBus,
    recorder: CaptureRecorder,
    observed: list[MissionRuntimeEvent],
) -> None:
    async for _topic, payload in bus.subscribe("swarm:missions:runtime"):
        event = MissionRuntimeEvent.model_validate_json(payload)
        observed.append(event)
        recorder.append("runtime", event)


def _latest_disposition(
    decisions: list[DispositionDecision],
    *,
    objective_mission_id: str,
    reason: str,
) -> DispositionDecision:
    matching = [
        decision
        for decision in decisions
        if decision.objective_mission_id == objective_mission_id
        and decision.reason == reason
    ]
    if not matching:
        raise RuntimeError(
            f"missing {reason} disposition for objective {objective_mission_id}"
        )
    return matching[-1]


async def _capture() -> dict[str, Any]:
    recorder = CaptureRecorder()
    bus = InMemoryBus()
    await bus.connect()

    world = World.vineyard(n_drones=6, ignition_after_s=86_400.0)
    registry = AdapterRegistry()
    adapters: dict[str, SimulatedAdapter] = {}
    drones = {drone.agent_id: drone for drone in world.drones}
    reserve_adapters: list[SimulatedAdapter] = []

    for index, drone in enumerate(world.drones):
        # Faster kinematics shorten the capture without changing SwarmOS policy.
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
        if index < 4:
            await adapter.connect()
        else:
            reserve_adapters.append(adapter)

    # Only execution duration is shortened for the simulator. Demand thresholds,
    # team size and reinforcement limits remain the reusable SwarmOS defaults;
    # the Take C harness does not tune them to obtain a particular response.
    orchestrator = AlarmDrivenExecutionGroupOrchestrator(
        bus=bus,
        registry=registry,
        world_drones=world.drones,
        continuous_patrol=False,
        execute_disposition_retask=True,
        reinforcement_review_period_s=0.02,
        alarm_policy=AlarmResponsePolicy(cooperative_hover_s=2.0),
    )

    groups: list[ExecutionGroup] = []
    dispositions: list[DispositionDecision] = []
    runtime_events: list[MissionRuntimeEvent] = []
    stop_sampling = asyncio.Event()

    tasks = [
        asyncio.create_task(
            _collect_groups(bus=bus, recorder=recorder, observed=groups)
        ),
        asyncio.create_task(
            _collect_dispositions(
                bus=bus,
                recorder=recorder,
                observed=dispositions,
            )
        ),
        asyncio.create_task(
            _collect_runtime(
                bus=bus,
                recorder=recorder,
                observed=runtime_events,
            )
        ),
        asyncio.create_task(consume_capacity_availability(bus, reserve_adapters)),
        asyncio.create_task(orchestrator.run()),
        asyncio.create_task(
            _sample_units(
                recorder=recorder,
                world=world,
                adapters=adapters,
                orchestrator=orchestrator,
                stop=stop_sampling,
            )
        ),
    ]
    await asyncio.sleep(0.03)

    milestones: dict[str, Any] = {}

    try:
        # World fact 1: continuous coverage is required.
        coverage = _coverage_objective(world.dock)
        milestones["coverage_objective_at_ms"] = recorder.elapsed_ms()
        donor = await orchestrator.dispatch_execution_group(coverage)
        await _wait_until(
            lambda: all(
                not drones[member.agent_id].is_docked for member in donor.members
            )
        )

        # World fact 2: a high-confidence simulated intrusion appears.
        evidence = AnomalyEvidence(
            source=AnomalySource.DRONE_CV,
            sensor=SensorKind.RGB,
            label="person",
            metric="object_score",
            value=0.99,
            baseline=None,
            unit="score",
            headline="",
            simulated=True,
        )
        evidence = evidence.model_copy(update={"headline": evidence_headline(evidence)})
        alarm = Anomaly(
            id="causal-take-c-intrusion",
            kind=AnomalyKind.INTRUSION,
            geo=Geo(
                lat=world.dock.lat + 0.0004,
                lon=world.dock.lon + 0.0004,
            ),
            confidence=0.99,
            evidence=evidence,
        )
        recorder.append(
            "anomaly",
            AnomalyView(
                id=alarm.id,
                kind=alarm.kind,
                geo=alarm.geo,
                sector_id=None,
                confidence=alarm.confidence,
                band=band(alarm.confidence),
                state=AnomalyState.PENDING,
                detected_at=alarm.ts,
                detected_by=alarm.source_agent,
                verifying_agent=None,
                evidence=alarm.evidence,
                ts=alarm.ts,
            ),
        )
        milestones["intrusion_at_ms"] = recorder.elapsed_ms()
        await bus.publish("swarm:anomalies", alarm.model_dump_json())

        await _wait_until(
            lambda: any(
                group.anomaly_id == alarm.id and group.reinforces_group_id is None
                for group in orchestrator.execution_groups.values()
            )
        )
        response = next(
            group
            for group in orchestrator.execution_groups.values()
            if group.anomaly_id == alarm.id and group.reinforces_group_id is None
        )
        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "COMPOSITION"
                for decision in dispositions
            )
        )
        composition = _latest_disposition(
            dispositions,
            objective_mission_id=response.objective_mission_id,
            reason="COMPOSITION",
        )
        milestones["composition_at_ms"] = recorder.elapsed_ms()
        milestones["composition_revision"] = composition.revision
        milestones["composition_members"] = composition.active_members

        # The scenario controls when the next world fact occurs, not what the
        # response to the current state should be.
        await asyncio.sleep(WORLD_FACT_PAUSE_S)

        # World fact 3: physical reserve capacity becomes available. The event
        # contains no identity or response instruction.
        capacity_event = CapacityAvailable()
        capacity_payload = capacity_event.model_dump_json()
        if "sim-" in capacity_payload:
            raise RuntimeError("capacity event leaked an executor identity")
        milestones["capacity_available_at_ms"] = recorder.elapsed_ms()
        await bus.publish(CAPACITY_AVAILABLE_TOPIC, capacity_payload)

        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "REINFORCEMENT"
                for decision in dispositions
            )
        )
        reinforcement = _latest_disposition(
            dispositions,
            objective_mission_id=response.objective_mission_id,
            reason="REINFORCEMENT",
        )
        milestones["reinforcement_at_ms"] = recorder.elapsed_ms()
        milestones["reinforcement_revision"] = reinforcement.revision
        milestones["reinforcement_members"] = reinforcement.active_members

        await _wait_until(
            lambda: all(
                drones[assignment.agent_id].at_target(assignment.geo)
                for assignment in reinforcement.assignments
            )
        )
        milestones["reinforcement_converged_at_ms"] = recorder.elapsed_ms()

        # Again, only the timing of a later external physical fact is scripted.
        await asyncio.sleep(WORLD_FACT_PAUSE_S)

        # World fact 4: one active physical executor fails. Its identity is read
        # from SwarmOS's own active disposition; no replacement is nominated.
        failed_assignment = reinforcement.assignments[0]
        failed_agent = failed_assignment.agent_id
        failed_role = failed_assignment.role
        milestones["failure_at_ms"] = recorder.elapsed_ms()
        milestones["failed_agent"] = failed_agent
        milestones["failed_role"] = failed_role
        adapters[failed_agent].inject_failure("EXTERNAL_SIMULATED_FAILURE")

        await _wait_until(
            lambda: any(
                decision.objective_mission_id == response.objective_mission_id
                and decision.reason == "REPLACEMENT"
                for decision in dispositions
            )
        )
        replacement = _latest_disposition(
            dispositions,
            objective_mission_id=response.objective_mission_id,
            reason="REPLACEMENT",
        )
        milestones["replacement_at_ms"] = recorder.elapsed_ms()
        milestones["replacement_revision"] = replacement.revision
        replacement_for_role = next(
            assignment
            for assignment in replacement.assignments
            if assignment.role == failed_role
        )
        milestones["replacement_agent"] = replacement_for_role.agent_id

        await _wait_until(
            lambda: all(
                drones[assignment.agent_id].at_target(assignment.geo)
                for assignment in replacement.assignments
            )
        )
        milestones["replacement_converged_at_ms"] = recorder.elapsed_ms()

        objective_group_ids = {
            group.id
            for group in orchestrator.execution_groups.values()
            if group.objective_mission_id == response.objective_mission_id
        }
        await _wait_until(
            lambda: all(
                orchestrator.execution_groups[group_id].state
                is ExecutionGroupState.COMPLETED
                for group_id in objective_group_ids
            ),
            within_s=7.0,
        )
        milestones["verified_at_ms"] = recorder.elapsed_ms()
        await asyncio.sleep(0.20)
    finally:
        stop_sampling.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for adapter in adapters.values():
            await adapter.disconnect()
        await bus.close()

    frames = sorted(recorder.frames, key=lambda frame: frame["at"])
    return {
        "schema_version": 1,
        "provenance": "causal-simulator-runtime",
        "proof_scope": {
            "swarmos_decisions": "runtime bus truth",
            "physical_positions": "kinematic simulator telemetry/state",
            "disposition_execution": "simulator only",
            "px4_disposition_claim": False,
        },
        "started_at": recorder.started_at.isoformat(),
        "duration_ms": recorder.elapsed_ms(),
        "world_facts": [
            "baseline continuous coverage objective exists",
            "intrusion appears",
            "capacity becomes available",
            "an active physical executor fails",
        ],
        "milestones": milestones,
        "frames": frames,
    }


async def _main() -> None:
    destination = Path(
        sys.argv[1] if len(sys.argv) > 1 else "artifacts/take-c-causal-sim.json"
    )
    capture = await _capture()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(capture, indent=2) + "\n", encoding="utf-8")
    print(
        "TAKE_C_CAPTURE "
        f"frames={len(capture['frames'])} "
        f"duration_ms={capture['duration_ms']} "
        f"composition={capture['milestones']['composition_members']} "
        f"reinforcement={capture['milestones']['reinforcement_members']} "
        f"revisions={capture['milestones']['composition_revision']}"
        f"->{capture['milestones']['reinforcement_revision']}"
        f"->{capture['milestones']['replacement_revision']}"
    )
    print(f"TAKE_C_CAPTURE_PATH {destination}")


if __name__ == "__main__":
    asyncio.run(_main())
