"""Phase 6.A integration tests — PolicyEngine wired through SwarmState.

These tests exercise the real `SwarmState.vineyard()` factory (which
includes the default `PolicyEngine` + `LocalStubWeatherProvider`) so
they catch any wiring regression in scheduler, command bus, or
coordinator.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from swarm_core.messages import (
    AgentState,
    AnomalyKind,
    AnomalyView,
    CommandStatus,
    ConfidenceBand,
    Geo,
    MissionView,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
    Sector,
    SectorState,
    UnitState,
)

from swarm_os.command_bus import submit
from swarm_os.coordinator import AUTO_RTL_PREFIX, AUTO_RTL_PRIORITY, SwarmCoordinator
from swarm_os.policy import PolicyEngine
from swarm_os.safety import LocalStubWeatherProvider, SafetyActionKind, WeatherSnapshot
from swarm_os.scheduler import AUTO_PATROL_PRIORITY, _schedule_repatrols
from swarm_os.sites import load_site_config
from swarm_os.state import VINEYARD_CENTER, SwarmState

OUTSIDE_GEOFENCE = Geo(lat=45.0000, lon=9.0000, alt_m=20.0)


def _vineyard_with_low_battery_airborne_unit() -> SwarmState:
    state = SwarmState.vineyard()
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=15.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
        dock_id=None,
    )
    return state


# ── scheduler integration ───────────────────────────────────────────────────


def test_scheduler_skips_auto_patrol_when_sector_centroid_outside_geofence() -> None:
    """A planted sector outside the site polygon must not produce auto-PATROL."""

    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    rogue = Sector(
        id="rogue-1",
        label="rogue",
        polygon=[
            Geo(lat=44.9990, lon=8.9990),
            Geo(lat=44.9990, lon=9.0010),
            Geo(lat=45.0010, lon=9.0010),
        ],
        centroid=OUTSIDE_GEOFENCE,
        confidence=0.0,
        state=SectorState.BLIND,
    )
    state.sectors[rogue.id] = rogue
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.DOCKED,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
    )

    created = _schedule_repatrols(state, now)
    assert all(m.sector_id != rogue.id for m in created)


def test_scheduler_auto_patrol_carries_priority() -> None:
    """Auto-PATROL stamped by the scheduler must carry the documented tier."""

    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"confidence": 0.0, "state": SectorState.BLIND}
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
    assert created and all(m.priority == AUTO_PATROL_PRIORITY for m in created)


# ── command bus integration ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_verify_rejected_when_dock_weather_locked() -> None:
    """Operator VERIFY on a sector must fail when the primary dock is locked."""

    state = SwarmState.vineyard()
    state.docks["dock-langhe-01"] = state.docks["dock-langhe-01"].model_copy(
        update={"weather_lock": True}
    )
    state.verifier_id = "sim-1"
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
    )
    sector = next(iter(state.sectors))
    cmd = OperatorCommand(
        operator_id="op-test",
        action=OperatorAction.VERIFY,
        target=f"sector:{sector}",
    )
    result = await submit(state, cmd)
    assert result.status is CommandStatus.REJECTED
    assert result.rejected_reason is RejectedReason.WEATHER_LOCK


@pytest.mark.asyncio
async def test_submit_return_allowed_even_when_weather_locked() -> None:
    """RTL is the safety path and must never be blocked by weather."""

    state = SwarmState.vineyard()
    state.docks["dock-langhe-01"] = state.docks["dock-langhe-01"].model_copy(
        update={"weather_lock": True}
    )
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
    )
    cmd = OperatorCommand(
        operator_id="op-test",
        action=OperatorAction.RETURN,
        target="unit:sim-1",
    )
    result = await submit(state, cmd)
    assert result.status is CommandStatus.ACCEPTED
    assert result.rejected_reason is None


@pytest.mark.asyncio
async def test_submit_verify_rejected_when_assigned_unit_battery_below_threshold() -> None:
    """The would-be verifier has 30%; VERIFY needs 40%."""

    state = SwarmState.vineyard()
    state.verifier_id = "sim-1"
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=30.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
    )
    sector = next(iter(state.sectors))
    cmd = OperatorCommand(
        operator_id="op-test",
        action=OperatorAction.VERIFY,
        target=f"sector:{sector}",
    )
    result = await submit(state, cmd)
    assert result.status is CommandStatus.REJECTED
    assert result.rejected_reason is RejectedReason.BATTERY_TOO_LOW


# ── coordinator integration ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_coordinator_emits_auto_rtl_for_low_battery_unit() -> None:
    state = _vineyard_with_low_battery_airborne_unit()
    coord = SwarmCoordinator(state)
    await coord._refresh_async(datetime.now(UTC))

    mission_id = f"{AUTO_RTL_PREFIX}sim-1"
    assert mission_id in state.missions
    mission = state.missions[mission_id]
    assert mission.kind == "RTL_DOCK"
    assert mission.priority == AUTO_RTL_PRIORITY
    assert mission.assigned_agent == "sim-1"
    assert len(state.safety_actions) == 1
    action = state.safety_actions[-1]
    assert action.kind is SafetyActionKind.AUTO_RTL
    assert action.reason is RejectedReason.BATTERY_TOO_LOW


@pytest.mark.asyncio
async def test_coordinator_does_not_duplicate_auto_rtl_per_unit() -> None:
    """Two consecutive refreshes must not create two RTL missions for the
    same agent — they're de-duped by mission id."""

    state = _vineyard_with_low_battery_airborne_unit()
    coord = SwarmCoordinator(state)
    await coord._refresh_async(datetime.now(UTC))
    await coord._refresh_async(datetime.now(UTC))
    assert sum(1 for m in state.missions.values() if m.kind == "RTL_DOCK") == 1


