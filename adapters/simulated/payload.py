"""Honest simulated payload controller for demo agents.

No physical light or speaker exists in this path. Every result is explicitly
marked ``SIMULATED`` so the Console/audit trail cannot confuse it with hardware
proof.
"""

from __future__ import annotations

from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.payload import UnsupportedPayloadAction


class SimulatedPayloadController:
    capabilities = frozenset(PayloadActionKind)

    def __init__(self, *, agent_id: str) -> None:
        self.agent_id = agent_id
        self._light_on = False
        self._speaker_active = False
        self._message: PayloadMessage | None = None

    async def execute(self, action: PayloadAction) -> PayloadActionResult:
        if action.agent_id != self.agent_id:
            raise ValueError(
                f"payload action targets {action.agent_id}, controller owns {self.agent_id}"
            )
        if action.kind not in self.capabilities:
            raise UnsupportedPayloadAction(action.kind.value)

        if action.kind is PayloadActionKind.LIGHT_ON:
            self._light_on = True
        elif action.kind is PayloadActionKind.LIGHT_OFF:
            self._light_on = False
        elif action.kind is PayloadActionKind.PLAY_MESSAGE:
            self._speaker_active = True
            self._message = action.message
        elif action.kind is PayloadActionKind.STOP_MESSAGE:
            self._speaker_active = False
            self._message = None

        return PayloadActionResult(
            action_id=action.id,
            agent_id=self.agent_id,
            kind=action.kind,
            status=PayloadActionStatus.SIMULATED,
            execution_mode=PayloadExecutionMode.SIMULATED,
            light_on=self._light_on,
            speaker_active=self._speaker_active,
            message=self._message,
        )
