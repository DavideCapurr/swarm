"""Vendor-neutral payload actions for SWARM-controlled physical response.

Flight and payload control are deliberately separate concerns. A DroneAdapter
continues to own navigation/autopilot integration, while an optional payload
controller may expose light, speaker, or future non-flight capabilities for the
same agent.

The domain vocabulary stays intentionally small. Vendor-specific details such
as MAVLink relay indexes never cross this boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid4().hex


class PayloadActionKind(str, Enum):
    LIGHT_ON = "light_on"
    LIGHT_OFF = "light_off"
    PLAY_MESSAGE = "play_message"
    STOP_MESSAGE = "stop_message"


class PayloadMessage(str, Enum):
    """Closed message catalogue.

    Free-form text is intentionally excluded from the control path. A real
    payload maps these stable IDs to pre-approved audio assets locally.
    """

    RESTRICTED_AREA = "restricted_area"


class PayloadExecutionMode(str, Enum):
    """How the action was executed, without overstating physical proof."""

    SIMULATED = "simulated"
    MAVLINK_ACK = "mavlink_ack"


class PayloadActionStatus(str, Enum):
    ACKNOWLEDGED = "acknowledged"
    SIMULATED = "simulated"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class PayloadAction(BaseModel):
    """One high-level action sent to a unit payload controller."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_new_id)
    agent_id: str
    kind: PayloadActionKind
    message: PayloadMessage | None = None
    ts: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _message_shape(self) -> PayloadAction:
        needs_message = self.kind is PayloadActionKind.PLAY_MESSAGE
        if needs_message and self.message is None:
            raise ValueError("PLAY_MESSAGE requires a catalogue message id")
        if not needs_message and self.message is not None:
            raise ValueError("message is only valid for PLAY_MESSAGE")
        return self


class PayloadActionResult(BaseModel):
    """Auditable result returned by a payload controller."""

    model_config = ConfigDict(extra="forbid")

    action_id: str
    agent_id: str
    kind: PayloadActionKind
    status: PayloadActionStatus
    execution_mode: PayloadExecutionMode
    light_on: bool = False
    speaker_active: bool = False
    message: PayloadMessage | None = None
    error_code: str | None = None
    ts: datetime = Field(default_factory=_now)
