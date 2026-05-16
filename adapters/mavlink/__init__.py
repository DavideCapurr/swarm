"""MAVLink DroneAdapter — PX4 / ArduPilot via pymavlink (Phase 5).

The Phase 0 stub used MAVSDK; Phase 5 rewrites the adapter on top of
`pymavlink`, the pure-Python wire-protocol library. No protobuf transitive
dependency, so the Phase 0 audit blocker that ruled out MAVSDK does not
apply. SITL boot + radio hardware acceptance is documented in
`docs/adapters/mavlink-setup.md`.
"""

from adapters.mavlink.adapter import (
    HEARTBEAT_TIMEOUT_S,
    MAVLinkAdapter,
    RejectedMission,
    point_in_polygon,
)

__all__ = (
    "HEARTBEAT_TIMEOUT_S",
    "MAVLinkAdapter",
    "RejectedMission",
    "point_in_polygon",
)
