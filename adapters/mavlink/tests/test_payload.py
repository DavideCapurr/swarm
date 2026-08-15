from __future__ import annotations

import pytest
from pymavlink import mavutil

from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.mavlink.adapter import MAVLinkAdapter
from adapters.mavlink.fake_endpoint import FakeMAVLinkEndpoint
from adapters.mavlink.payload import MAVLinkPayloadController


@pytest.mark.asyncio
async def test_light_command_uses_mavlink_relay_and_waits_for_ack() -> None:
    endpoint = FakeMAVLinkEndpoint()
    await endpoint.start()
    adapter = MAVLinkAdapter(
        agent_id="mav-1",
        connection=f"udpout:127.0.0.1:{endpoint.port}",
        heartbeat_timeout_s=10.0,
    )
    try:
        await adapter.connect()
        controller = MAVLinkPayloadController(adapter=adapter, light_relay_index=0)
        result = await controller.execute(
            PayloadAction(agent_id="mav-1", kind=PayloadActionKind.LIGHT_ON)
        )
        assert mavutil.mavlink.MAV_CMD_DO_SET_RELAY in endpoint.state.command_calls
        assert result.status is PayloadActionStatus.ACKNOWLEDGED
        assert result.execution_mode is PayloadExecutionMode.MAVLINK_ACK
        assert result.light_on is True
    finally:
        await adapter.disconnect()
        await endpoint.stop()


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
            light_relay_index=0,
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
        assert mavutil.mavlink.MAV_CMD_DO_SET_RELAY not in endpoint.state.command_calls
    finally:
        await adapter.disconnect()
        await endpoint.stop()
