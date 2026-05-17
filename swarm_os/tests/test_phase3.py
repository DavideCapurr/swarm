"""Phase 3 — Truth Layer tests.

These tests are the acceptance gate for Phase 3:
  - every Console-facing field arrives from SwarmOS (no client derive)
  - the event detector covers all 15 transition kinds
  - the scheduler auto-creates patrol missions when sectors decay
  - the command bus drives the full lifecycle
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from swarm_core.messages import (
    AgentState,
    Anomaly,
    AnomalyKind,
    AnomalyState,
    AnomalyView,
    CommandStatus,
    ConfidenceBand,
    DockStatus,
    Geo,
    MissionPhase,
    MissionProgress,
    MissionView,
    OperatorAction,
    OperatorCommand,
    PowerStatus,
    SectorState,
    Telemetry,
    UnitState,
)

from swarm_os.command_bus import submit
from swarm_os.command_bus import tick as command_tick
from swarm_os.coordinator import SwarmCoordinator
from swarm_os.event_detector import EventDetector
from swarm_os.scheduler import _schedule_repatrols
from swarm_os.state import DEFAULT_DOCK_ID, VINEYARD_CENTER, SwarmState

# ── Truth layer: awareness frame carries mode + verifier ─────────────────────


@pytest.mark.asyncio
async def test_awareness_frame_carries_mode_and_verifier() -> None:
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)

    # Drop a unit in the air → mode should be `patrol`.
    await coordinator.apply_telemetry(
        Telemetry(agent_id="sim-1", geo=VINEYARD_CENTER, battery_pct=90.0)
    )
    state.units["sim-1"] = state.units["sim-1"].model_copy(
        update={"fsm_state": AgentState.EN_ROUTE}
    )
    await coordinator.apply_telemetry(
        Telemetry(agent_id="sim-1", geo=VINEYARD_CENTER, battery_pct=90.0)
    )
    assert state.awareness.mode.value == "patrol"

    # Now an anomaly → mode becomes `verification` and awareness carries the
    # verifier id without any client-side picking.
    anomaly = Anomaly(
        kind=AnomalyKind.SMOKE,
        geo=VINEYARD_CENTER,
        confidence=0.72,
        source_agent="sim-1",
    )
    await coordinator.apply_anomaly(anomaly)
    assert state.awareness.mode.value == "verification"
    assert state.awareness.verifying_agent == "sim-1"
    assert state.anomalies[anomaly.id].verifying_agent == "sim-1"


@pytest.mark.asyncio
async def test_primary_dock_flag_is_server_set() -> None:
    state = SwarmState.vineyard()
    assert state.docks[DEFAULT_DOCK_ID].primary is True
    # Adding a second dock keeps the primary flag stable.
    state.docks["dock-secondary"] = state.docks[DEFAULT_DOCK_ID].model_copy(
        update={"dock_id": "dock-secondary", "primary": False}
    )
    primaries = [d for d in state.docks.values() if d.primary]
    assert len(primaries) == 1
    assert primaries[0].dock_id == DEFAULT_DOCK_ID


@pytest.mark.asyncio
async def test_snapshot_frames_contain_truth_fields() -> None:
    state = SwarmState.vineyard()
    coordinator = SwarmCoordinator(state)
    frames = await coordinator.snapshot_frames()

    by_kind: dict[str, list[dict[str, object]]] = {}
    for frame in frames:
        by_kind.setdefault(frame["kind"], []).append(frame["data"])

    [awareness] = by_kind["awareness"]
    assert "mode" in awareness
    assert "verifying_agent" in awareness
    primaries = [d for d in by_kind["dock"] if d["primary"]]
    assert len(primaries) == 1


# ── Scheduler: auto re-patrol on decayed sectors ─────────────────────────────


def test_scheduler_creates_auto_patrol_for_stale_sector() -> None:
    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    # Mark every sector as freshly covered except center-b, which we leave
    # blind so it is the unique candidate the scheduler should service.
    for sid, sector in state.sectors.items():
        if sid == "center-b":
            state.sectors[sid] = sector.model_copy(
                update={"confidence": 0.0, "state": SectorState.BLIND}
            )
        else:
            state.sectors[sid] = sector.model_copy(
                update={
                    "confidence": 0.9,
                    "state": SectorState.COVERED,
                    "last_visited_at": now,
                }
            )
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
    )

    created = _schedule_repatrols(state, now)
    target_ids = {m.sector_id for m in created}
    assert target_ids == {"center-b"}
    auto = created[0]
    assert auto.kind == "PATROL"
    assert auto.assigned_agent == "sim-1"


def test_scheduler_skips_when_hold_patrol_is_set() -> None:
    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    state.hold_patrol = True
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"confidence": 0.0, "state": SectorState.BLIND}
    )
    assert _schedule_repatrols(state, now) == []


def test_scheduler_does_not_duplicate_per_sector() -> None:
    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"confidence": 0.0, "state": SectorState.BLIND}
    )
    state.missions["existing"] = MissionView(
        id="existing",
        kind="PATROL",
        sector_id="center-b",
        phase=MissionPhase.EN_ROUTE,
    )
    created = _schedule_repatrols(state, now)
    assert "center-b" not in {m.sector_id for m in created}


# ── Command lifecycle ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_command_lifecycle_progresses_to_completed() -> None:
    state = SwarmState.vineyard()
    # We need a unit so RETURN has a valid target.
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=80.0,
        geo=VINEYARD_CENTER,
    )

    result = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.RETURN,
            target="unit:sim-1",
            operator_id="op-davide",
        ),
    )
    command_id = result.command_id
    assert state.commands[command_id].status == CommandStatus.ACCEPTED
    assert state.commands[command_id].mission_id is not None

    # Move the linked mission past PENDING → tick should flip ACCEPTED → IN_FLIGHT.
    mission_id = state.commands[command_id].mission_id
    assert mission_id is not None
    state.missions[mission_id] = state.missions[mission_id].model_copy(
        update={"phase": MissionPhase.EN_ROUTE}
    )
    now = datetime.now(UTC)
    command_tick(state, now)
    assert state.commands[command_id].status == CommandStatus.IN_FLIGHT
    assert state.commands[command_id].in_flight_at is not None

    # Now complete the mission → tick should flip IN_FLIGHT → COMPLETED.
    state.missions[mission_id] = state.missions[mission_id].model_copy(
        update={"phase": MissionPhase.DONE}
    )
    command_tick(state, datetime.now(UTC))
    assert state.commands[command_id].status == CommandStatus.COMPLETED
    assert state.commands[command_id].completed_at is not None


@pytest.mark.asyncio
async def test_command_lifecycle_timeout_marks_timed_out() -> None:
    state = SwarmState.vineyard()
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=80.0,
        geo=VINEYARD_CENTER,
    )

    result = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.RETURN,
            target="unit:sim-1",
            operator_id="op-davide",
        ),
    )
    command_id = result.command_id
    # Move to IN_FLIGHT artificially with a stale in_flight_at so the next
    # tick should mark it timed_out.
    long_ago = datetime.now(UTC) - timedelta(seconds=200)
    state.commands[command_id] = state.commands[command_id].model_copy(
        update={"status": CommandStatus.IN_FLIGHT, "in_flight_at": long_ago}
    )
    command_tick(state, datetime.now(UTC))
    assert state.commands[command_id].status == CommandStatus.TIMED_OUT


@pytest.mark.asyncio
async def test_hold_patrol_command_completes_immediately() -> None:
    state = SwarmState.vineyard()
    result = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.HOLD_PATROL,
            target="session:current",
            operator_id="op-davide",
        ),
    )
    command = state.commands[result.command_id]
    assert command.status == CommandStatus.COMPLETED
    assert state.hold_patrol is True


@pytest.mark.asyncio
async def test_apply_command_via_coordinator_emits_frames_and_events() -> None:
    state = SwarmState.vineyard()
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=80.0,
        geo=VINEYARD_CENTER,
    )
    coordinator = SwarmCoordinator(state)

    result, frames = await coordinator.apply_command(
        OperatorCommand(
            action=OperatorAction.HOLD_PATROL,
            target="session:current",
            operator_id="op-davide",
        )
    )
    assert result.status == CommandStatus.COMPLETED
    kinds = {frame["kind"] for frame in frames}
    assert "operator" in kinds
    assert "event" in kinds
    operator_events = [
        frame
        for frame in frames
        if frame["kind"] == "event" and frame["data"]["kind"] == "operator"
    ]
    assert operator_events  # at least one lifecycle event emitted


# ── Event detector coverage ──────────────────────────────────────────────────


def test_event_detector_emits_anomaly_state_transitions() -> None:
    state = SwarmState.vineyard()
    state.anomalies["a-1"] = _anomaly(state, "a-1", AnomalyState.PENDING)
    detector = EventDetector()

    first = detector.update(state)
    assert any(
        e.kind.value == "anomaly" and e.anomaly_id == "a-1" for e in first
    )

    state.anomalies["a-1"] = state.anomalies["a-1"].model_copy(
        update={"state": AnomalyState.VERIFYING}
    )
    second = detector.update(state)
    assert any("verifying" in e.body for e in second if e.kind.value == "anomaly")

    state.anomalies["a-1"] = state.anomalies["a-1"].model_copy(
        update={"state": AnomalyState.VERIFIED}
    )
    third = detector.update(state)
    assert any("verified" in e.body for e in third if e.kind.value == "anomaly")

    state.anomalies["a-1"] = state.anomalies["a-1"].model_copy(
        update={"state": AnomalyState.DISMISSED}
    )
    fourth = detector.update(state)
    assert any("dismissed" in e.body for e in fourth if e.kind.value == "anomaly")

    state.anomalies["a-2"] = _anomaly(state, "a-2", AnomalyState.ESCALATED)
    fifth = detector.update(state)
    assert any("escalated" in e.body for e in fifth if e.kind.value == "anomaly")


def test_event_detector_emits_patrol_and_mission_failed() -> None:
    state = SwarmState.vineyard()
    state.missions["m-1"] = MissionView(
        id="m-1",
        kind="PATROL",
        sector_id="center-b",
        phase=MissionPhase.PENDING,
    )
    detector = EventDetector()
    detector.update(state)

    state.missions["m-1"] = state.missions["m-1"].model_copy(
        update={"phase": MissionPhase.EN_ROUTE}
    )
    events = detector.update(state)
    assert any(e.kind.value == "patrol" and "started" in e.body for e in events)

    state.missions["m-1"] = state.missions["m-1"].model_copy(
        update={"phase": MissionPhase.DONE}
    )
    events = detector.update(state)
    assert any(e.kind.value == "patrol" and "completed" in e.body for e in events)

    state.missions["m-2"] = MissionView(
        id="m-2",
        kind="VERIFY",
        sector_id="center-b",
        phase=MissionPhase.PENDING,
    )
    detector.update(state)
    state.missions["m-2"] = state.missions["m-2"].model_copy(
        update={"phase": MissionPhase.FAILED}
    )
    events = detector.update(state)
    assert any(e.kind.value == "mission" and "failed" in e.body for e in events)


def test_event_detector_emits_sector_visited_battery_link_dock_weather() -> None:
    state = SwarmState.vineyard()
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"last_visited_by": "sim-1"}
    )
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=15.0,  # low
        geo=VINEYARD_CENTER,
        link_quality=0.20,  # degraded
    )
    state.docks[DEFAULT_DOCK_ID] = state.docks[DEFAULT_DOCK_ID].model_copy(
        update={"weather_lock": True}
    )

    detector = EventDetector()
    events = detector.update(state)
    kinds = {(e.kind.value, e.body.split(" ")[0]) for e in events}

    assert any(e.kind.value == "sector" and "visited" in e.body for e in events)
    assert any(e.kind.value == "system" and "battery" in e.body for e in events)
    assert any(e.kind.value == "link" and "degraded" in e.body for e in events)
    assert any(e.kind.value == "dock" and "weather" in e.body for e in events)
    assert kinds


def test_event_detector_emits_operator_command_lifecycle() -> None:
    state = SwarmState.vineyard()
    detector = EventDetector()

    command = OperatorCommand(
        action=OperatorAction.VERIFY,
        target="sector:north-a",
        operator_id="op-davide",
        status=CommandStatus.ACCEPTED,
    )
    state.commands[command.id] = command
    accepted_events = detector.update(state)
    assert any(
        e.kind.value == "operator" and "accepted" in e.body for e in accepted_events
    )

    state.commands[command.id] = command.model_copy(
        update={"status": CommandStatus.COMPLETED}
    )
    completed_events = detector.update(state)
    assert any(
        e.kind.value == "operator" and "completed" in e.body for e in completed_events
    )

    rejected = OperatorCommand(
        action=OperatorAction.RETURN,
        target="unit:missing",
        operator_id="op-davide",
        status=CommandStatus.REJECTED,
    )
    state.commands[rejected.id] = rejected
    rejected_events = detector.update(state)
    assert any(
        e.kind.value == "operator" and "rejected" in e.body for e in rejected_events
    )


# ── Voice / forbidden words ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_phase3_event_bodies_contain_no_forbidden_words() -> None:
    from swarm_core.voice import has_forbidden

    state = SwarmState.vineyard()
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=15.0,
        geo=VINEYARD_CENTER,
        link_quality=0.20,
    )
    state.docks[DEFAULT_DOCK_ID] = state.docks[DEFAULT_DOCK_ID].model_copy(
        update={"weather_lock": True, "power_status": PowerStatus.ONLINE, "status": DockStatus.ONLINE}
    )

    coordinator = SwarmCoordinator(state)
    await coordinator.apply_telemetry(
        Telemetry(
            agent_id="sim-1", geo=VINEYARD_CENTER, battery_pct=15.0, link_quality=0.20
        )
    )
    await coordinator.apply_anomaly(
        Anomaly(
            kind=AnomalyKind.INTRUSION,
            geo=VINEYARD_CENTER,
            confidence=0.92,
            source_agent="sim-1",
        )
    )
    await coordinator.apply_mission_progress(
        MissionProgress(mission_id="m-1", phase="DONE", progress_pct=100.0)
    )
    for event in state.events:
        assert has_forbidden(event.body) is None, event.body


# ── Helpers ─────────────────────────────────────────────────────────────────


def _anomaly(
    state: SwarmState, anomaly_id: str, anomaly_state: AnomalyState
) -> AnomalyView:
    return AnomalyView(
        id=anomaly_id,
        kind=AnomalyKind.SMOKE,
        geo=Geo(lat=44.7, lon=8.03),
        sector_id="center-b",
        confidence=0.7,
        band=ConfidenceBand.ELEVATED,
        state=anomaly_state,
        detected_by="sim-1",
    )
