"""Admin endpoints — hot reload of site config + audit.

Phase 6.B shipped this surface with a transitional ``X-Admin-Token``
header gate; Phase 6.C replaced it with the JWT ``commander`` role,
which already enforces MFA at login time. See ``backend/app/auth/``
for the issuer and the ``Principal`` model.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from swarm_core.messages import Event, EventKind

from backend.app.auth.deps import Principal, require_commander
from backend.app.hub import HUB
from backend.app.observability.logging import get_logger
from swarm_os import COORDINATOR
from swarm_os.policy import PolicyEngine
from swarm_os.sectors import default_sector_grid
from swarm_os.sites import (
    DEFAULT_SITE_ID,
    SiteConfigNotFound,
    load_site_config,
)

logger = get_logger("backend.admin")

router = APIRouter(prefix="/admin")


class ReloadBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    site_id: str = Field(
        DEFAULT_SITE_ID,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9-]{0,62}[a-z0-9]$",
    )


@router.post("/reload-site-config", status_code=status.HTTP_200_OK)
async def reload_site_config(
    body: ReloadBody,
    principal: Annotated[Principal, Depends(require_commander)],
) -> dict[str, Any]:
    """Reload the policy + topology for a site without restarting the backend.

    Requires the JWT ``commander`` role *with* a satisfied MFA bit; the
    ``require_commander`` dependency enforces both. Side effects on
    success mirror Phase 6.B: swap the policy engine, rebuild the sector
    grid if the centre moved, update the session site_id, append a
    ``system`` Event to the audit log, broadcast it on WS.

    Operator-facing rejections (404 unknown site, 422 validation) leave
    state untouched. The whole sequence runs under `state.lock` so
    in-flight `apply_*` paths see either the old config or the new one,
    never a mix.
    """

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
            body=(
                f"site config reloaded: {previous_site_id} -> "
                f"{new_config.site_id} (by {principal.operator_id})"
            ),
        )
        state.append_event(event)

    await HUB.broadcast({"kind": "event", "data": event.model_dump(mode="json")})
    logger.info(
        "site config reloaded",
        previous=previous_site_id,
        current=new_config.site_id,
        operator=principal.operator_id,
    )
    return {
        "status": "ok",
        "previous_site_id": previous_site_id,
        "site_id": new_config.site_id,
        "event_id": event.id,
    }
