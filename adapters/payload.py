"""Optional payload-control capability for SWARM agents.

This is intentionally not part of ``DroneAdapter``. Flight adapters that do
not expose payload control remain valid, while a payload-capable unit can
register a controller under the same ``agent_id``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from swarm_core.payloads import PayloadAction, PayloadActionKind, PayloadActionResult


class UnsupportedPayloadAction(RuntimeError):
    """Raised when a controller cannot execute a requested payload action."""


@runtime_checkable
class PayloadController(Protocol):
    agent_id: str
    capabilities: frozenset[PayloadActionKind]

    async def execute(self, action: PayloadAction) -> PayloadActionResult: ...


class PayloadControllerRegistry:
    """Payload controllers keyed by the same agent IDs as ``AdapterRegistry``."""

    def __init__(self) -> None:
        self._by_id: dict[str, PayloadController] = {}

    def register(self, controller: PayloadController) -> None:
        if controller.agent_id in self._by_id:
            raise ValueError(f"Payload controller already registered: {controller.agent_id}")
        self._by_id[controller.agent_id] = controller

    def unregister(self, agent_id: str) -> None:
        self._by_id.pop(agent_id, None)

    def get(self, agent_id: str) -> PayloadController:
        return self._by_id[agent_id]

    def get_optional(self, agent_id: str) -> PayloadController | None:
        return self._by_id.get(agent_id)

    def __len__(self) -> int:
        return len(self._by_id)
