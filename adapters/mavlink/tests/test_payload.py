from __future__ import annotations

from typing import Any

import pytest
from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.payload import MAV_CMD_DO_SET_ACTUATOR, MAVLinkPayloadController


class OutputConfirmingFakeMAVLinkEndpoint(FakeMAVLinkEndpoint):
    """Mimic PX4 v1.14: actuator command has no ACK, output state is observable."""

    def __init__(self) -> None:
        super().__init__(drop_command_acks={MAV_CMD_DO_SET_ACTUATOR})

    def _handle(self, msg: Any) -> None:
        super()._handle(msg)
        if msg.get_type() != "COMMAND_LONG":
            return
        if int(getattr(msg, "command", -1)) != MAV_CMD_DO_SET_ACTUATOR:
            return
        value = float(getattr(msg, "param1", 0.0))
        raw = 2000 if value >= 0.5 else 1000 if value <= -0.5 else 1500
        outputs = [1500] * 8
        outputs[4] = raw
        self._send(self._mav.servo_output_raw_encode(0, 0, *outputs))


@pytest.mark.asyncio
async def test_light_command_confirms_px4_output_without_actuator_ack() -> None:
    endpoint = OutputConfirmingFakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        controller = MAVLinkPayloadController(
            adapter=adapter,
            light_actuator_number=1,
            light_output_channel=5,
        )
        result = await controller.execute(
            PayloadAction(agent_id="mav-1", kind=PayloadActionKind.LIGHT_ON)
        )
        assert MAV_CMD_DO_SET_ACTUATOR in endpoint.state.command_calls
        assert result.status is PayloadActionStatus.CONFIRMED
        assert result.execution_mode is PayloadExecutionMode.MAVLINK_OUTPUT_CONFIRMED
        assert result.light_on is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()


def test_light_mapping_is_bounded_and_complete() -> None:
    endpoint = FakeMAVLinkEndpoint()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
    )
    with pytest.raises(ValueError):
        MAVLinkPayloadController(
            adapter=adapter,
            light_actuator_number=0,
            light_output_channel=5,
        )
    with pytest.raises(ValueError):
        MAVLinkPayloadController(
            adapter=adapter,
            light_actuator_number=7,
            light_output_channel=5,
        )
    with pytest.raises(ValueError):
        MAVLinkPayloadController(
            adapter=adapter,
            light_actuator_number=1,
            light_output_channel=9,
        )
    with pytest.raises(ValueError):
        MAVLinkPayloadController(adapter=adapter, light_actuator_number=1)


@pytest.mark.asyncio
async def test_demo_speaker_never_claims_px4_output_confirmation() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        controller = MAVLinkPayloadController(
            adapter=adapter,
            light_actuator_number=1,
            light_output_channel=5,
            simulate_speaker=True,
        )
        result = await controller.execute(
            PayloadAction(
                agent_id="mav-1",
                kind=PayloadActionKind.PLAY_MESSAGE,
                message=PayloadMessage.RESTRICTED_AREA,
            )
        )
        assert result.status is PayloadActionStatus.SIMULATED
        assert result.execution_mode is PayloadExecutionMode.SIMULATED
        assert result.speaker_active is True
        assert MAV_CMD_DO_SET_ACTUATOR not in endpoint.state.command_calls
    finally:
        await adapter.disconnect()
        await endpoint.stop()
