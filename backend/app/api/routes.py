"""REST routes — thin wrappers around the in-memory state.

These endpoints feed the frontend's initial render. Live updates ride the
WebSocket (`/ws/telemetry`).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from backend.app.state import STATE

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "fleet_size": len(STATE.fleet),
        "anomaly_count": len(STATE.anomalies),
        "telemetry_agents": list(STATE.last_telemetry.keys()),
    }


@router.get("/fleet")
async def fleet() -> dict[str, Any]:
    return {"fleet": [fs.model_dump(mode="json") for fs in STATE.fleet.values()]}


@router.get("/anomalies")
async def anomalies() -> dict[str, Any]:
    return {
        "anomalies": [a.model_dump(mode="json") for a in STATE.anomalies.values()]
    }


@router.get("/telemetry/latest")
async def telemetry_latest() -> dict[str, Any]:
    return {
        "telemetry": {
            aid: t.model_dump(mode="json") for aid, t in STATE.last_telemetry.items()
        }
    }


@router.get("/events")
async def events(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, len(STATE.events) or 1))
    return {"events": list(STATE.events)[-limit:]}
