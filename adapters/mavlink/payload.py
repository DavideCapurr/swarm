"""MAVLink-backed payload control for light plus explicit demo audio state.

PX4 v1.14's generic payload path is ``MAV_CMD_DO_SET_ACTUATOR``. A configured
flight-controller output maps ``Offboard Actuator Set 1..6`` to the physical
payload line.

PX4 v1.14 publishes this command onto ``vehicle_command`` instead of returning
a direct COMMAND_ACK from the MAVLink receiver. The controller therefore does
not invent ACK evidence: it requests ``SERVO_OUTPUT_RAW``, sends the actuator
command, and reports success only after the configured PWM output is observed
in the requested state.

That proves the PX4 command-to-output path. It still does not prove that a
physical lamp, driver or cable exists beyond the flight-controller output.

There is no vendor-neutral MAVLink primitive for arbitrary speaker playback.
When explicitly enabled for a demo, speaker state is simulated and always
reported as such.
"""

from __future__ import annotations

import asyncio
import math

from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionResult,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.mavlink.adapter import MAVLinkAdapter, MAVLinkCommandError
from adapters.payload import UnsupportedPayloadAction

# Canonical ids from MAVLink common.xml. pymavlink 2.4.49's generated
# ardupilotmega v1 dialect used by this project predates the SET_ACTUATOR
# symbol, even though the wire command is supported by PX4 v1.14.
MAV_CMD_DO_SET_ACTUATOR = 187
MAV_CMD_SET_MESSAGE_INTERVAL = 511
MAVLINK_MSG_ID_SERVO_OUTPUT_RAW = 36


class MAVLinkPayloadController:
    def __init__(
        self,
        *,
        adapter: MAVLinkAdapter,
        light_actuator_number: int | None = None,
        light_output_channel: int | None = None,
        light_on_value: float = 1.0,
        light_off_value: float = -1.0,
        simulate_speaker: bool = False,
    ) -> None:
        if (light_actuator_number is None) != (light_output_channel is None):
            raise ValueError(
                "light_actuator_number and light_output_channel must be configured together"
            )
        if light_actuator_number is not None and not 1 <= light_actuator_number <= 6:
            raise ValueError("light_actuator_number must be in [1, 6]")
        if light_output_channel is not None and not 1 <= light_output_channel <= 8:
            raise ValueError("light_output_channel must be in [1, 8]")
        if not -1.0 <= light_on_value <= 1.0:
            raise ValueError("light_on_value must be in [-1, 1]")
        if not -1.0 <= light_off_value <= 1.0:
            raise ValueError("light_off_value must be in [-1, 1]")

        self.adapter = adapter
        self.agent_id = adapter.agent_id
        self._light_actuator_number = light_actuator_number
        self._light_output_channel = light_output_channel
        self._light_on_value = light_on_value
        self._light_off_value = light_off_value
        self._simulate_speaker = simulate_speaker
        self._servo_stream_ready = False

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
            enabled = action.kind is PayloadActionKind.LIGHT_ON
            await self._set_light_and_confirm_output(enabled)
            self._light_on = enabled
            return PayloadActionResult(
                action_id=action.id,
                agent_id=self.agent_id,
                kind=action.kind,
                status=PayloadActionStatus.CONFIRMED,
                execution_mode=PayloadExecutionMode.MAVLINK_OUTPUT_CONFIRMED,
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

    async def _ensure_servo_output_stream(self) -> None:
        if self._servo_stream_ready:
            return
        await self.adapter._send_command_long(
            MAV_CMD_SET_MESSAGE_INTERVAL,
            param1=float(MAVLINK_MSG_ID_SERVO_OUTPUT_RAW),
            param2=100_000.0,
        )
        self._servo_stream_ready = True

    async def _set_light_and_confirm_output(self, enabled: bool) -> None:
        assert self._light_actuator_number is not None
        assert self._light_output_channel is not None

        await self._ensure_servo_output_stream()
        output_field = f"servo{self._light_output_channel}_raw"

        def _matches_output(msg: object) -> bool:
            if getattr(msg, "get_type", lambda: "")() != "SERVO_OUTPUT_RAW":
                return False
            raw = int(getattr(msg, output_field, 0))
            return raw >= 1750 if enabled else 0 < raw <= 1250

        output_seen = self.adapter._create_waiter(_matches_output)
        value = self._light_on_value if enabled else self._light_off_value
        params = [math.nan] * 6
        params[self._light_actuator_number - 1] = value
        mav = self.adapter._require_mav()
        loop = asyncio.get_running_loop()

        try:
            await loop.run_in_executor(
                None,
                lambda: mav.mav.command_long_send(
                    mav.target_system,
                    mav.target_component,
                    MAV_CMD_DO_SET_ACTUATOR,
                    0,
                    params[0],
                    params[1],
                    params[2],
                    params[3],
                    params[4],
                    params[5],
                    0.0,
                ),
            )
            try:
                await asyncio.wait_for(output_seen, timeout=self.adapter._response_timeout_s)
            except TimeoutError as exc:
                raise MAVLinkCommandError(
                    "MAV_CMD_DO_SET_ACTUATOR sent but configured PWM output was not observed"
                ) from exc
        finally:
            self.adapter._waiters = [
                waiter for waiter in self.adapter._waiters if waiter.future is not output_seen
            ]
