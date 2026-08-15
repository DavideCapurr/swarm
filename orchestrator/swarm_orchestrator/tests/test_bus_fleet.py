from __future__ import annotations

import asyncio
import json
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
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator


class _ImmediateMissionAdapter:
    vendor = "test"
    model = "instant"

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.executed: list[str] = []

    def execute_mission(self, mission: Any) -> AsyncIterator[MissionProgress]:
        async def _run() -> AsyncIterator[MissionProgress]:
            self.executed.append(mission.id)
            yield MissionProgress(
                mission_id=mission.id,
                phase="EN_ROUTE",
                progress_pct=25.0,
            )
            yield MissionProgress(
                mission_id=mission.id,
                phase="DONE",
                progress_pct=100.0,
            )

        return _run()


@pytest.mark.asyncio
async def test_bus_fleet_snapshot_filters_to_owned_registered_adapters() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    registry.register(_ImmediateMissionAdapter("mav-001"))  # type: ignore[arg-type]
    registry.register(_ImmediateMissionAdapter("mav-002"))  # type: ignore[arg-type]
    orch = BusFleetOrchestrator(bus=bus, registry=registry)

    task = asyncio.create_task(orch._fleet_state_loop())
    await asyncio.sleep(0)
    for agent_id in ("mav-001", "mav-002", "foreign-001"):
        await bus.publish(
            "swarm:fleet:state",
            FleetState(
                agent_id=agent_id,
                vendor="mavlink",
                model="px4-x500",
                fsm_state=AgentState.DOCKED,
                battery_pct=80.0,
                geo=Geo(lat=45.0, lon=10.0),
            ).model_dump_json(),
        )

    await orch.wait_for_registered_fleet(timeout_s=1.0)
    assert [state.agent_id for state in orch._snapshot_fleet()] == ["mav-001", "mav-002"]

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await bus.close()


@pytest.mark.asyncio
async def test_anomaly_dispatches_through_registered_adapter_without_world_drones() -> None:
    bus = InMemoryBus()
    await bus.connect()
    registry = AdapterRegistry()
    near = _ImmediateMissionAdapter("mav-near")
    far = _ImmediateMissionAdapter("mav-far")
    registry.register(near)  # type: ignore[arg-type]
    registry.register(far)  # type: ignore[arg-type]
    orch = BusFleetOrchestrator(
        bus=bus,
        registry=registry,
        verify_hover_s=0.0,
        continuous_patrol=False,
    )
    orch_task = asyncio.create_task(orch.run())
    await asyncio.sleep(0.05)

    target = Geo(lat=45.0, lon=10.0)
    await bus.publish(
        "swarm:fleet:state",
        FleetState(
            agent_id="mav-near",
            vendor="mavlink",
            model="px4-x500",
            fsm_state=AgentState.DOCKED,
            battery_pct=90.0,
            geo=Geo(lat=45.0001, lon=10.0001),
        ).model_dump_json(),
    )
    await bus.publish(
        "swarm:fleet:state",
        FleetState(
            agent_id="mav-far",
            vendor="mavlink",
            model="px4-x500",
            fsm_state=AgentState.DOCKED,
            battery_pct=90.0,
            geo=Geo(lat=45.02, lon=10.02),
        ).model_dump_json(),
    )
    await orch.wait_for_registered_fleet(timeout_s=1.0)

    awards: list[dict[str, object]] = []
    progress: list[dict[str, object]] = []

    async def _watch_award() -> None:
        async for _, payload in bus.subscribe("swarm:missions:award"):
            awards.append(json.loads(payload))
            return

    async def _watch_progress() -> None:
        async for _, payload in bus.subscribe("swarm:missions:progress:*"):
            frame = json.loads(payload)
            progress.append(frame)
            if frame["phase"] == "DONE":
                return

    award_task = asyncio.create_task(_watch_award())
    progress_task = asyncio.create_task(_watch_progress())
    await asyncio.sleep(0)

    await bus.publish(
        "swarm:anomalies",
        Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=target,
            confidence=0.9,
        ).model_dump_json(),
    )

    await asyncio.wait_for(award_task, timeout=2.0)
    await asyncio.wait_for(progress_task, timeout=2.0)

    assert awards[0]["winner_agent_id"] == "mav-near"
    assert len(near.executed) == 1
    assert far.executed == []
    assert progress[-1]["phase"] == "DONE"

    orch_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await orch_task
    await bus.close()
