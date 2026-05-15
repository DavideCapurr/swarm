"""MAVLink DroneAdapter — placeholder for PX4 / ArduPilot hardware work.

Covers a huge slice of the non-DJI market: Quantum Systems, Auterion, Parrot
Anafi USA, custom PX4 builds, ArduPilot copters/planes, etc. No ROS2 needed.

Real flight SDK activation is intentionally deferred to Phase 5. MAVSDK-Python
is not installed by the Phase 0-4 extras because its protobuf pin currently
fails the security audit. Phase 5 must pick a secure MAVLink runtime before
hardware execution.
"""

from adapters.mavlink.adapter import MAVLinkAdapter

__all__ = ["MAVLinkAdapter"]
