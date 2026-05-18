"""Phase 6.G — kernel-side EMERGENCY_RTL_ALL tests.

These tests exercise the command-bus + coordinator path; the
backend HTTP layer is covered separately in
``backend/tests/test_emergency_rtl.py``.

The contract we verify here:

  * Submit with the canonical fleet target is accepted.
  * Submit with any other target is REJECTED with INVALID_TARGET_KIND
    — the audit log must never carry attacker-chosen target strings.
  * An RTL_DOCK mission is queued for every airborne unit, with
    priority above auto-RTL.
  * Already-docked, OFFLINE, and ERROR units do not get a mission
    queued.
  * Non-emergency in-flight missions on those units are force-failed
    so the new RTL is the only thing bidding for the unit.
  * The safety-policy gate is bypassed (a unit below the battery
    floor still gets an emergency RTL).
  * ``state.hold_patrol`` is forced True and the scheduler stops
    spawning new patrols.
  * ``state.emergency_active_at`` records the trigger timestamp.
  * Idempotency: a second submit on the same boot does not duplicate
    missions that are still in flight.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from swarm_core.messages import (
    AgentState,
    CommandStatus,
    Geo,
    MissionPhase,
    MissionView,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
    SectorState,
    UnitState,
)

from swarm_os.command_bus import (
    EMERGENCY_FLEET_TARGET,
    EMERGENCY_MISSION_PREFIX,
    EMERGENCY_RTL_PRIORITY,
    submit,
)
from swarm_os.coordinator import AUTO_RTL_PREFIX, SwarmCoordinator
from swarm_os.scheduler import _schedule_repatrols
from swarm_os.state import VINEYARD_CENTER, SwarmState


def _seed_units(state: SwarmState) -> None:
    """Three units: one en-route, one docked, one offline."""

    state.units["sim-air-1"] = UnitState(
        agent_id="sim-air-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=80.0,
        geo=VINEYARD_CENTER,
    )
    state.units["sim-air-2"] = UnitState(
        agent_id="sim-air-2",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.ON_STATION,
        battery_pct=15.0,  # below safety floor — we still want an RTL
        geo=VINEYARD_CENTER,
    )
    state.units["sim-docked"] = UnitState(
        agent_id="sim-docked",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=100.0,
        geo=VINEYARD_CENTER,
    )
    state.units["sim-offline"] = UnitState(
        agent_id="sim-offline",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.OFFLINE,
        battery_pct=42.0,
        geo=VINEYARD_CENTER,
    )


@pytest.mark.asyncio
async def test_emergency_rtl_all_queues_one_mission_per_airborne_unit() -> None:
    state = SwarmState.vineyard()
    _seed_units(state)
    result = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    # The operator command itself completes immediately — N spawned
    # missions are visible separately in state.missions.
    assert state.commands[result.command_id].status == CommandStatus.COMPLETED
    emergency_missions = {
        m.assigned_agent: m
        for m in state.missions.values()
        if m.id.startswith(EMERGENCY_MISSION_PREFIX)
    }
    assert set(emergency_missions) == {"sim-air-1", "sim-air-2"}
    for m in emergency_missions.values():
        assert m.kind == "RTL_DOCK"
        assert m.priority == EMERGENCY_RTL_PRIORITY
        assert m.phase == MissionPhase.PENDING


@pytest.mark.asyncio
async def test_emergency_rtl_all_rejects_non_fleet_target() -> None:
    """The audit log must never carry attacker-chosen target strings."""

    state = SwarmState.vineyard()
    _seed_units(state)
    result = await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target="sector:center-a",  # not the canonical target
            operator_id="op-commander01",
        ),
    )
    stored = state.commands[result.command_id]
    assert stored.status == CommandStatus.REJECTED
    assert stored.rejected_reason == RejectedReason.INVALID_TARGET_KIND
    # No missions were spawned.
    assert not any(
        m.id.startswith(EMERGENCY_MISSION_PREFIX) for m in state.missions.values()
    )


@pytest.mark.asyncio
async def test_emergency_rtl_all_bypasses_safety_policy_gate() -> None:
    """A unit below the battery floor must still get an emergency RTL.

    Without the bypass the policy engine would reject the would-be
    mission for BATTERY_TOO_LOW — exactly the case where we *need* the
    RTL to dispatch.
    """

    state = SwarmState.vineyard()
    _seed_units(state)
    # sim-air-2 has battery_pct=15.0, which is below the policy floor.
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    spawned = [
        m for m in state.missions.values() if m.id.startswith(EMERGENCY_MISSION_PREFIX)
    ]
    assert any(m.assigned_agent == "sim-air-2" for m in spawned)


@pytest.mark.asyncio
async def test_emergency_rtl_all_forces_hold_patrol_and_records_timestamp() -> None:
    state = SwarmState.vineyard()
    _seed_units(state)
    assert state.hold_patrol is False
    assert state.emergency_active_at is None
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    assert state.hold_patrol is True
    assert state.emergency_active_at is not None


@pytest.mark.asyncio
async def test_emergency_rtl_all_stops_auto_patrol_scheduler() -> None:
    """The scheduler refuses to spawn new patrols once the emergency fires."""

    state = SwarmState.vineyard()
    _seed_units(state)
    # Mark a sector blind so the scheduler *would* normally spawn a patrol.
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"confidence": 0.0, "state": SectorState.BLIND}
    )
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    created = _schedule_repatrols(state, datetime.now(UTC))
    assert created == []


@pytest.mark.asyncio
async def test_emergency_rtl_all_force_fails_conflicting_missions() -> None:
    """Non-RTL in-flight missions on airborne units are cancelled."""

    state = SwarmState.vineyard()
    _seed_units(state)
    state.missions["verify-existing"] = MissionView(
        id="verify-existing",
        kind="VERIFY",
        assigned_agent="sim-air-1",
        sector_id="center-b",
        phase=MissionPhase.EN_ROUTE,
        progress_pct=42.0,
        ts=datetime.now(UTC),
    )
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    assert state.missions["verify-existing"].phase == MissionPhase.FAILED
    # The emergency mission is the only non-terminal mission for that unit.
    em = state.missions[f"{EMERGENCY_MISSION_PREFIX}sim-air-1"]
    assert em.phase == MissionPhase.PENDING


@pytest.mark.asyncio
async def test_emergency_rtl_all_is_idempotent_within_a_boot() -> None:
    """A second submit while the first is still in-flight should not duplicate."""

    state = SwarmState.vineyard()
    _seed_units(state)
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    first_missions = {
        mid: state.missions[mid]
        for mid in state.missions
        if mid.startswith(EMERGENCY_MISSION_PREFIX)
    }
    # Second submit — same operator, same target.
    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    second_missions = {
        mid: state.missions[mid]
        for mid in state.missions
        if mid.startswith(EMERGENCY_MISSION_PREFIX)
    }
    assert set(first_missions) == set(second_missions)
    # The first mission objects are still in place (not replaced).
    for mid in first_missions:
        assert state.missions[mid] is first_missions[mid] or (
            state.missions[mid].ts == first_missions[mid].ts
        )


@pytest.mark.asyncio
async def test_coordinator_suppresses_auto_rtl_when_emergency_active() -> None:
    """Once the emergency RTL is queued, the safety actions path must not
    queue an additional auto-RTL for the same unit. Two RTLs on one
    unit would race for the same slot and double-count the audit
    event."""

    state = SwarmState.vineyard()
    # Use a unit below the battery floor so the policy engine *would*
    # emit a SafetyAction(AUTO_RTL, ...). Place it inside the geofence so
    # the unit is otherwise valid.
    state.units["sim-air-low"] = UnitState(
        agent_id="sim-air-low",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=10.0,  # below the safety floor
        geo=Geo(lat=44.700, lon=8.030, alt_m=20.0),
    )
    coordinator = SwarmCoordinator(state)

    await submit(
        state,
        OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id="op-commander01",
        ),
    )
    # Run a full refresh tick; the safety-actions branch would normally
    # queue an `auto-rtl-sim-air-low` mission for the low-battery unit.
    await coordinator.apply_command(
        OperatorCommand(
            action=OperatorAction.HOLD_PATROL,
            target="session:current",
            operator_id="op-commander01",
        )
    )
    has_emergency = any(
        m.id.startswith(EMERGENCY_MISSION_PREFIX) and m.assigned_agent == "sim-air-low"
        for m in state.missions.values()
    )
    has_auto_rtl = any(
        m.id == f"{AUTO_RTL_PREFIX}sim-air-low" for m in state.missions.values()
    )
    assert has_emergency, "emergency mission expected for low-battery airborne unit"
    assert not has_auto_rtl, "auto-rtl must be suppressed while emergency is active"
