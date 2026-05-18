"""Phase 6.I — GDPR data-subject endpoints.

Two admin-mediated endpoints:

* ``POST /admin/export`` — Art. 15 access. Returns every row across
  ``operator_commands`` and ``events`` that references the targeted
  operator id. JSON only (no PDF — anti-overreach).
* ``POST /admin/forget`` — Art. 17 erasure. Rewrites
  ``operator_commands.operator_id`` to a deterministic pseudonym
  ``op-erased-<sha256_short>``. The audit row stays (Art. 17(3)(b)
  / (e)).

Both routes:

* Are gated by ``require_commander``, which also re-checks the
  ``mfa=true`` claim on every call.
* Validate ``operator_id`` shape against the same regex as the rest of
  the API (``backend.app.security.is_valid_operator_id``).
* Are rate-limited at 1/min/commander; abuse is auditable.
* Append a ``system`` audit event with the actor + the targeted id.
* Broadcast the audit event on the WebSocket hub so connected Consoles
  see the action in their timeline.

Voice constraint (§5.2): the audit body is in confidence-bound
language. The string "erasure" is not on the forbidden-words list; the
phrase "data export" is fine; "Intruder" / "Manual" / "alarm" /
"red-alert" / etc. are not used in any audit body emitted from this
module — see ``backend/tests/test_phase6i_compliance.py`` for the
voice-clean assertion.
"""

from __future__ import annotations

import hashlib
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import Event, EventKind

from backend.app.auth.deps import Principal, require_commander
from backend.app.db import get_repository
from backend.app.hub import HUB
from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import get_metrics
from backend.app.security import RateLimiter, is_valid_operator_id
from swarm_os import COORDINATOR

router = APIRouter(prefix="/admin")
logger = get_logger("backend.compliance")

# Dedicated 1/min/operator rate limiter — the export/erasure surface is
# narrow but the audit blast radius is high, so we throttle the same
# way as the emergency stop.
_compliance_limiter = RateLimiter(capacity=1, refill_per_s=1.0 / 60.0)

ERASURE_PHRASE = "ERASE OPERATOR DATA"
ERASED_PREFIX = "op-erased-"


def _pseudonymise(operator_id: str) -> str:
    """Deterministic pseudonym for an erased operator.

    SHA-256 over the original id, truncated to 16 hex chars. The full
    digest is not needed: the storage column is 64 chars, the prefix is
    11 chars, so 16 hex chars (64 bits) is plenty of collision
    resistance for the audit-row-rewriting purpose and leaves room in
    the column.
    """
    digest = hashlib.sha256(operator_id.encode("utf-8")).hexdigest()
    return f"{ERASED_PREFIX}{digest[:16]}"


class ExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    operator_id: str = Field(min_length=1, max_length=64)


