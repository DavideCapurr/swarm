"""Tests for the Phase 6.A PolicyEngine."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from swarm_core.messages import (
    AgentState,
    DockState,
    DockStatus,
    Geo,
    MissionPhase,
    MissionView,
    PowerStatus,
    RejectedReason,
    UnitState,
)

from swarm_os.policy import PolicyEngine
from swarm_os.safety import (
    LocalStubWeatherProvider,
    SafetyActionKind,
    WeatherProvider,
    WeatherSnapshot,
)
from swarm_os.sites import SiteConfig, load_site_config

# ── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def site_config() -> SiteConfig:
    """Built-in vineyard-01 config (no YAML on disk needed)."""
    return load_site_config()


@pytest.fixture()
def engine(site_config: SiteConfig) -> PolicyEngine:
    return PolicyEngine(site_config, LocalStubWeatherProvider())


def _airborne_unit(
    *,
    agent_id: str = "unit-001",
    battery_pct: float = 85.0,
    link_quality: float = 0.9,
    geo: Geo | None = None,
) -> UnitState:
    return UnitState(
        agent_id=agent_id,
        vendor="simulator",
        model="sim",
        fsm_state=AgentState.EN_ROUTE,
        battery_pct=battery_pct,
        geo=geo or Geo(lat=44.7000, lon=8.0300, alt_m=20.0),
        link_quality=link_quality,
        dock_id=None,
    )


def _docks(*, weather_lock: bool = False) -> dict[str, DockState]:
    return {
        "dock-langhe-01": DockState(
            dock_id="dock-langhe-01",
            status=DockStatus.ONLINE,
            power_status=PowerStatus.ONLINE,
            primary=True,
            weather_lock=weather_lock,
        )
    }


def _mission(
    *,
    kind: str = "PATROL",
    waypoints: list[Geo] | None = None,
    assigned_agent: str | None = None,
) -> MissionView:
    return MissionView(
        id="m-001",
        kind=kind,
        assigned_agent=assigned_agent,
        phase=MissionPhase.PENDING,
        waypoints=waypoints or [Geo(lat=44.7000, lon=8.0300, alt_m=30.0)],
    )


# ── validate_mission ────────────────────────────────────────────────────────


def test_validate_mission_allows_waypoints_inside_geofence(engine: PolicyEngine) -> None:
    decision = engine.validate_mission(_mission(), units={}, docks=_docks())
    assert decision.allowed is True
    assert decision.reason is None


def test_validate_mission_rejects_waypoint_outside_geofence(engine: PolicyEngine) -> None:
    far_away = [Geo(lat=44.9999, lon=8.9999, alt_m=30.0)]
    decision = engine.validate_mission(
        _mission(waypoints=far_away), units={}, docks=_docks()
    )
    assert decision.allowed is False
    assert decision.reason is RejectedReason.OUTSIDE_GEOFENCE


def test_validate_mission_rejects_altitude_above_ceiling(engine: PolicyEngine) -> None:
    above = [Geo(lat=44.7000, lon=8.0300, alt_m=200.0)]
    decision = engine.validate_mission(
        _mission(waypoints=above), units={}, docks=_docks()
    )
    assert decision.allowed is False
    assert decision.reason is RejectedReason.OUTSIDE_GEOFENCE


def test_validate_mission_rejects_low_battery_for_kind(engine: PolicyEngine) -> None:
    unit = _airborne_unit(battery_pct=25.0)
    mission = _mission(kind="VERIFY", assigned_agent=unit.agent_id)
    decision = engine.validate_mission(
        mission, units={unit.agent_id: unit}, docks=_docks()
    )
    assert decision.allowed is False
    assert decision.reason is RejectedReason.BATTERY_TOO_LOW
    assert "VERIFY" in decision.detail


def test_validate_mission_allows_low_battery_above_kind_threshold(engine: PolicyEngine) -> None:
    """VERIFY needs 40%; PATROL only 30%. A 35%-battery unit can still PATROL."""

    unit = _airborne_unit(battery_pct=35.0)
    mission = _mission(kind="PATROL", assigned_agent=unit.agent_id)
    decision = engine.validate_mission(
        mission, units={unit.agent_id: unit}, docks=_docks()
    )
    assert decision.allowed is True


def test_validate_mission_rejects_low_link(engine: PolicyEngine) -> None:
    unit = _airborne_unit(link_quality=0.2)
    mission = _mission(assigned_agent=unit.agent_id)
    decision = engine.validate_mission(
        mission, units={unit.agent_id: unit}, docks=_docks()
    )
    assert decision.allowed is False
    assert decision.reason is RejectedReason.LINK_TOO_WEAK


def test_validate_mission_blocks_movement_when_dock_weather_locked(engine: PolicyEngine) -> None:
    decision = engine.validate_mission(
        _mission(kind="PATROL"), units={}, docks=_docks(weather_lock=True)
    )
    assert decision.allowed is False
    assert decision.reason is RejectedReason.WEATHER_LOCK


def test_validate_mission_allows_rtl_when_dock_weather_locked(engine: PolicyEngine) -> None:
    """RTL_DOCK is the safety action itself — never blocked by weather."""

    decision = engine.validate_mission(
        _mission(kind="RTL_DOCK"), units={}, docks=_docks(weather_lock=True)
    )
    assert decision.allowed is True


# ── safety actions ─────────────────────────────────────────────────────────


def test_evaluate_safety_actions_emits_auto_rtl_below_battery_floor(engine: PolicyEngine) -> None:
    unit = _airborne_unit(battery_pct=15.0)
    actions = engine.evaluate_safety_actions({unit.agent_id: unit})
    assert len(actions) == 1
    assert actions[0].kind is SafetyActionKind.AUTO_RTL
    assert actions[0].reason is RejectedReason.BATTERY_TOO_LOW


def test_evaluate_safety_actions_emits_auto_rtl_below_link_floor(engine: PolicyEngine) -> None:
    unit = _airborne_unit(link_quality=0.1)
    actions = engine.evaluate_safety_actions({unit.agent_id: unit})
    assert len(actions) == 1
    assert actions[0].kind is SafetyActionKind.AUTO_RTL
    assert actions[0].reason is RejectedReason.LINK_TOO_WEAK


def test_evaluate_safety_actions_battery_precedes_link(engine: PolicyEngine) -> None:
    """Both bad — battery is the worse condition, so it wins the slot."""

    unit = _airborne_unit(battery_pct=15.0, link_quality=0.1)
    actions = engine.evaluate_safety_actions({unit.agent_id: unit})
    assert len(actions) == 1
    assert actions[0].reason is RejectedReason.BATTERY_TOO_LOW


def test_evaluate_safety_actions_skips_docked_units(engine: PolicyEngine) -> None:
    docked = _airborne_unit(battery_pct=5.0).model_copy(
        update={"fsm_state": AgentState.DOCKED, "dock_id": "dock-langhe-01"}
    )
    actions = engine.evaluate_safety_actions({docked.agent_id: docked})
    assert actions == []


def test_evaluate_safety_actions_uses_fsm_not_dock_id(engine: PolicyEngine) -> None:
    """The telemetry projection stamps a home dock on every unit, so a
    populated dock_id must not exempt an airborne unit from auto-RTL."""

    flying = _airborne_unit(battery_pct=5.0).model_copy(
        update={"dock_id": "dock-langhe-01"}
    )
    actions = engine.evaluate_safety_actions({flying.agent_id: flying})
    assert len(actions) == 1
    assert actions[0].reason is RejectedReason.BATTERY_TOO_LOW


def test_evaluate_safety_actions_skips_healthy_unit(engine: PolicyEngine) -> None:
    actions = engine.evaluate_safety_actions({"u": _airborne_unit()})
    assert actions == []


# ── weather ────────────────────────────────────────────────────────────────


async def test_current_weather_uses_provider(engine: PolicyEngine) -> None:
    snap = await engine.current_weather()
    assert snap is not None
    assert snap.source == "stub"


def test_is_weather_locked_returns_true_when_none(engine: PolicyEngine) -> None:
    assert engine.is_weather_locked(None) is True


def test_is_weather_locked_respects_each_threshold(engine: PolicyEngine, site_config: SiteConfig) -> None:
    thr = site_config.thresholds.weather
    benign = WeatherSnapshot(
        wind_mps=thr.max_wind_mps - 1,
        visibility_km=thr.min_visibility_km + 1,
        temp_c=15.0,
        source="stub",
    )
    assert engine.is_weather_locked(benign) is False
    too_windy = WeatherSnapshot(
        wind_mps=thr.max_wind_mps + 1,
        visibility_km=10.0,
        temp_c=15.0,
        source="stub",
    )
    assert engine.is_weather_locked(too_windy) is True
    too_dark = WeatherSnapshot(
        wind_mps=2.0,
        visibility_km=thr.min_visibility_km - 0.1,
        temp_c=15.0,
        source="stub",
    )
    assert engine.is_weather_locked(too_dark) is True
    too_cold = WeatherSnapshot(
        wind_mps=2.0,
        visibility_km=10.0,
        temp_c=thr.temp_c_min - 0.1,
        source="stub",
    )
    assert engine.is_weather_locked(too_cold) is True


class _FailingWeatherProvider:
    """Deliberately raises to exercise the fail-closed code path."""

    async def current(self, site_id: str) -> WeatherSnapshot:
        raise RuntimeError("upstream OpenWeather 503")


async def test_current_weather_returns_none_when_provider_raises(site_config: SiteConfig) -> None:
    engine = PolicyEngine(site_config, _FailingWeatherProvider())
    assert isinstance(_FailingWeatherProvider(), WeatherProvider)
    snap = await engine.current_weather()
    assert snap is None
    # And the next call doesn't poison the cache with None — it re-tries.
    snap2 = await engine.current_weather()
    assert snap2 is None


async def test_current_weather_caches_within_refresh_interval(site_config: SiteConfig) -> None:
    """A successful fetch is reused until the refresh interval elapses."""

    calls: list[str] = []

    class _CountingProvider:
        async def current(self, site_id: str) -> WeatherSnapshot:
            calls.append(site_id)
            return WeatherSnapshot(
                wind_mps=2.0, visibility_km=10.0, temp_c=15.0, source="counting"
            )

    fake_now = [datetime(2026, 5, 16, 12, 0, 0, tzinfo=UTC)]
    engine = PolicyEngine(
        site_config, _CountingProvider(), clock=lambda: fake_now[0]
    )
    await engine.current_weather()
    await engine.current_weather()
    assert len(calls) == 1  # second call hit the cache


# ── refresh_dock_weather_locks ─────────────────────────────────────────────


async def test_refresh_dock_weather_locks_emits_lock_when_provider_fails(
    site_config: SiteConfig,
) -> None:
    engine = PolicyEngine(site_config, _FailingWeatherProvider())
    docks = _docks(weather_lock=False)
    updated = await engine.refresh_dock_weather_locks(docks)
    assert "dock-langhe-01" in updated
    assert updated["dock-langhe-01"].weather_lock is True


async def test_refresh_dock_weather_locks_no_op_when_already_correct(
    engine: PolicyEngine,
) -> None:
    """Stub provider returns benign; an already-unlocked dock should not
    be re-emitted (sticky frame, less WS noise)."""

    docks = {
        "dock-langhe-01": DockState(
            dock_id="dock-langhe-01",
            status=DockStatus.ONLINE,
            power_status=PowerStatus.ONLINE,
            primary=True,
            weather_lock=False,
            wind_mps=3.0,
            visibility_km=10.0,
            temp_c=18.0,
        )
    }
    # Prime the engine cache so the comparison matches snapshot fields.
    await engine.current_weather()
    updated = await engine.refresh_dock_weather_locks(docks)
    assert updated == {}


# ── priority resolution ────────────────────────────────────────────────────


def test_resolve_priorities_sorts_desc_stable() -> None:
    a = MissionView(id="a", kind="PATROL", priority=10)
    b = MissionView(id="b", kind="VERIFY", priority=50)
    c = MissionView(id="c", kind="RTL_DOCK", priority=100)
    d = MissionView(id="d", kind="PATROL", priority=10)
    ordered = PolicyEngine.resolve_priorities([a, b, c, d])
    assert [m.id for m in ordered] == ["c", "b", "a", "d"]
