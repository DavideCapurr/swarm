from __future__ import annotations

import pytest
from pydantic import ValidationError

from swarm_core.payloads import PayloadAction, PayloadActionKind, PayloadMessage


def test_play_message_requires_catalogue_message() -> None:
    with pytest.raises(ValidationError):
        PayloadAction(agent_id="unit-001", kind=PayloadActionKind.PLAY_MESSAGE)


def test_non_message_action_rejects_message_id() -> None:
    with pytest.raises(ValidationError):
        PayloadAction(
            agent_id="unit-001",
            kind=PayloadActionKind.LIGHT_ON,
            message=PayloadMessage.RESTRICTED_AREA,
        )


def test_catalogue_message_is_valid_for_play_message() -> None:
    action = PayloadAction(
        agent_id="unit-001",
        kind=PayloadActionKind.PLAY_MESSAGE,
        message=PayloadMessage.RESTRICTED_AREA,
    )
    assert action.message is PayloadMessage.RESTRICTED_AREA
