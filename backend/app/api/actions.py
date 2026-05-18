"""Operator intent endpoints.

Phase 6.C: the caller is identified by the JWT ``Principal`` produced by
``require_operator``; the transitional ``X-Operator-Id`` header is gone.
A viewer hitting any of these endpoints gets 403; an operator or
commander goes through.

Phase 3 mechanics are preserved: every accepted command flows through
``COORDINATOR.apply_command`` so the lifecycle states
(submitted → accepted → in_flight → completed) and the audit log live in
``state.commands``. The endpoint also broadcasts the resulting WS frames
so connected Consoles see the operator timeline update without waiting
for the next telemetry tick.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict
from swarm_core.messages import (
    CommandStatus,
    Event,
    EventKind,
    OperatorAction,
    OperatorCommand,
    RejectedReason,
)

from backend.app.auth.deps import Principal, require_commander, require_operator
from backend.app.db import get_repository
from backend.app.hub import HUB
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import get_metrics
from backend.app.security import RateLimiter
from swarm_os import COORDINATOR
from swarm_os.command_bus import EMERGENCY_FLEET_TARGET

router = APIRouter(prefix="/actions")
_limiter = RateLimiter()
# Phase 6.G — fleet-wide stop is heavily throttled per-operator so a stuck
# UI cannot spam the bus or hide a malicious replay. One per 60 s with no
# burst credit (capacity=1, refill 1/60 s).
_emergency_limiter = RateLimiter(capacity=1, refill_per_s=1.0 / 60.0)
EMERGENCY_CONFIRMATION = "RETURN ALL UNITS"
logger = get_logger("backend.actions")


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
    principal: Principal,
) -> tuple[dict[str, str | None], int]:
    metrics = get_metrics()
    if not await _limiter.allow(_client_key(request, principal.operator_id)):
        command = OperatorCommand(
            action=action,
            target=body.target,
            operator_id=principal.operator_id,
            rejected_reason=RejectedReason.RATE_LIMITED,
            status=CommandStatus.REJECTED,
        )
        # Rate-limited commands are still audited — operators need to see
        # the rejection in the timeline + auditors need to spot abuse.
        await get_repository().write_operator_command(command)
        metrics.actions_total.labels(action=action.value, outcome="rate_limited").inc()
        return {
            "command_id": command.id,
            "status": "rejected",
            "rejected_reason": RejectedReason.RATE_LIMITED.value,
        }, status.HTTP_429_TOO_MANY_REQUESTS

    command = OperatorCommand(
        action=action, target=body.target, operator_id=principal.operator_id
    )
    result, frames = await COORDINATOR.apply_command(command)
    for frame in frames:
        await HUB.broadcast(frame)
    stored = COORDINATOR.state.commands.get(command.id)
    if stored is not None:
        await get_repository().write_operator_command(stored)
    if result.rejected_reason is None:
        metrics.actions_total.labels(action=action.value, outcome="accepted").inc()
        code = status.HTTP_202_ACCEPTED
    else:
        metrics.actions_total.labels(
            action=action.value, outcome=result.rejected_reason.value
        ).inc()
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return result.as_response(), code


@router.post("/verify", status_code=status.HTTP_202_ACCEPTED)
async def verify(
    request: Request,
    response: Response,
    body: ActionBody,
    principal: Annotated[Principal, Depends(require_operator)],
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.VERIFY, body, principal)
    response.status_code = code
    return body_out


@router.post("/hold-patrol", status_code=status.HTTP_202_ACCEPTED)
async def hold_patrol(
    request: Request,
    response: Response,
    body: ActionBody,
    principal: Annotated[Principal, Depends(require_operator)],
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.HOLD_PATROL, body, principal)
    response.status_code = code
    return body_out


@router.post("/dismiss", status_code=status.HTTP_202_ACCEPTED)
async def dismiss(
    request: Request,
    response: Response,
    body: ActionBody,
    principal: Annotated[Principal, Depends(require_operator)],
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.DISMISS, body, principal)
    response.status_code = code
    return body_out


@router.post("/return", status_code=status.HTTP_202_ACCEPTED)
async def return_unit(
    request: Request,
    response: Response,
    body: ActionBody,
    principal: Annotated[Principal, Depends(require_operator)],
) -> dict[str, str | None]:
    body_out, code = await _dispatch(request, OperatorAction.RETURN, body, principal)
    response.status_code = code
    return body_out


# ── Phase 6.G — fleet-wide emergency RTL ──────────────────────────────────────


class EmergencyRtlAllBody(BaseModel):
    """Double-confirmation envelope for the fleet-wide stop.

    Both fields are mandatory:
      * ``confirm`` is a literal ``True`` (the boolean — fails on string
        coercion under ``strict=True``).
      * ``confirmation_phrase`` must equal the literal string
        ``RETURN ALL UNITS``. Adding a phrase guards against accidental
        replay of a captured request body — the operator has to type the
        words in the modal.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    confirm: Literal[True]
    confirmation_phrase: str


