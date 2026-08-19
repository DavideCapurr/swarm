from __future__ import annotations

from swarm_core.messages import Geo

from sim.swarm_sim.drone import Drone


def test_waypoint_arrival_requires_vertical_convergence_after_xy_arrival() -> None:
    dock = Geo(lat=44.7, lon=8.03, alt_m=0.0)
    drone = Drone(
        agent_id="sim-proof",
        dock=dock,
        speed_mps=100.0,
        climb_mps=20.0,
    )

    drone.command_takeoff()
    for _ in range(20):
        drone.step(0.1)
        if drone.is_airborne:
            break
    assert drone.is_airborne

    target = Geo(lat=dock.lat, lon=dock.lon, alt_m=55.0)
    drone.command_goto(target)

    # Horizontal coincidence alone is not a disposition convergence proof.
    assert not drone.at_target(target)

    for _ in range(30):
        drone.step(0.1)
        if drone.at_target(target):
            break

    assert drone.at_target(target)
    assert abs(drone.geo.alt_m - 55.0) < 1.5
