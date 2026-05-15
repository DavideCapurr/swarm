"""REST routes — thin wrappers around the in-memory state.

These endpoints feed the frontend's initial render. Live updates ride the
WebSocket (`/ws/telemetry`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from swarm_core.messages import EventKind

from backend.app.state import STATE
from swarm_os import SWARM_STATE

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "fleet_size": len(STATE.fleet),
        "anomaly_count": len(STATE.anomalies),
        "telemetry_agents": list(STATE.last_telemetry.keys()),
        "swarmos_units": len(SWARM_STATE.units),
        "swarmos_mode": SWARM_STATE.mode.value,
    }


@router.get("/session")
async def session() -> dict[str, Any]:
    return {"session": SWARM_STATE.session.model_dump(mode="json")}


@router.get("/awareness")
async def awareness() -> dict[str, Any]:
    return {"awareness": SWARM_STATE.awareness.model_dump(mode="json")}


@router.get("/docks")
async def docks() -> dict[str, Any]:
    return {"docks": [d.model_dump(mode="json") for d in SWARM_STATE.docks.values()]}


@router.get("/sectors")
async def sectors() -> dict[str, Any]:
    return {"sectors": [s.model_dump(mode="json") for s in SWARM_STATE.sectors.values()]}


@router.get("/units")
async def units() -> dict[str, Any]:
    return {"units": [u.model_dump(mode="json") for u in SWARM_STATE.units.values()]}


@router.get("/missions")
async def missions() -> dict[str, Any]:
    return {"missions": [m.model_dump(mode="json") for m in SWARM_STATE.missions.values()]}


@router.get("/fleet")
async def fleet() -> dict[str, Any]:
    return {"fleet": [fs.model_dump(mode="json") for fs in STATE.fleet.values()]}


@router.get("/anomalies")
async def anomalies() -> dict[str, Any]:
    if SWARM_STATE.anomalies:
        return {
            "anomalies": [
                a.model_dump(mode="json") for a in SWARM_STATE.anomalies.values()
            ]
        }
    return {"anomalies": [a.model_dump(mode="json") for a in STATE.anomalies.values()]}


@router.get("/anomalies/raw")
async def raw_anomalies() -> dict[str, Any]:
    return {"anomalies": [a.model_dump(mode="json") for a in STATE.anomalies.values()]}


@router.get("/telemetry/latest")
async def telemetry_latest() -> dict[str, Any]:
    return {
        "telemetry": {
            aid: t.model_dump(mode="json") for aid, t in STATE.last_telemetry.items()
        }
    }


@router.get("/events")
async def events(
    limit: int = Query(100, ge=1, le=500),
    kind: EventKind | None = None,
    sector: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
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

    legacy = list(STATE.events)[-limit:]
    return {"events": legacy}
