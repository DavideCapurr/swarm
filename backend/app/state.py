"""In-process state holder for the backend.

The backend's job in commit 1 is small but real:
  - subscribe to the SWARM OS bus,
  - keep an authoritative-enough recent snapshot of fleet + anomalies + events,
  - expose REST + WebSocket so the frontend can render.

The DB layer is bootstrapped in `db/` but commit 1 keeps the hot path in-memory
to keep the demo zero-friction. Telemetry persistence to TimescaleDB is wired
in a follow-up.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from swarm_core.messages import Anomaly, FleetState, Telemetry


@dataclass
class BackendState:
    fleet: dict[str, FleetState] = field(default_factory=dict)
    anomalies: dict[str, Anomaly] = field(default_factory=dict)
    last_telemetry: dict[str, Telemetry] = field(default_factory=dict)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))

    def add_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, **payload})


STATE = BackendState()
