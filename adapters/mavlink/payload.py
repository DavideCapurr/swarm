"""MAVLink-backed payload control for light plus explicit demo audio state.

PX4 v1.14's generic payload path is ``MAV_CMD_DO_SET_ACTUATOR``. A configured
flight-controller output maps ``Offboard Actuator Set 1..6`` to the physical
payload line. This controller addresses one of those six actuator values and
leaves every other value as NaN/ignore.

An accepted ``COMMAND_ACK`` proves the PX4/MAVLink command path only. Physical
hardware still requires the corresponding PX4 output mapping and a connected
light/driver.

There is no vendor-neutral MAVLink primitive for arbitrary speaker playback.
When explicitly enabled for a demo, speaker state is simulated and always
reported as such.
"""

from __future__ import annotations

import math

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
        light_actuator_number: int | None = None,
        light_on_value: float = 1.0,
        light_off_value: float = -1.0,
        simulate_speaker: bool = False,
    ) -> None:
        if light_actuator_number is not None and not 1 <= light_actuator_number <= 6:
            raise ValueError("light_actuator_number must be in [1, 6]")
        if not -1.0 <= light_on_value <= 1.0:
            raise ValueError("light_on_value must be in [-1, 1]")
        if not -1.0 <= light_off_value <= 1.0:
            raise ValueError("light_off_value must be in [-1, 1]")

        self.adapter = adapter
        self.agent_id = adapter.agent_id
        self._light_actuator_number = light_actuator_number
        self._light_on_value = light_on_value
        self._light_off_value = light_off_value
        self._simulate_speaker = simulate_speaker

        capabilities: set[PayloadActionKind] = set()
        if light_actuator_number is not None:
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
            assert self._light_actuator_number is not None
            enabled = action.kind is PayloadActionKind.LIGHT_ON
            value = self._light_on_value if enabled else self._light_off_value
            params = [math.nan] * 6
            params[self._light_actuator_number - 1] = value
            await self.adapter._send_command_long(
                mavutil.mavlink.MAV_CMD_DO_SET_ACTUATOR,
                param1=params[0],
                param2=params[1],
                param3=params[2],
                param4=params[3],
                param5=params[4],
                param6=params[5],
                param7=0.0,
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
