from __future__ import annotations

import pytest

from swarm_core.payloads import (
    PayloadAction,
    PayloadActionKind,
    PayloadActionStatus,
    PayloadExecutionMode,
    PayloadMessage,
)

from adapters.simulated.payload import SimulatedPayloadController


@pytest.mark.asyncio
async def test_simulated_payload_state_transitions_are_explicitly_simulated() -> None:
    controller = SimulatedPayloadController(agent_id="unit-001")

    light = await controller.execute(
        PayloadAction(agent_id="unit-001", kind=PayloadActionKind.LIGHT_ON)
    )
    assert light.light_on is True
    assert light.status is PayloadActionStatus.SIMULATED
    assert light.execution_mode is PayloadExecutionMode.SIMULATED

    speaker = await controller.execute(
        PayloadAction(
            agent_id="unit-001",
            kind=PayloadActionKind.PLAY_MESSAGE,
            message=PayloadMessage.RESTRICTED_AREA,
        )
    )
    assert speaker.light_on is True
    assert speaker.speaker_active is True
    assert speaker.message is PayloadMessage.RESTRICTED_AREA

    stopped = await controller.execute(
        PayloadAction(agent_id="unit-001", kind=PayloadActionKind.STOP_MESSAGE)
    )
    assert stopped.speaker_active is False
    assert stopped.message is None


@pytest.mark.asyncio
async def test_simulated_controller_rejects_cross_agent_action() -> None:
    controller = SimulatedPayloadController(agent_id="unit-001")
    with pytest.raises(ValueError):
        await controller.execute(
            PayloadAction(agent_id="unit-002", kind=PayloadActionKind.LIGHT_ON)
        )
