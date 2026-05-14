# ADR 0003 — DroneAdapter interface (the interoperability moat)

**Status**: Accepted
**Date**: 2026-05-13

## Context

SWARM's #1 priority is interfacing with **many drones already on the market**
and orchestrating them as one fleet. The orchestrator must never speak a
vendor-specific dialect; otherwise the moat collapses into N parallel
integrations.

## Decision

A single `DroneAdapter` `typing.Protocol`, defined in `adapters/base.py`, is
the only surface the orchestrator sees. Every vendor implementation
(`adapters/<vendor>/`) implements this Protocol and is registered in the
`AdapterRegistry`.

### Interface (canonical)

```python
class DroneAdapter(Protocol):
    # identity & capability
    vendor: str
    model: str
    capabilities: Capabilities          # rgb, thermal, lidar, payload_drop, rtk
    autopilot_failsafes: Failsafes      # lost_link_rtl, low_batt_rtl, geofence_rtl

    # lifecycle
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def health(self) -> HealthReport: ...

    # safety envelope (SWARM declares the envelope, autopilot enforces)
    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None: ...

    # mission-level autonomy
    async def execute_mission(
        self, mission: MissionTask
    ) -> AsyncIterator[MissionProgress]: ...
    async def pause_mission(self) -> None: ...
    async def resume_mission(self) -> None: ...
    async def cancel_mission(self) -> None: ...
    async def divert(self, new_waypoint: Waypoint) -> None: ...
    async def request_capture(self, sensor: SensorKind) -> CaptureResult: ...

    # streams
    def stream_telemetry(self) -> AsyncIterator[Telemetry]: ...
    def stream_video(self) -> AsyncIterator[VideoFrame]: ...
```

### Conformance suite

`adapters/tests/conformance.py` defines a generic test class
`AdapterConformanceTests` that every adapter must instantiate. The same
scenarios run against every vendor:

1. `test_connect_disconnect`
2. `test_telemetry_stream_emits_at_minimum_1hz`
3. `test_execute_mission_verify_reaches_geo`
4. `test_divert_mid_flight`
5. `test_rtl_on_low_battery_failsafe`
6. `test_capabilities_match_declared`

Stub adapters (`autel/`, `parrot/`, `skydio/`, `dji_psdk/`) raise
`NotImplementedError` from their methods AND are marked `pytest.skip` in the
conformance suite until wired — they declare their protocol shape but do not
falsely pass tests.

## Consequences

- The orchestrator is vendor-agnostic by construction; there is no place to
  write `if isinstance(agent, DJIAdapter)`.
- Adding a new vendor = one new folder + passing the conformance suite. Zero
  changes to `core/`, `orchestrator/`, `backend/`, `frontend/`.
- Vendor SDKs are isolated as optional extras in `pyproject.toml` — installing
  SWARM does not require all SDKs.

## Discipline rules

1. Vendor-specific types never leak past `adapters/<vendor>/`. The boundary
   converts to `core/swarm_core/messages.py` types.
2. Mission DSL primitives (`PATROL`, `VERIFY`, `COVER`, `RELAY`, `RTL_DOCK`)
   must be expressible by every vendor's autopilot. If a primitive cannot
   be expressed on a given vendor, either (a) the adapter raises
   `UnsupportedMission`, OR (b) the primitive is decomposed in `core/` into
   atomics every vendor supports — never (c) hack vendor-specific into the
   orchestrator.
3. Stream rates: telemetry minimum 1 Hz, target 10 Hz; video best-effort.
