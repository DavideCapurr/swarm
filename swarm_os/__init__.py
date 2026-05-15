"""SwarmOS simulated kernel.

Phase 1 keeps the kernel in memory. It projects raw bus messages into the
Console-facing contracts defined in `swarm_core.messages`.
"""

from swarm_os.state import SWARM_STATE, SwarmState

__all__ = ("SWARM_STATE", "SwarmState")
