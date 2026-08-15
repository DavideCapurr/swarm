"""MAVLink-backed payload control for light plus explicit demo audio state.

The light path is real protocol traffic: ``MAV_CMD_DO_SET_RELAY`` is sent
through the existing ACK-validated MAVLink command path. An ACK proves the
PX4/SITL command path, not that physical light hardware exists.

There is no vendor-neutral MAVLink primitive for arbitrary speaker playback.
When explicitly enabled for a demo, speaker state is therefore simulated and
always reported as such.
"""

from __future__ import annotations

from pymavlink import mavutil
from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.payload import UnsupportedPayloadAction


class MAVLinkPayloadController:
    def __init__(
        self,
        *,
        adapter: MAVLinkAdapter,
        light_relay_index: int | None = None,
        simulate_speaker: bool = False,
    ) -> None:
        if light_relay_index is not None and light_relay_index < 0:
            raise ValueError("light_relay_index must be >= 0")
        self.adapter = adapter
        self.agent_id = adapter.agent_id
        self._light_relay_index = light_relay_index
        self._simulate_speaker = simulate_speaker
        capabilities: set[PayloadActionKind] = set()
        if light_relay_index is not None:
            capabilities.update({PayloadActionKind.LIGHT_ON, PayloadActionKind.LIGHT_OFF})
        if simulate_speaker:
            capabilities.update(
                {PayloadActionKind.PLAY_MESSAGE, PayloadActionKind.STOP_MESSAGE}
            )
        self.capabilities = frozenset(capabilities)
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

        if action.kind in {PayloadActionKind.LIGHT_ON, PayloadActionKind.LIGHT_OFF}:
            assert self._light_relay_index is not None
            enabled = action.kind is PayloadActionKind.LIGHT_ON
            await self.adapter._send_command_long(
                mavutil.mavlink.MAV_CMD_DO_SET_RELAY,
                param1=float(self._light_relay_index),
                param2=1.0 if enabled else 0.0,
            )
            self._light_on = enabled
            return PayloadActionResult(
                action_id=action.id,
                agent_id=self.agent_id,
                kind=action.kind,
                status=PayloadActionStatus.ACKNOWLEDGED,
                execution_mode=PayloadExecutionMode.MAVLINK_ACK,
                light_on=self._light_on,
                speaker_active=self._speaker_active,
                message=self._message,
            )

        if action.kind is PayloadActionKind.PLAY_MESSAGE:
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
