"""Auth audit helpers — every login / refresh / revocation lands as a
``system`` Event in the SwarmOS event deque, broadcast on the WS hub, and
(when persistence is enabled) flushed to the DB by the bus consumer's
normal events path.

Bodies are confidence-bound and PII-free: the operator id is recorded,
the password and TOTP code are not.
"""

from __future__ import annotations

import contextlib
from typing import Literal

from swarm_core.messages import Event, EventKind

from backend.app.auth.store import OperatorRole
from backend.app.db import get_repository
from backend.app.hub import HUB
from swarm_os import COORDINATOR

AuthOutcome = Literal[
    "login_success",
    "login_failure",
    "refresh_success",
    "refresh_failure",
    "logout",
    "revoked",
]


def _format_body(
    *,
    operator_id: str,
    outcome: AuthOutcome,
    role: OperatorRole | None,
    reason: str | None,
) -> str:
    role_part = f" role={role.value}" if role is not None else ""
    reason_part = f" reason={reason}" if reason else ""
    return f"auth {outcome} operator={operator_id}{role_part}{reason_part}"


async def emit_auth_event(
    *,
    operator_id: str,
    outcome: AuthOutcome,
    role: OperatorRole | None = None,
    reason: str | None = None,
) -> Event:
    """Append an audit event to state, broadcast on WS, persist (best-effort).

    Returns the appended ``Event`` so the route can include the id in
    its response body when useful (e.g. a logout returning the audit row
    id helps tracing)."""

    body = _format_body(
        operator_id=operator_id, outcome=outcome, role=role, reason=reason
    )
    event = Event(kind=EventKind.SYSTEM, body=body)
    COORDINATOR.state.append_event(event)
    await HUB.broadcast({"kind": "event", "data": event.model_dump(mode="json")})
    with contextlib.suppress(Exception):  # pragma: no cover — repository swallows by design
        await get_repository().write_events([event])
    return event


__all__ = ("AuthOutcome", "emit_auth_event")
