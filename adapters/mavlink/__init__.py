"""MAVLink DroneAdapter — speaks to any PX4 / ArduPilot drone via MAVSDK-Python.

Covers a huge slice of the non-DJI market: Quantum Systems, Auterion, Parrot
Anafi USA, custom PX4 builds, ArduPilot copters/planes, etc. No ROS2 needed.

To use this adapter for real:
  1. `pip install -e ".[mavlink]"` to pull MAVSDK.
  2. Point `MAVLINK_CONNECTION` env var at the autopilot
     (e.g. `udp://:14540` for PX4 SITL, `serial:///dev/ttyACM0:115200` for hardware).
"""

from adapters.mavlink.adapter import MAVLinkAdapter

__all__ = ["MAVLinkAdapter"]
