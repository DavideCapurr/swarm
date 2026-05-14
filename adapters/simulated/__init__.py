"""Simulated DroneAdapter — drives the 2D Python sim.

This is the adapter that makes `make demo` run without any vendor SDK installed.
It implements the full `DroneAdapter` Protocol against `sim.swarm_sim.drone.Drone`
state machines so we can prove the auction + mission flow end-to-end.
"""

from adapters.simulated.adapter import SimulatedAdapter

__all__ = ["SimulatedAdapter"]
