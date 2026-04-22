import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket, accept: bool = True) -> None:
        if accept:
            await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            if channel in self._connections and websocket in self._connections[channel]:
                self._connections[channel].remove(websocket)
            if channel in self._connections and not self._connections[channel]:
                del self._connections[channel]

    async def broadcast(self, channel: str, payload: dict[str, Any]) -> bool:
        async with self._lock:
            sockets = list(self._connections.get(channel, set()))
        if not sockets:
            return False

        delivered = False
        stale: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_json(payload)
                delivered = True
            except Exception:
                stale.append(socket)

        if stale:
            async with self._lock:
                for socket in stale:
                    self._connections[channel].discard(socket)
        return delivered


ws_manager = WebSocketManager()
