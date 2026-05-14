"""Light Python simulator — placeholder for Gazebo + PX4 SITL.

The sim is a 2D vineyard with:
  - 1 dock (origin),
  - N kinematic drones starting docked,
  - an ignition scheduler that injects SMOKE anomalies at configurable times.

The sim is the target of `adapters.simulated.SimulatedAdapter`. When SWARM
graduates to Gazebo, the same `SimulatedAdapter` shape is replaced by a Gazebo
bridge; `core/` and `orchestrator/` are unaffected.
"""

from sim.swarm_sim.drone import Drone
from sim.swarm_sim.perception import MockPerception
from sim.swarm_sim.world import World

__all__ = ["Drone", "MockPerception", "World"]
