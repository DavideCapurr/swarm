"""Module-level WS hub so multiple routers can broadcast to the same clients.

Phase 3 needs both the bus consumer (telemetry-driven frames) and the action
endpoints (operator command lifecycle frames) to fan out through the same
hub. Keeping the singleton here avoids a circular import between `main` and
`api.actions`.
"""

from __future__ import annotations

from backend.app.ws.telemetry import WSHub

HUB = WSHub()

__all__ = ("HUB",)
