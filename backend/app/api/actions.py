"""Operator intent endpoints.

Phase 3: every accepted command now flows through `COORDINATOR.apply_command`
so the lifecycle states (submitted → accepted → in_flight → completed) and
the audit log live in `state.commands`. The endpoint also broadcasts the
resulting WS frames so connected Consoles see the operator timeline update
without waiting for the next telemetry tick.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from swarm_core.messages import (
    CommandStatus,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
)

from backend.app.db import get_repository
from backend.app.hub import HUB
from backend.app.security import RateLimiter, is_valid_operator_id
from swarm_os import COORDINATOR

router = APIRouter(prefix="/actions")
_limiter = RateLimiter()


class ActionBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    target: str


def _client_key(request: Request, operator_id: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{operator_id}"


async def _dispatch(
    request: Request,
    action: OperatorAction,
    body: ActionBody,
    operator_id: str | None,
) -> tuple[dict[str, str | None], int]:
    if not is_valid_operator_id(operator_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_operator_id")
    assert operator_id is not None

    if not await _limiter.allow(_client_key(request, operator_id)):
        command = OperatorCommand(
            action=action,
            target=body.target,
            operator_id=operator_id,
            rejected_reason=RejectedReason.RATE_LIMITED,
            status=CommandStatus.REJECTED,
        )
        # Rate-limited commands are still audited — operators need to see
        # the rejection in the timeline + auditors need to spot abuse.
        await get_repository().write_operator_command(command)
        return {
            "command_id": command.id,
            "status": "rejected",
            "rejected_reason": RejectedReason.RATE_LIMITED.value,
        }, status.HTTP_429_TOO_MANY_REQUESTS

    command = OperatorCommand(action=action, target=body.target, operator_id=operator_id)
    result, frames = await COORDINATOR.apply_command(command)
    for frame in frames:
        await HUB.broadcast(frame)
    stored = COORDINATOR.state.commands.get(command.id)
    if stored is not None:
        await get_repository().write_operator_command(stored)
    code = (
        status.HTTP_202_ACCEPTED
        if result.rejected_reason is None
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    return result.as_response(), code


@router.post("/verify", status_code=status.HTTP_202_ACCEPTED)
async def verify(
    request: Request,
    response: Response,
    body: ActionBody,
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.VERIFY, body, x_operator_id)
    response.status_code = code
    return body_out


@router.post("/hold-patrol", status_code=status.HTTP_202_ACCEPTED)
async def hold_patrol(
    request: Request,
    response: Response,
    body: ActionBody,
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.HOLD_PATROL, body, x_operator_id)
    response.status_code = code
    return body_out


@router.post("/dismiss", status_code=status.HTTP_202_ACCEPTED)
async def dismiss(
    request: Request,
    response: Response,
    body: ActionBody,
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.DISMISS, body, x_operator_id)
    response.status_code = code
    return body_out


@router.post("/return", status_code=status.HTTP_202_ACCEPTED)
async def return_unit(
    request: Request,
    response: Response,
    body: ActionBody,
    x_operator_id: Annotated[str | None, Header(alias="X-Operator-Id")] = None,
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.RETURN, body, x_operator_id)
    response.status_code = code
    return body_out
