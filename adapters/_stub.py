"""Shared base for vendor adapter STUBS — DJI PSDK, Autel, Parrot, Skydio.

Stubs declare the protocol shape (so type checkers and the registry accept them)
but every method raises `NotImplementedError`. The conformance test suite is
expected to `pytest.skip` stub adapters until they are wired.

Why this exists: we want the *contract* with each vendor to be visible in the
codebase from day 1. When the time comes to integrate (DJI dev account
provisioned, Olympe installed, Skydio enterprise API key obtained), it is a
question of replacing the stub body — not designing the interface from scratch
under deadline pressure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from swarm_core.messages import (
    CaptureResult,
    MissionProgress,
    MissionTask,
    SensorKind,
    Telemetry,
    Waypoint,
)

from adapters.base import (
    Capabilities,
    Failsafes,
    HealthReport,
    Polygon,
    VideoFrame,
)


class StubAdapter:
    """Inherit from this to declare a vendor adapter that isn't wired yet."""

    vendor: str = "stub"

    def __init__(self, *, agent_id: str, model: str = "unknown") -> None:
        self.agent_id = agent_id
        self.model = model
        self.capabilities = Capabilities()
        self.autopilot_failsafes = Failsafes()

    @property
    def stub_reason(self) -> str:
        return (
            f"adapters/{self.vendor}/ is a typed stub — vendor SDK not wired "
            f"in this commit. See adapters/_stub.py."
        )

    async def connect(self) -> None:
        raise NotImplementedError(self.stub_reason)

    async def disconnect(self) -> None:
        raise NotImplementedError(self.stub_reason)

    async def health(self) -> HealthReport:
        raise NotImplementedError(self.stub_reason)

    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None:
        raise NotImplementedError(self.stub_reason)

    async def execute_mission(self, mission: MissionTask) -> AsyncIterator[MissionProgress]:  # type: ignore[override]
        raise NotImplementedError(self.stub_reason)
        if False:
            yield  # pragma: no cover

    async def pause_mission(self) -> None:
        raise NotImplementedError(self.stub_reason)

    async def resume_mission(self) -> None:
        raise NotImplementedError(self.stub_reason)

    async def cancel_mission(self) -> None:
        raise NotImplementedError(self.stub_reason)

    async def divert(self, new_waypoint: Waypoint) -> None:
        raise NotImplementedError(self.stub_reason)

    async def request_capture(self, sensor: SensorKind) -> CaptureResult:
        raise NotImplementedError(self.stub_reason)

    async def stream_telemetry(self) -> AsyncIterator[Telemetry]:  # type: ignore[override]
        raise NotImplementedError(self.stub_reason)
        if False:
            yield  # pragma: no cover

    async def stream_video(self) -> AsyncIterator[VideoFrame]:  # type: ignore[override]
        raise NotImplementedError(self.stub_reason)
        if False:
            yield  # pragma: no cover
