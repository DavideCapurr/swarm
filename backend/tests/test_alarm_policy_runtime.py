from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from adapters.base import AdapterRegistry
from backend.app.fleet import FleetManager, fleet_from_env
from orchestrator.swarm_orchestrator.bus import InMemoryBus
from orchestrator.swarm_orchestrator.bus_fleet import BusFleetOrchestrator
from orchestrator.swarm_orchestrator.policy_bus import (
    AlarmPolicyBusFleetOrchestrator,
    AlarmPolicyPresenceResponseBusFleetOrchestrator,
)
from orchestrator.swarm_orchestrator.presence_bus import (
    PresenceResponseBusFleetOrchestrator,
)


@pytest.fixture
async def bus() -> AsyncIterator[InMemoryBus]:
    value = InMemoryBus()
    await value.connect()
    yield value
    await value.close()


def test_runtime_selection_preserves_legacy_default(bus: InMemoryBus) -> None:
    legacy = FleetManager(bus=bus, registry=AdapterRegistry(), vendors=("mavlink",))
    assert type(legacy._build_mission_orchestrator()) is BusFleetOrchestrator

    legacy_presence = FleetManager(
        bus=bus,
        registry=AdapterRegistry(),
        vendors=("mavlink",),
        presence_response_enabled=True,
    )
    assert (
        type(legacy_presence._build_mission_orchestrator())
        is PresenceResponseBusFleetOrchestrator
    )


def test_runtime_selection_uses_alarm_policy_only_when_enabled(
    bus: InMemoryBus,
) -> None:
    policy = FleetManager(
        bus=bus,
        registry=AdapterRegistry(),
        vendors=("mavlink",),
        alarm_response_policy_enabled=True,
    )
    assert type(policy._build_mission_orchestrator()) is AlarmPolicyBusFleetOrchestrator

    policy_presence = FleetManager(
        bus=bus,
        registry=AdapterRegistry(),
        vendors=("mavlink",),
        alarm_response_policy_enabled=True,
        presence_response_enabled=True,
    )
    assert (
        type(policy_presence._build_mission_orchestrator())
        is AlarmPolicyPresenceResponseBusFleetOrchestrator
    )


def test_fleet_from_env_builds_alarm_policy_without_event_decisions(
    bus: InMemoryBus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_ALARM_RESPONSE_POLICY", "1")
    monkeypatch.setenv("SWARM_ALARM_COOPERATIVE_THRESHOLD", "0.81")
    monkeypatch.setenv("SWARM_ALARM_HIGH_CONFIDENCE_THRESHOLD", "0.95")
    monkeypatch.setenv("SWARM_ALARM_MAX_TEAM_SIZE", "5")
    monkeypatch.setenv("SWARM_ALARM_SINGLE_HOVER_S", "11")
    monkeypatch.setenv("SWARM_ALARM_COOPERATIVE_HOVER_S", "17")

    fleet = fleet_from_env(bus)

    assert fleet.alarm_response_policy_enabled is True
    assert fleet.alarm_policy.cooperative_threshold == 0.81
    assert fleet.alarm_policy.high_confidence_threshold == 0.95
    assert fleet.alarm_policy.max_team_size == 5
    assert fleet.alarm_policy.single_hover_s == 11.0
    assert fleet.alarm_policy.cooperative_hover_s == 17.0


def test_alarm_policy_is_opt_in_by_default(
    bus: InMemoryBus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "SWARM_ALARM_RESPONSE_POLICY",
        "SWARM_ALARM_COOPERATIVE_THRESHOLD",
        "SWARM_ALARM_HIGH_CONFIDENCE_THRESHOLD",
        "SWARM_ALARM_MAX_TEAM_SIZE",
        "SWARM_ALARM_SINGLE_HOVER_S",
        "SWARM_ALARM_COOPERATIVE_HOVER_S",
    ):
        monkeypatch.delenv(name, raising=False)

    fleet = fleet_from_env(bus)

    assert fleet.alarm_response_policy_enabled is False
    assert fleet.alarm_policy.cooperative_threshold == 0.80
    assert fleet.alarm_policy.high_confidence_threshold == 0.93
    assert fleet.alarm_policy.max_team_size == 3


def test_alarm_policy_rejects_inverted_thresholds(
    bus: InMemoryBus,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SWARM_ALARM_COOPERATIVE_THRESHOLD", "0.90")
    monkeypatch.setenv("SWARM_ALARM_HIGH_CONFIDENCE_THRESHOLD", "0.80")

    with pytest.raises(ValueError, match="HIGH_CONFIDENCE_THRESHOLD"):
        fleet_from_env(bus)
