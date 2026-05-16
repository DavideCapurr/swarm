"""WebSocket fan-out hub for the operator dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from swarm_os import COORDINATOR

logger = logging.getLogger("backend.ws")


class WSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        for frame in await COORDINATOR.snapshot_frames():
            await ws.send_text(json.dumps(frame))
        logger.info("ws connect — %d clients", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("ws disconnect — %d clients", len(self._clients))

    async def broadcast(self, msg: dict[str, Any]) -> None:
        payload = json.dumps(msg)
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                await ws.send_text(payload)
            except (WebSocketDisconnect, RuntimeError):
                await self.disconnect(ws)
