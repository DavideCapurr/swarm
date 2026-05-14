"""SWARM OS — multi-vendor drone interoperability layer.

Every `adapters/<vendor>/` package exports a class implementing the `DroneAdapter`
Protocol from `adapters.base`. The orchestrator imports the abstract `DroneAdapter`
ONLY — it does not know vendor-specific types.
"""

from adapters.base import (
    AdapterRegistry,
    Capabilities,
    DroneAdapter,
    Failsafes,
    HealthReport,
    VideoFrame,
)

__all__ = [
    "AdapterRegistry",
    "Capabilities",
    "DroneAdapter",
    "Failsafes",
    "HealthReport",
    "VideoFrame",
]
