"""Tests for `backend.app.fleet` — SWARM_VENDORS parsing + runner registry."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from adapters.base import AdapterRegistry
from backend.app.fleet import (
    IN_PROCESS_VENDORS,
    SUPPORTED_VENDORS,
    FleetManager,
    UnknownVendor,
    fleet_from_env,
    parse_vendors,
)
from orchestrator.swarm_orchestrator.bus import Bus, InMemoryBus

# ── parse_vendors ─────────────────────────────────────────────────────────────


def test_parse_vendors_default_is_simulator_only() -> None:
    assert parse_vendors(None) == ("simulator",)
    assert parse_vendors("") == ("simulator",)
    assert parse_vendors("   ") == ("simulator",)


def test_parse_vendors_simulator_alone() -> None:
    assert parse_vendors("simulator") == ("simulator",)


def test_parse_vendors_simulator_plus_mavlink() -> None:
    assert parse_vendors("simulator,mavlink") == ("simulator", "mavlink")


def test_parse_vendors_mavlink_alone() -> None:
    assert parse_vendors("mavlink") == ("mavlink",)


def test_parse_vendors_lowercases_and_strips() -> None:
    assert parse_vendors("  SIMULATOR ,  MAVLink ") == ("simulator", "mavlink")


def test_parse_vendors_dedupes() -> None:
    assert parse_vendors("mavlink,mavlink,simulator") == ("mavlink", "simulator")


def test_parse_vendors_ignores_empty_tokens() -> None:
    assert parse_vendors("simulator,,mavlink,") == ("simulator", "mavlink")


def test_parse_vendors_rejects_unknown() -> None:
    with pytest.raises(UnknownVendor):
        parse_vendors("simulator,not-a-vendor")
    with pytest.raises(UnknownVendor):
        parse_vendors("dji")  # stub package exists but isn't supported in Phase 5


def test_supported_vendors_pinned() -> None:
    # Document the closed set so a relaxed allowlist surfaces in review.
    assert frozenset({"simulator", "mavlink"}) == SUPPORTED_VENDORS
    assert frozenset({"mavlink"}) == IN_PROCESS_VENDORS


# ── FleetManager ──────────────────────────────────────────────────────────────


@pytest.fixture
async def bus() -> Any:
    b = InMemoryBus()
    await b.connect()
    yield b
    await b.close()


class _StubRunner:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


def _make_booter(captured: dict[str, _StubRunner]) -> Any:
    async def _boot(_bus: Bus, _registry: AdapterRegistry) -> _StubRunner:
        runner = _StubRunner()
        runner.started = True
        captured["runner"] = runner
        return runner

    return _boot


@pytest.mark.asyncio
async def test_fleet_manager_boots_in_process_vendors(bus: Bus) -> None:
    captured: dict[str, _StubRunner] = {}
    fleet = FleetManager(
        bus=bus,
        vendors=("simulator", "mavlink"),
        booters={"mavlink": _make_booter(captured)},
    )
    await fleet.start()
    assert "runner" in captured
    assert captured["runner"].started
    await fleet.stop()
    assert captured["runner"].stopped


@pytest.mark.asyncio
async def test_fleet_manager_skips_out_of_process_vendors(bus: Bus) -> None:
    """The simulator runs as its own process — the in-process fleet must
    NOT spawn it (would double-boot)."""
    booter_calls: list[str] = []

    async def _booter(_bus: Bus, _registry: AdapterRegistry) -> _StubRunner:
        booter_calls.append("simulator")
        return _StubRunner()

    fleet = FleetManager(
        bus=bus,
        vendors=("simulator",),
        booters={"simulator": _booter},  # type: ignore[dict-item]
    )
    await fleet.start()
    await fleet.stop()
    assert booter_calls == []


@pytest.mark.asyncio
async def test_fleet_manager_continues_when_a_vendor_fails(bus: Bus) -> None:
    async def _failing(_bus: Bus, _registry: AdapterRegistry) -> _StubRunner:
        raise RuntimeError("autopilot offline")

    fleet = FleetManager(
        bus=bus,
        vendors=("mavlink",),
        booters={"mavlink": _failing},
    )
    # Boot must not raise — a transient adapter failure must not take down
    # the backend; the simulator runs of course continue independently.
    await fleet.start()
    assert fleet._runners == []
    await fleet.stop()


# ── fleet_from_env ────────────────────────────────────────────────────────────


def test_fleet_from_env_defaults(
    bus: Bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SWARM_VENDORS", raising=False)
    fleet = fleet_from_env(bus)
    assert fleet.vendors == ("simulator",)


def test_fleet_from_env_reads_env(
    bus: Bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SWARM_VENDORS", "simulator,mavlink")
    fleet = fleet_from_env(bus)
    assert fleet.vendors == ("simulator", "mavlink")


def test_fleet_from_env_raises_on_unknown(
    bus: Bus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SWARM_VENDORS", "simulator,not-a-vendor")
    with pytest.raises(UnknownVendor):
        fleet_from_env(bus)


# `asyncio` re-exported here so the test module's imports compile under
# `from __future__ import annotations` even when only a fixture uses it.
_ = asyncio