@router.post(
    "/emergency-rtl-all",
    status_code=status.HTTP_202_ACCEPTED,
)
async def emergency_rtl_all(
    request: Request,
    response: Response,
    body: EmergencyRtlAllBody,
    principal: Annotated[Principal, Depends(require_commander)],
) -> dict[str, str | None]:
    """Order RTL for every airborne unit.

    Requires the JWT ``commander`` role *with* a satisfied MFA bit (the
    ``require_commander`` dependency enforces both) and a double
    confirmation in the body. The handler is its own micro-pipeline so
    the audit footprint is unambiguous:

      1. The exact confirmation phrase must be present in the body. If
         not, the request is logged as a 400 with no command record.
      2. A dedicated 1/min/operator rate limiter throttles the route;
         when it trips, the command is still audited with a
         ``RATE_LIMITED`` rejection so abuse is visible.
      3. The command is dispatched through the coordinator like any
         other operator intent, but the safety-policy gate is bypassed
         on purpose (a low battery is *why* we're stopping the fleet).
      4. A ``system`` Event tagged ``emergency_rtl_all`` is appended to
         the audit log and broadcast on WS so every Console renders the
         state change immediately.
    """

    metrics = get_metrics()
    if body.confirmation_phrase != EMERGENCY_CONFIRMATION:
        metrics.actions_total.labels(
            action=OperatorAction.EMERGENCY_RTL_ALL.value,
            outcome="missing_confirmation",
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="emergency_confirmation_required",
        )

    if not await _emergency_limiter.allow(principal.operator_id):
        command = OperatorCommand(
            action=OperatorAction.EMERGENCY_RTL_ALL,
            target=EMERGENCY_FLEET_TARGET,
            operator_id=principal.operator_id,
            status=CommandStatus.REJECTED,
            rejected_reason=RejectedReason.RATE_LIMITED,
        )
        await get_repository().write_operator_command(command)
        metrics.actions_total.labels(
            action=OperatorAction.EMERGENCY_RTL_ALL.value, outcome="rate_limited"
        ).inc()
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return {
            "command_id": command.id,
            "status": "rejected",
            "rejected_reason": RejectedReason.RATE_LIMITED.value,
        }

    command = OperatorCommand(
        action=OperatorAction.EMERGENCY_RTL_ALL,
        target=EMERGENCY_FLEET_TARGET,
        operator_id=principal.operator_id,
    )
    result, frames = await COORDINATOR.apply_command(command)
    stored = COORDINATOR.state.commands.get(command.id)
    if stored is not None:
        await get_repository().write_operator_command(stored)

    spawned = [
        mid
        for mid in COORDINATOR.state.missions
        if mid.startswith("emergency-rtl-")
    ]
    audit = Event(
        kind=EventKind.SYSTEM,
        body=(
            f"emergency rtl all triggered by {principal.operator_id} · "
            f"{len(spawned)} unit(s) returning · safety policy bypassed"
        ),
        action_label=None,
    )
    COORDINATOR.state.append_event(audit)
    frames.append({"kind": "event", "data": audit.model_dump(mode="json")})
    for frame in frames:
        await HUB.broadcast(frame)
    logger.warning(
        "emergency rtl all",
        operator=principal.operator_id,
        spawned_missions=len(spawned),
        command_id=command.id,
    )

    if result.rejected_reason is None:
        metrics.actions_total.labels(
            action=OperatorAction.EMERGENCY_RTL_ALL.value, outcome="accepted"
        ).inc()
        code = status.HTTP_202_ACCEPTED
    else:
        metrics.actions_total.labels(
            action=OperatorAction.EMERGENCY_RTL_ALL.value,
            outcome=result.rejected_reason.value,
        ).inc()
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    response.status_code = code
    return result.as_response()
