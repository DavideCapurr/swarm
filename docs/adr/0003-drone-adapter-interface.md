# ADR 0003 — DroneAdapter interface (the interoperability moat)

**Status**: Accepted  
**Date**: 2026-05-13  
**Authority clarification**: 2026-08-15 — see ADR 0011

## Context

SWARM's #1 priority is interfacing with **many drones already on the market**
and orchestrating them as one fleet. The orchestrator must never speak a
vendor-specific dialect; otherwise the moat collapses into N parallel
integrations.

The adapter boundary must also preserve decision authority. A vendor adapter is
not a delegated fleet brain: it translates SWARM-issued execution intent into a
vendor/autopilot protocol and reports state/evidence back to SwarmOS.

## Decision

A single `DroneAdapter` `typing.Protocol`, defined in `adapters/base.py`, is the
only surface the orchestrator sees. Every vendor implementation
(`adapters/<vendor>/`) implements this Protocol and is registered in the
`AdapterRegistry`.

Mission-level decision authority is governed by
[`ADR 0011`](0011-central-decision-authority.md): **SwarmOS decides; physical
agents execute.**

### Interface (canonical)

```python
class DroneAdapter(Protocol):
    # identity & capability
    vendor: str
    model: str
    capabilities: Capabilities
    autopilot_failsafes: Failsafes

    # lifecycle
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def health(self) -> HealthReport: ...

    # safety envelope (SWARM declares it; autopilot may enforce it locally)
    async def set_safety(
        self, geofence: Polygon, max_alt_m: float, rtl_battery_pct: int
    ) -> None: ...

    # SWARM-issued mission execution
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

### Authority of the interface

An adapter may:

- translate an already-selected `MissionTask` to vendor commands;
- delegate low-level flight execution to the onboard autopilot;
- report telemetry, captures, health and mission progress;
- enforce bounded local safety behavior such as geofence, low-battery and
  lost-link failsafes.

An adapter must **not**:

- allocate itself or another aircraft to a mission;
- run the fleet allocator/autonomy/scheduler;
- choose a new mission objective from local sensor data;
- command or retask peer agents;
- form an independent mission-authority layer.

`divert()` is therefore an imperative execution primitive called **by SwarmOS**.
It is not permission for the adapter to decide when or why a diversion should
occur.

### Conformance suite

`adapters/tests/conformance.py` defines a generic test class
`AdapterConformanceTests` that vendor adapters instantiate. The common
behavioral surface includes:

1. connect/disconnect;
2. telemetry streaming;
3. execution of a SWARM-issued VERIFY mission;
4. execution of a SWARM-issued mid-flight divert;
5. declared local safety failsafes;
6. capability reporting.

Stub adapters (`autel/`, `parrot/`, `skydio/`, `dji_psdk/`) remain stubs until
wired; they must not falsely advertise working behavior.

## Consequences

- The orchestrator is vendor-agnostic by construction; there is no place to
  write `if isinstance(agent, DJIAdapter)`.
- Adding a new vendor = one new adapter implementation passing the conformance
  and authority-boundary tests. Fleet-decision code does not move into that
  adapter.
- Vendor SDKs are isolated as optional extras in `pyproject.toml`.
- Commodity autopilots may keep strong low-level flight autonomy while mission
  intelligence remains centralized in SwarmOS.
- Compromising one physical endpoint does not give that endpoint legitimate
  authority to allocate or command the rest of the fleet, although telemetry
  poisoning and direct endpoint compromise remain security concerns.

## Discipline rules

1. Vendor-specific types never leak past `adapters/<vendor>/`. The boundary
   converts to `core/swarm_core/messages.py` types.
2. Mission DSL primitives (`PATROL`, `VERIFY`, `COVER`, `RELAY`, `RTL_DOCK`)
   must be expressible by every vendor's autopilot. If a primitive cannot be
   expressed on a given vendor, either the adapter raises `UnsupportedMission`
   or SwarmOS decomposes the higher-level objective into supported execution
   primitives. The adapter must not invent its own fleet strategy.
3. Stream rates: telemetry minimum 1 Hz, target 10 Hz; video best-effort.
4. Adapter implementations must not import central decision-authority modules
   such as allocator, scheduler, autonomy or the orchestrator service.
