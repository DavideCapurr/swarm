"""Run the conformance suite against the simulated adapter."""

from __future__ import annotations

from swarm_core.messages import Geo

from adapters.simulated import SimulatedAdapter
from adapters.tests.conformance import AdapterConformanceTests
from sim.swarm_sim.drone import Drone


def _make_simulated() -> SimulatedAdapter:
    dock = Geo(lat=45.0, lon=10.0)
    drone = Drone(agent_id="sim-1", dock=dock, speed_mps=50.0)
    return SimulatedAdapter(agent_id="sim-1", drone=drone)


class TestSimulatedAdapterConformance(AdapterConformanceTests):
    adapter_factory = staticmethod(_make_simulated)
    is_stub = False
