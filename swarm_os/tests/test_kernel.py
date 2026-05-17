from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    AnomalyState,
    Geo,
    MissionProgress,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
    RiskState,
    Telemetry,
    UnitState,
)

from swarm_os.awareness import calculate_awareness
from swarm_os.command_bus import submit
from swarm_os.coordinator import SwarmCoordinator
from swarm_os.fsm import compute_mode
from swarm_os.sectors import default_sector_grid, score_sectors, sector_for_geo
from swarm_os.state import VINEYARD_CENTER, SwarmState


def test_default_sector_grid_has_stable_targets() -> None:
    sectors = {s.id: s for s in default_sector_grid(VINEYARD_CENTER)}
    assert len(sectors) == 9
    assert "north-a" in sectors
    assert sector_for_geo(VINEYARD_CENTER, sectors) == "center-b"


def test_sector_scoring_marks_never_visited_blind_and_old_stale() -> None:
    now = datetime.now(UTC)
    sectors = {s.id: s for s in default_sector_grid(VINEYARD_CENTER)}
    sectors["center-b"] = sectors["center-b"].model_copy(
        update={"last_visited_at": now - timedelta(minutes=10), "confidence": 1.0}
    )
    scored = score_sectors(sectors, now)
    assert scored["north-a"].state.value == "blind"
    assert scored["center-b"].state.value == "stale"


@pytest.mark.asyncio
async def test_coordinator_projects_telemetry_and_anomaly() -> None:
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)

    frames = await coordinator.apply_telemetry(
        Telemetry(agent_id="sim-1", geo=VINEYARD_CENTER, battery_pct=91.0)
    )
    assert state.units["sim-1"].current_sector_id == "center-b"
    assert any(frame["kind"] == "unit" for frame in frames)

    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=Geo(lat=VINEYARD_CENTER.lat + 0.0027, lon=VINEYARD_CENTER.lon + 0.0027),
        confidence=0.78,
        source_agent="sim-1",
    )
    frames = await coordinator.apply_anomaly(anomaly)
    assert state.mode.value == "verification"
    assert state.anomalies[anomaly.id].state == AnomalyState.PENDING
    assert any(frame["kind"] == "anomaly_view" for frame in frames)
    assert any(event.anomaly_id == anomaly.id for event in state.events)


@pytest.mark.asyncio
async def test_coordinator_projects_mission_progress() -> None:
    state = SwarmState.vineyard()
    state.verifier_id = "sim-1"
    coordinator = SwarmCoordinator(state)
    frames = await coordinator.apply_mission_progress(
        MissionProgress(mission_id="m-1", phase="ON_STATION", progress_pct=42.0)
    )
    assert state.missions["m-1"].phase.value == "on_station"
    assert any(frame["kind"] == "mission" for frame in frames)


def test_fsm_rule_order() -> None:
    state = SwarmState.vineyard()
    assert compute_mode(state).value == "rest"

    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
    )
    assert compute_mode(state).value == "patrol"

    state.units["sim-1"] = state.units["sim-1"].model_copy(update={"battery_pct": 12.0})
    assert compute_mode(state).value == "maintenance"


def test_awareness_breakdown_has_factors() -> None:
    now = datetime.now(UTC)
    state = SwarmState.vineyard()
    awareness = calculate_awareness(
        sectors=state.sectors,
        units=state.units,
        anomalies=state.anomalies,
        now=now,
    )
    assert awareness.risk_state == RiskState.ELEVATED
    assert "sector_confidence" in awareness.factors


@pytest.mark.asyncio
async def test_command_bus_accepts_verify_and_rejects_missing_target() -> None:
    state = SwarmState.vineyard()
    accepted = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.VERIFY,
            target="sector:north-a",
            operator_id="op-davide",
        ),
    )
    assert accepted.status.value == "accepted"
    assert state.missions
    # Phase 3: submit() is pure mutation. The command is in `state.commands`;
    # the audit `Event` is appended by the detector during a coordinator
    # refresh — see test_phase3.py.
    assert accepted.command_id in state.commands
    assert state.commands[accepted.command_id].status.value == "accepted"

    rejected = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.RETURN,
            target="unit:missing",
            operator_id="op-davide",
        ),
    )
    assert rejected.rejected_reason == RejectedReason.TARGET_NOT_FOUND