@pytest.mark.asyncio
async def test_coordinator_flips_dock_weather_lock_when_provider_says_unsafe() -> None:
    """A provider returning unsafe wind must result in the dock being
    weather-locked at the next refresh cycle."""

    class _WindyProvider:
        async def current(self, site_id: str) -> WeatherSnapshot:
            return WeatherSnapshot(
                wind_mps=20.0,
                visibility_km=10.0,
                temp_c=15.0,
                source="windy-stub",
            )

    state = SwarmState.vineyard()
    state.policy = PolicyEngine(load_site_config(), _WindyProvider())
    coord = SwarmCoordinator(state)
    await coord._refresh_async(datetime.now(UTC))
    dock = state.docks["dock-langhe-01"]
    assert dock.weather_lock is True
    assert dock.wind_mps == 20.0


@pytest.mark.asyncio
async def test_coordinator_clears_dock_weather_lock_when_conditions_return_safe() -> None:
    state = SwarmState.vineyard()
    state.docks["dock-langhe-01"] = state.docks["dock-langhe-01"].model_copy(
        update={"weather_lock": True}
    )
    # Default policy uses the benign LocalStubWeatherProvider — the next
    # refresh must clear the lock.
    state.policy = PolicyEngine(load_site_config(), LocalStubWeatherProvider())
    coord = SwarmCoordinator(state)
    await coord._refresh_async(datetime.now(UTC))
    assert state.docks["dock-langhe-01"].weather_lock is False


# ── end-to-end: operator VERIFY through full coordinator path ──────────────


@pytest.mark.asyncio
async def test_apply_command_rejects_verify_outside_geofence_sector() -> None:
    """Plant an outside-the-fence sector and assert apply_command rejects."""

    state = SwarmState.vineyard()
    rogue = Sector(
        id="rogue-1",
        label="rogue",
        polygon=[
            Geo(lat=44.9990, lon=8.9990),
            Geo(lat=44.9990, lon=9.0010),
            Geo(lat=45.0010, lon=9.0010),
        ],
        centroid=OUTSIDE_GEOFENCE,
        confidence=0.0,
        state=SectorState.BLIND,
    )
    state.sectors[rogue.id] = rogue
    state.verifier_id = "sim-1"
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
    )
    coord = SwarmCoordinator(state)
    cmd = OperatorCommand(
        operator_id="op-test",
        action=OperatorAction.VERIFY,
        target=f"sector:{rogue.id}",
    )
    result, frames = await coord.apply_command(cmd)
    assert result.status is CommandStatus.REJECTED
    assert result.rejected_reason is RejectedReason.OUTSIDE_GEOFENCE
    # And the command audit frame is in the broadcast.
    operator_frames = [f for f in frames if f["kind"] == "operator"]
    assert operator_frames, "expected operator frame in apply_command result"
    assert operator_frames[0]["data"]["status"] == CommandStatus.REJECTED.value


async def test_apply_command_rejects_verify_outside_geofence_anomaly() -> None:
    """Anomaly targets must carry their geo into the policy gate.

    Without it the tentative VERIFY mission has no waypoints and the
    geofence check never fires for anomaly targets."""

    state = SwarmState.vineyard()
    state.anomalies["a-rogue"] = AnomalyView(
        id="a-rogue",
        kind=AnomalyKind.SMOKE,
        geo=OUTSIDE_GEOFENCE,
        confidence=0.7,
        band=ConfidenceBand.ELEVATED,
    )
    state.verifier_id = "sim-1"
    state.units["sim-1"] = UnitState(
        agent_id="sim-1",
        vendor="simulated",
        model="sim-x500",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=90.0,
        geo=VINEYARD_CENTER,
        link_quality=0.9,
    )
    cmd = OperatorCommand(
        operator_id="op-test",
        action=OperatorAction.VERIFY,
        target="anomaly:a-rogue",
    )
    result = await submit(state, cmd)
    assert result.status is CommandStatus.REJECTED
    assert result.rejected_reason is RejectedReason.OUTSIDE_GEOFENCE


# ── do-no-harm: existing scheduler test still passes through the new path ──


def test_scheduler_still_creates_patrol_for_in_polygon_sector() -> None:
    """Sanity: the policy gate must not break the common case."""

    state = SwarmState.vineyard()
    now = datetime.now(UTC)
    state.sectors["center-b"] = state.sectors["center-b"].model_copy(
        update={"confidence": 0.0, "state": SectorState.BLIND}
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
    assert any(m.sector_id == "center-b" for m in created)
    assert all(isinstance(m, MissionView) for m in created)
