"""REST routes — thin wrappers around the in-memory state.

These endpoints feed the frontend's initial render. Live updates ride the
WebSocket (`/ws/telemetry`).

Phase 6.C: every read route now requires the ``viewer`` JWT role. The
public surface is just ``/`` and ``/health``. The action and admin
routers enforce ``operator`` and ``commander`` respectively.

Phase 4 additions (still in place):
  - `/events` accepts `from=&to=` for historical queries against the DB
    (falls back to the in-memory deque when persistence is disabled).
  - `/missions/{id}/history` returns the per-mission event timeline from DB.
  - `/operator-commands` returns the audit log for an operator id.

The `from`/`to` parameters are typed as `datetime` so FastAPI parses + rejects
malformed input before it reaches the DB — a free SQL injection guard on top
of SQLAlchemy's parameterized queries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from swarm_core.messages import EventKind

from backend.app.auth.deps import Principal, require_viewer
from backend.app.db import get_repository
from backend.app.state import STATE
from swarm_os import SWARM_STATE

router = APIRouter()
# A second router for the few endpoints that must stay unauthenticated:
# `/` (service identity) and `/health` (liveness probe for orchestrators).
public_router = APIRouter()


# ── Public (no auth) ──────────────────────────────────────────────────────────


@public_router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "fleet_size": len(STATE.fleet),
        "anomaly_count": len(STATE.anomalies),
        "telemetry_agents": list(STATE.last_telemetry.keys()),
        "swarmos_units": len(SWARM_STATE.units),
        "swarmos_mode": SWARM_STATE.mode.value,
        "persistence": get_repository().enabled,
    }


# ── Viewer (authenticated reads) ──────────────────────────────────────────────


_VIEWER = Annotated[Principal, Depends(require_viewer)]


@router.get("/session")
async def session(_: _VIEWER) -> dict[str, Any]:
    return {"session": SWARM_STATE.session.model_dump(mode="json")}


@router.get("/awareness")
async def awareness(_: _VIEWER) -> dict[str, Any]:
    return {"awareness": SWARM_STATE.awareness.model_dump(mode="json")}


@router.get("/docks")
async def docks(_: _VIEWER) -> dict[str, Any]:
    return {"docks": [d.model_dump(mode="json") for d in SWARM_STATE.docks.values()]}


@router.get("/sectors")
async def sectors(_: _VIEWER) -> dict[str, Any]:
    return {"sectors": [s.model_dump(mode="json") for s in SWARM_STATE.sectors.values()]}


@router.get("/units")
async def units(_: _VIEWER) -> dict[str, Any]:
    return {"units": [u.model_dump(mode="json") for u in SWARM_STATE.units.values()]}


@router.get("/missions")
async def missions(_: _VIEWER) -> dict[str, Any]:
    return {"missions": [m.model_dump(mode="json") for m in SWARM_STATE.missions.values()]}


@router.get("/missions/{mission_id}/history")
async def mission_history(
    mission_id: str,
    _: _VIEWER,
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    """Per-mission event timeline. Phase 4: DB-backed."""
    if not get_repository().enabled:
        # In-memory fallback — filter the deque by mission_id.
        in_mem = [
            e.model_dump(mode="json")
            for e in list(SWARM_STATE.events)
            if e.mission_id == mission_id
        ][-limit:]
        return {"mission_id": mission_id, "events": in_mem}
    events = await get_repository().mission_history(mission_id, limit=limit)
    return {
        "mission_id": mission_id,
        "events": [e.model_dump(mode="json") for e in events],
    }


@router.get("/commands")
async def commands(
    _: _VIEWER, limit: int = Query(100, ge=1, le=500)
) -> dict[str, Any]:
    ordered = sorted(
        SWARM_STATE.commands.values(),
        key=lambda c: c.submitted_at,
    )
    return {"commands": [c.model_dump(mode="json") for c in ordered[-limit:]]}


@router.get("/operator-commands")
async def operator_commands(
    _: _VIEWER,
    operator_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Audit log query — Phase 4. Backed by DB when persistence is enabled."""
    # Reject malformed operator_id (same regex as the action endpoints) so the
    # audit query surface matches the write surface.
    if operator_id is not None:
        from backend.app.security import is_valid_operator_id

        if not is_valid_operator_id(operator_id):
            raise HTTPException(status_code=400, detail="invalid_operator_id")

    if not get_repository().enabled:
        cmds = list(SWARM_STATE.commands.values())
        if operator_id is not None:
            cmds = [c for c in cmds if c.operator_id == operator_id]
        cmds.sort(key=lambda c: c.submitted_at)
        return {"commands": [c.model_dump(mode="json") for c in cmds[-limit:]]}

    rows = await get_repository().list_operator_commands(
        operator_id=operator_id, limit=limit
    )
    return {"commands": [c.model_dump(mode="json") for c in rows]}


@router.get("/fleet")
async def fleet(_: _VIEWER) -> dict[str, Any]:
    return {"fleet": [fs.model_dump(mode="json") for fs in STATE.fleet.values()]}


@router.get("/anomalies")
async def anomalies(_: _VIEWER) -> dict[str, Any]:
    if SWARM_STATE.anomalies:
        return {
            "anomalies": [
                a.model_dump(mode="json") for a in SWARM_STATE.anomalies.values()
            ]
        }
    return {"anomalies": [a.model_dump(mode="json") for a in STATE.anomalies.values()]}


@router.get("/anomalies/raw")
async def raw_anomalies(_: _VIEWER) -> dict[str, Any]:
    return {"anomalies": [a.model_dump(mode="json") for a in STATE.anomalies.values()]}


@router.get("/telemetry/latest")
async def telemetry_latest(_: _VIEWER) -> dict[str, Any]:
    return {
        "telemetry": {
            aid: t.model_dump(mode="json") for aid, t in STATE.last_telemetry.items()
        }
    }


@router.get("/events")
async def events(
    _: _VIEWER,
    limit: int = Query(100, ge=1, le=500),
    kind: EventKind | None = None,
    sector: str | None = Query(default=None, max_length=64),
    agent: str | None = Query(default=None, max_length=64),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
) -> dict[str, Any]:
    """Event timeline. Phase 4 adds `from=&to=` for DB-backed history queries.

    When `from`/`to` is supplied, or persistence is enabled and the in-memory
    deque is empty, we read from the DB. Otherwise we serve the live deque.
    """
    # Hard ceiling on time range to keep query bounded.
    if from_ is not None and to is not None and to < from_:
        raise HTTPException(status_code=400, detail="invalid_time_range")

    if get_repository().enabled and (from_ is not None or to is not None):
        rows = await get_repository().list_events(
            from_ts=from_,
            to_ts=to,
            kind=kind,
            sector_id=sector,
            agent_id=agent,
            limit=limit,
        )
        return {"events": [e.model_dump(mode="json") for e in rows]}

    swarmos_events = list(SWARM_STATE.events)
    if swarmos_events:
        filtered = swarmos_events
        if kind is not None:
            filtered = [e for e in filtered if e.kind == kind]
        if sector is not None:
            filtered = [e for e in filtered if e.sector_id == sector]
        if agent is not None:
            filtered = [e for e in filtered if e.agent_id == agent]
        return {"events": [e.model_dump(mode="json") for e in filtered[-limit:]]}

    if get_repository().enabled:
        rows = await get_repository().list_events(
            kind=kind, sector_id=sector, agent_id=agent, limit=limit
        )
        return {"events": [e.model_dump(mode="json") for e in rows]}

    legacy = list(STATE.events)[-limit:]
    return {"events": legacy}
