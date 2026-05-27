"""WebSocket fan-out hub for the operator dashboard."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from anyio import BrokenResourceError, ClosedResourceError
from fastapi import WebSocket, WebSocketDisconnect

from backend.app.observability.logging import get_logger
from backend.app.observability.metrics import get_metrics
from swarm_os import COORDINATOR

logger = get_logger("backend.ws")


class WSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, *, subprotocol: str | None = None) -> None:
        # `subprotocol` is set when the client used the `bearer, <jwt>`
        # negotiation path so Starlette echoes the chosen protocol back
        # in the handshake response.
        if subprotocol:
            await ws.accept(subprotocol=subprotocol)
        else:
            await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            count = len(self._clients)
        get_metrics().ws_clients.set(count)
        for frame in await COORDINATOR.snapshot_frames():
            await ws.send_text(json.dumps(frame))
        logger.info("ws connect", clients=count)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
            count = len(self._clients)
        get_metrics().ws_clients.set(count)
        logger.info("ws disconnect", clients=count)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        payload = json.dumps(msg)
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(payload)
            except (
                WebSocketDisconnect,
                RuntimeError,
                # `anyio.ClosedResourceError` / `BrokenResourceError` fire
                # when a peer's send stream has been torn down (e.g. the
                # ASGI transport for a TestClient that was closed in a
                # prior test, or a real socket that was reset). The hub
                # treats them like `WebSocketDisconnect` so one dead
                # client cannot break a fleet-wide broadcast.
                ClosedResourceError,
                BrokenResourceError,
            ):
                await self.disconnect(ws)
