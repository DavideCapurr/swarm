"""DJI Cloud DroneAdapter — speaks to DJI Dock / DJI Enterprise drones via the
DJI Cloud API (REST + MQTT).

Reference: https://developer.dji.com/doc/cloud-api-tutorial/en/

Mission DSL mapping:
  PATROL → upload a Waypoint Mission KMZ, dispatch via Cloud API.
  VERIFY → Cloud command `flight_authority` + waypoint mission with single point + camera trigger.
  RTL_DOCK → Cloud command `return_home`.
  RELAY → custom hold-at-altitude waypoint mission with long stay time.

Telemetry arrives via MQTT topics under `thing/product/<sn>/osd`.

Commit-1 scope: protocol shape + auth/header skeleton; the actual mission
upload flow requires a DJI developer account, an enrolled aircraft/Dock, and
cloud server endpoints. Methods raise `NotConfigured` when env is missing.
"""

from adapters.dji_cloud.adapter import DJICloudAdapter, NotConfigured

__all__ = ["DJICloudAdapter", "NotConfigured"]
