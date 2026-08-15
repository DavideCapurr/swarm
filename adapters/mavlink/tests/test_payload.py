from __future__ import annotations

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


@pytest.mark.asyncio
async def test_light_command_uses_mavlink_actuator_and_waits_for_ack() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        controller = MAVLinkPayloadController(adapter=adapter, light_actuator_number=1)
        result = await controller.execute(
            PayloadAction(agent_id="mav-1", kind=PayloadActionKind.LIGHT_ON)
        )
        assert MAV_CMD_DO_SET_ACTUATOR in endpoint.state.command_calls
        assert result.status is PayloadActionStatus.ACKNOWLEDGED
        assert result.execution_mode is PayloadExecutionMode.MAVLINK_ACK
        assert result.light_on is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()


def test_light_actuator_number_is_bounded_to_px4_offboard_set() -> None:
    endpoint = FakeMAVLinkEndpoint()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
    )
    with pytest.raises(ValueError):
        MAVLinkPayloadController(adapter=adapter, light_actuator_number=0)
    with pytest.raises(ValueError):
        MAVLinkPayloadController(adapter=adapter, light_actuator_number=7)


@pytest.mark.asyncio
async def test_demo_speaker_never_claims_mavlink_ack() -> None:
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
