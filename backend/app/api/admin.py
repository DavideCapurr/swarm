"""Phase 6.B admin endpoints — hot reload of site config + audit.

This module owns operator-out-of-band actions: today, just the policy
hot reload. The endpoints are gated by `SWARM_ADMIN_TOKEN` env var via
the `X-Admin-Token` header; if the env var is unset the entire admin
surface returns 503, so a misconfigured deploy fails closed.

The 6.C RBAC pass replaces this header gate with a JWT `commander`
scope; until then this is the transitional shim. The drone-day
checklist (§2.C) tracks the JWT migration.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import Event, EventKind

from backend.app.hub import HUB
from swarm_os import COORDINATOR
from swarm_os.policy import PolicyEngine
from swarm_os.sectors import default_sector_grid
from swarm_os.sites import (
    DEFAULT_SITE_ID,
    SiteConfigNotFound,
    load_site_config,
)

logger = logging.getLogger("backend.admin")

ADMIN_TOKEN_ENV = "SWARM_ADMIN_TOKEN"  # transitional Phase 6.B gate
ADMIN_TOKEN_HEADER = "X-Admin-Token"

router = APIRouter(prefix="/admin")


class ReloadBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    site_id: str = Field(
        DEFAULT_SITE_ID,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$",
    )


def _require_admin_token(token: str | None) -> None:
    """Enforce the env-driven token gate. Unset env → 503 (admin disabled)."""

    configured = os.environ.get(ADMIN_TOKEN_ENV)
    if configured is None or configured == "":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="admin_disabled",
        )
    if not token or token != configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_admin_token",
        )


@router.post("/reload-site-config", status_code=status.HTTP_200_OK)
async def reload_site_config(
    body: ReloadBody,
    x_admin_token: Annotated[str | None, Header(alias=ADMIN_TOKEN_HEADER)] = None,
) -> dict[str, Any]:
    """Reload the policy + topology for a site without restarting the backend.

    Side effects on success:
      - swap `state.policy` to a `PolicyEngine` bound to the new SiteConfig
        (preserving the existing WeatherProvider binding so an upgraded
        provider doesn't regress to the stub);
      - rebuild `state.sectors` if the site centre moved;
      - update `session.site_id`;
      - append a `system` Event to the audit log and broadcast it on WS.

    Operator-facing rejections (404 unknown site, 422 validation) leave
    state untouched. The whole sequence runs under `state.lock` so
    in-flight `apply_*` paths see either the old config or the new one,
    never a mix.
    """

    _require_admin_token(x_admin_token)
    state = COORDINATOR.state
    try:
        new_config = load_site_config(body.site_id)
    except SiteConfigNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="site_config_not_found",
        ) from exc

    async with state.lock:
        previous_site_id = state.session.site_id
        previous_provider = state.policy.weather_provider
        state.policy = PolicyEngine(new_config, previous_provider)
        state.session = state.session.model_copy(
            update={"site_id": new_config.site_id}
        )
        # Rebuild the sector grid if the centre genuinely moved; preserve
        # the existing one when it's the same site to keep history intact.
        if new_config.site_id != previous_site_id:
            state.sectors = {
                s.id: s for s in default_sector_grid(new_config.center)
            }
        event = Event(
            kind=EventKind.SYSTEM,
            body=f"site config reloaded: {previous_site_id} -> {new_config.site_id}",
        )
        state.append_event(event)

    await HUB.broadcast({"kind": "event", "data": event.model_dump(mode="json")})
    logger.info(
        "site config reloaded",
        extra={"previous": previous_site_id, "current": new_config.site_id},
    )
    return {
        "status": "ok",
        "previous_site_id": previous_site_id,
        "site_id": new_config.site_id,
        "event_id": event.id,
    }
