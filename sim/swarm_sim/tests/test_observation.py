"""Phase 7.B — confirm-by-observation unit tests for perception.observe.

A dispatched drone that physically reaches an anomaly's geo and dwells makes
the sim re-emit that same anomaly with `verified=True`. This is the only path
that drives an anomaly to VERIFIED in the live sim, which R2 (auto-ESCALATE)
depends on. These tests pin the contract: exactly one re-emit per anomaly,
only for airborne drones that *continuously* dwell on station.
"""

from __future__ import annotations

from swarm_core.messages import Anomaly, AnomalyKind, Geo

from sim.swarm_sim.drone import Drone
from sim.swarm_sim.perception import MockPerception

DOCK = Geo(lat=44.7000, lon=8.0300, alt_m=0.0)
# ~38 m NE of the dock — well outside the 15 m confirm radius so a unit
# sitting at the dock never falsely confirms.
HOTSPOT = Geo(lat=44.7002, lon=8.0304, alt_m=30.0)


def _on_station_drone(geo: Geo) -> Drone:
    """A drone hovering (airborne) at `geo`. Sets the internal mode + position
    directly — the runner reads `_mode` the same way (runner.py)."""

    d = Drone(agent_id="sim-1", dock=DOCK)
    d.geo = Geo(lat=geo.lat, lon=geo.lon, alt_m=30.0)
    d._mode = "HOVER"
    return d


def _perception(dwell_s: float = 2.5) -> tuple[MockPerception, list[Anomaly]]:
    emitted: list[Anomaly] = []
    perception = MockPerception(
        territory_center=DOCK,
        confirm_dwell_s=dwell_s,
        on_anomaly=emitted.append,
    )
    return perception, emitted


def test_dwell_triggers_single_verified_reemit() -> None:
    perception, emitted = _perception(dwell_s=2.5)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    assert len(emitted) == 1 and emitted[0].verified is False

    drone = _on_station_drone(HOTSPOT)
    # 30 ticks @ 0.1 s = 3.0 s of dwell ≥ the 2.5 s threshold.
    for _ in range(30):
        perception.observe([drone], dt=0.1)

    verified = [a for a in emitted if a.verified]
    assert len(verified) == 1, f"expected exactly one verified re-emit, got {verified}"
    confirmed = verified[0]
    # Same anomaly identity + the same perception number — only `verified` flips.
    assert confirmed.id == emitted[0].id
    assert confirmed.kind == AnomalyKind.FIRE
    assert confirmed.geo == HOTSPOT
    assert confirmed.confidence == 0.88


def test_no_double_emit_across_many_ticks() -> None:
    perception, emitted = _perception(dwell_s=2.5)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    drone = _on_station_drone(HOTSPOT)
    for _ in range(200):  # far longer than the dwell window
        perception.observe([drone], dt=0.1)
    assert len([a for a in emitted if a.verified]) == 1


def test_drone_never_arriving_triggers_no_confirm() -> None:
    perception, emitted = _perception(dwell_s=2.5)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    # An airborne unit hovering back at the dock (~38 m away) never confirms.
    far = _on_station_drone(DOCK)
    for _ in range(200):
        perception.observe([far], dt=0.1)
    assert [a for a in emitted if a.verified] == []


def test_docked_drone_on_geo_does_not_confirm() -> None:
    """Only *airborne* drones confirm — a docked unit on the geo does not."""

    perception, emitted = _perception(dwell_s=2.5)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    docked = Drone(agent_id="sim-1", dock=DOCK)
    docked.geo = Geo(lat=HOTSPOT.lat, lon=HOTSPOT.lon, alt_m=0.0)  # _mode stays DOCKED
    for _ in range(200):
        perception.observe([docked], dt=0.1)
    assert [a for a in emitted if a.verified] == []


def test_brief_flythrough_resets_dwell() -> None:
    """Dwell must be *continuous* — leaving the radius resets the clock."""

    perception, emitted = _perception(dwell_s=2.5)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    on = _on_station_drone(HOTSPOT)
    off = _on_station_drone(DOCK)

    # 2.0 s on station — below the 2.5 s threshold.
    for _ in range(20):
        perception.observe([on], dt=0.1)
    assert [a for a in emitted if a.verified] == []
    # One tick away resets the accumulator.
    perception.observe([off], dt=0.1)
    # Another 2.0 s — still no confirm because the clock restarted.
    for _ in range(20):
        perception.observe([on], dt=0.1)
    assert [a for a in emitted if a.verified] == []
    # Push continuously past the threshold — now it confirms, exactly once.
    for _ in range(10):
        perception.observe([on], dt=0.1)
    assert len([a for a in emitted if a.verified]) == 1


def test_world_step_drives_observation() -> None:
    """`World.step` must drive `perception.observe` so the live sim confirms
    without any extra wiring (the runner only calls `world.step`)."""

    from sim.swarm_sim.world import World

    emitted: list[Anomaly] = []
    perception, _ = _perception(dwell_s=2.5)
    perception.on_anomaly = emitted.append
    drone = _on_station_drone(HOTSPOT)
    world = World(dock=DOCK, drones=[drone], perception=perception)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)

    for _ in range(30):
        world.step(0.1)

    assert len([a for a in emitted if a.verified]) == 1


def test_real_kinematics_drone_confirms_only_after_arrival() -> None:
    """End-to-end with *real* kinematics (no forced mode/geo): a drone
    commanded to take off and fly to the hotspot confirms the anomaly only
    after it physically arrives and dwells — never while still en route."""

    from sim.swarm_sim.world import World

    perception, emitted = _perception(dwell_s=2.5)
    drone = Drone(agent_id="sim-1", dock=DOCK)
    world = World(dock=DOCK, drones=[drone], perception=perception)
    perception.emit_anomaly(AnomalyKind.FIRE, HOTSPOT, 0.88)
    drone.command_takeoff()
    drone.command_goto(HOTSPOT)

    arrived_at: int | None = None
    confirmed_at: int | None = None
    for i in range(600):  # up to 60 world-seconds
        world.step(0.1)
        if arrived_at is None and drone.at_target(HOTSPOT):
            arrived_at = i
        if confirmed_at is None and any(a.verified for a in emitted):
            confirmed_at = i

    assert arrived_at is not None, "drone never reached the hotspot"
    assert confirmed_at is not None, "anomaly was never confirmed"
    assert len([a for a in emitted if a.verified]) == 1
    # Confirmation strictly follows physical arrival (+ the dwell window).
    assert confirmed_at > arrived_at