class ForgetBody(BaseModel):
    """Double-confirmation envelope for the erasure call.

    The literal-typed ``confirm`` and ``confirmation_phrase`` mirror
    the Phase 6.G emergency stop: a captured request body can't be
    replayed without re-typing the phrase, and a missing ``confirm``
    fails fast at the pydantic layer.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    operator_id: str = Field(min_length=1, max_length=64)
    confirm: Literal[True]
    confirmation_phrase: str


def _require_valid_operator_id(value: str) -> None:
    if not is_valid_operator_id(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_operator_id",
        )


def _client_key(request: Request, principal: Principal) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{principal.operator_id}"


@router.post("/export", status_code=status.HTTP_200_OK)
async def export_operator_data(
    request: Request,
    body: ExportBody,
    principal: Annotated[Principal, Depends(require_commander)],
) -> dict[str, Any]:
    """Return a JSON snapshot of every persisted row for ``operator_id``.

    GDPR Art. 15 (right of access). The Console never calls this
    endpoint directly — the controller's DSAR procedure authenticates
    the subject out-of-band and the commander dispatches the call.

    Side effects: a ``system`` event "data export for op-xxx by op-yyy"
    is appended to the audit log and broadcast on the WS hub. The
    metric ``swarm_actions_total{action="data_export",outcome=...}`` is
    incremented.
    """
    _require_valid_operator_id(body.operator_id)
    metrics = get_metrics()
    if not await _compliance_limiter.allow(_client_key(request, principal)):
        metrics.actions_total.labels(
            action="data_export", outcome="rate_limited"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
        )

    payload = await get_repository().export_operator(body.operator_id)
    audit = Event(
        kind=EventKind.SYSTEM,
        body=(
            f"data export for {body.operator_id} by {principal.operator_id} "
            f"· {len(payload['operator_commands'])} command(s) "
            f"· {len(payload['events'])} event(s)"
        ),
    )
    COORDINATOR.state.append_event(audit)
    await HUB.broadcast({"kind": "event", "data": audit.model_dump(mode="json")})
    metrics.actions_total.labels(action="data_export", outcome="accepted").inc()
    logger.info(
        "data export served",
        subject=body.operator_id,
        actor=principal.operator_id,
        commands=len(payload["operator_commands"]),
        events=len(payload["events"]),
    )
    return {
        "subject": body.operator_id,
        "exported_at": audit.ts.isoformat(),
        "audit_event_id": audit.id,
        **payload,
    }


@router.post("/forget", status_code=status.HTTP_200_OK)
async def forget_operator_data(
    request: Request,
    body: ForgetBody,
    principal: Annotated[Principal, Depends(require_commander)],
) -> dict[str, Any]:
    """Anonymise every ``operator_commands`` row for ``operator_id``.

    GDPR Art. 17 (right to erasure) with Art. 17(3)(b)/(e) carve-out:
    the audit row stays for legal-obligation reasons; the
    identifying column is rewritten to ``op-erased-<sha256_short>``.

    Returns the count of rewritten rows + the pseudonym so the
    commander can correlate the audit trail. Idempotent: calling
    twice with the same subject yields a second call rewriting zero
    rows.

    Note: this endpoint does **not** remove the entry from
    ``infra/config/operators.yaml``. That step is performed in the
    same maintenance window via
    ``python -m backend.app.auth.cli`` so the operator-store rotation
    is a deliberate, separate action and not coupled to a data-subject
    request.
    """
    _require_valid_operator_id(body.operator_id)
    if body.confirmation_phrase != ERASURE_PHRASE:
        metrics = get_metrics()
        metrics.actions_total.labels(
            action="data_erasure", outcome="missing_confirmation"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="erasure_confirmation_required",
        )
    if body.operator_id.startswith(ERASED_PREFIX):
        # Defence in depth: don't let a previously-erased pseudonym
        # be re-anonymised — that would mask the audit trail.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="already_erased",
        )

    metrics = get_metrics()
    if not await _compliance_limiter.allow(_client_key(request, principal)):
        metrics.actions_total.labels(
            action="data_erasure", outcome="rate_limited"
        ).inc()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate_limited",
        )

    pseudonym = _pseudonymise(body.operator_id)
    rewritten = await get_repository().anonymize_operator(
        body.operator_id, pseudonym
    )
    audit = Event(
        kind=EventKind.SYSTEM,
        body=(
            f"data erasure for {body.operator_id} by {principal.operator_id} "
            f"· {rewritten} command(s) anonymised · pseudonym {pseudonym}"
        ),
    )
    COORDINATOR.state.append_event(audit)
    await HUB.broadcast({"kind": "event", "data": audit.model_dump(mode="json")})
    metrics.actions_total.labels(action="data_erasure", outcome="accepted").inc()
    logger.warning(
        "data erasure executed",
        subject=body.operator_id,
        actor=principal.operator_id,
        rewritten=rewritten,
        pseudonym=pseudonym,
    )
    return {
        "subject": body.operator_id,
        "pseudonym": pseudonym,
        "rewritten": rewritten,
        "audit_event_id": audit.id,
    }


__all__ = (
    "ERASED_PREFIX",
    "ERASURE_PHRASE",
    "_compliance_limiter",
    "_pseudonymise",
    "router",
)
