"""SwarmOS simulated kernel.

Phase 3 keeps the kernel in memory but exposes a single module-level
`COORDINATOR` so the bus consumer, the WS hub, and the operator action
endpoints all share one state-mutating + event-detecting instance.
"""

from swarm_os.coordinator import SwarmCoordinator
from swarm_os.state import SWARM_STATE, SwarmState

COORDINATOR = SwarmCoordinator(SWARM_STATE)

__all__ = ("COORDINATOR", "SWARM_STATE", "SwarmCoordinator", "SwarmState")
