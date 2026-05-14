"""FastAPI entrypoint for SWARM OS backend.

Run: `uvicorn backend.app.main:app --reload`
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router as api_router
from backend.app.bus_consumer import BusConsumer
from backend.app.ws.telemetry import WSHub

logger = logging.getLogger("backend")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

hub = WSHub()
bus_consumer = BusConsumer(hub)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    await bus_consumer.start()
    logger.info("backend ready")
    try:
        yield
    finally:
        await bus_consumer.stop()


app = FastAPI(title="SWARM OS Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket) -> None:
    await hub.connect(websocket)
    # Push a hello frame and the current snapshot so the client can confirm the
    # link is alive even before the bus emits its next event.
    try:
        import json as _json
        from backend.app.state import STATE

        await websocket.send_text(_json.dumps({"kind": "hello", "data": {}}))
        for fs in STATE.fleet.values():
            await websocket.send_text(
                _json.dumps({"kind": "fleet", "data": _json.loads(fs.model_dump_json())})
            )
        for t in STATE.last_telemetry.values():
            await websocket.send_text(
                _json.dumps({"kind": "telemetry", "data": _json.loads(t.model_dump_json())})
            )
    except Exception:
        pass

    try:
        while True:
            # We don't expect inbound messages in commit 1 — just keep the socket alive.
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        await hub.disconnect(websocket)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "swarm-os-backend", "version": "0.1.0"}
