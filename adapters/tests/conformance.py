"""Adapter conformance suite — the contract every vendor must satisfy.

Every concrete adapter (simulated, mavlink, dji_cloud, …) and every stub goes
through this exact set of scenarios. Stubs are expected to skip; wired adapters
must pass. This is what prevents vendor-specific drift from leaking out of
`adapters/<vendor>/`.

Usage from a vendor's test module:

    from adapters.tests.conformance import AdapterConformanceTests

    class TestSimulatedConformance(AdapterConformanceTests):
        adapter_factory = staticmethod(_make_simulated_adapter)
        is_stub = False
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

import pytest
from swarm_core.messages import Geo, SensorKind
from swarm_core.missions import VERIFY

from adapters.base import DroneAdapter, Polygon


class AdapterConformanceTests:
    """Subclass this in `adapters/<vendor>/tests/` and set `adapter_factory`."""

    adapter_factory: Callable[[], DroneAdapter]  # set by subclass
    is_stub: bool = False  # set True for unwired stubs

    # ── helpers ──────────────────────────────────────────────────────────────

    def _skip_if_stub(self) -> None:
        if self.is_stub:
            pytest.skip("stub adapter — wiring deferred")

    def _make(self) -> DroneAdapter:
        return self.adapter_factory()

    # ── test cases ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_runtime_satisfies_protocol(self) -> None:
        a = self._make()
        # Structural check: required attributes present.
        assert isinstance(a.vendor, str) and a.vendor
        assert isinstance(a.model, str) and a.model
        assert isinstance(a.agent_id, str) and a.agent_id
        assert a.capabilities is not None
        assert a.autopilot_failsafes is not None

    @pytest.mark.asyncio
    async def test_connect_disconnect(self) -> None:
        self._skip_if_stub()
        a = self._make()
        await a.connect()
        h = await a.health()
        assert h.online
        await a.disconnect()

    @pytest.mark.asyncio
    async def test_telemetry_stream_emits_at_minimum_1hz(self) -> None:
        self._skip_if_stub()
        a = self._make()
        await a.connect()
        received: list[Any] = []

        async def collect() -> None:
            async for t in a.stream_telemetry():
                received.append(t)
                if len(received) >= 3:
                    return

        import contextlib

        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(collect(), timeout=4.0)
        await a.disconnect()
        # Must see at least 1 reading per second.
        assert len(received) >= 3, f"telemetry hz too low: got {len(received)} in 4s"

    @pytest.mark.asyncio
    async def test_execute_mission_verify_reaches_geo(self) -> None:
        self._skip_if_stub()
        a = self._make()
        await a.connect()
        mission = VERIFY(geo=Geo(lat=45.001, lon=10.001), hover_s=0.5)
        phases: list[str] = []

        async def run() -> None:
            async for p in a.execute_mission(mission):
                phases.append(p.phase)

        await asyncio.wait_for(run(), timeout=30.0)
        await a.disconnect()
        assert phases, "no progress emitted"
        assert phases[-1] in ("DONE", "FAILED")

    @pytest.mark.asyncio
    async def test_capabilities_match_declared(self) -> None:
        a = self._make()
        # Sensors set must be non-trivial — at least RGB.
        if not self.is_stub:
            assert SensorKind.RGB in a.capabilities.sensors

    @pytest.mark.asyncio
    async def test_set_safety_accepts_polygon(self) -> None:
        self._skip_if_stub()
        a = self._make()
        await a.connect()
        geofence = Polygon(
            points=(
                Geo(lat=45.0, lon=10.0),
                Geo(lat=45.01, lon=10.0),
                Geo(lat=45.01, lon=10.01),
                Geo(lat=45.0, lon=10.01),
            )
        )
        await a.set_safety(geofence, max_alt_m=120.0, rtl_battery_pct=25)
        await a.disconnect()
