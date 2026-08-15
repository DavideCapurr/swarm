"""In-process state holder for the backend.

The backend subscribes to the SWARM OS bus, keeps recent authoritative runtime
snapshots, and exposes them over REST/WebSocket. Multi-agent execution-group
composition is stored exactly as SwarmOS publishes it; the backend does not
recompute group membership or roles.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from swarm_core.execution_groups import ExecutionGroup
from swarm_core.messages import Anomaly, FleetState, Telemetry


@dataclass
class BackendState:
    fleet: dict[str, FleetState] = field(default_factory=dict)
    anomalies: dict[str, Anomaly] = field(default_factory=dict)
    last_telemetry: dict[str, Telemetry] = field(default_factory=dict)
    execution_groups: dict[str, ExecutionGroup] = field(default_factory=dict)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=500))

    def add_event(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"kind": kind, **payload})


STATE = BackendState()
