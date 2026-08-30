"""WebSocket 三通道枢纽（方案 2.4 机制 11）。

通道：/ws/monitor、/ws/logs/{task_uuid}、/ws/ai
消息信封：{"type": "...", "payload": {...}, "ts": ISO8601}
服务端每 30s 发送 heartbeat；断连由客户端按指数退避重连。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket

from astroforge.utils.logger import get_logger

log = get_logger("astroforge.ws")

HEARTBEAT_SECONDS = 30


class WSHub:
    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._channels.setdefault(channel, set()).add(websocket)
        log.info("WS 接入: %s（当前 %d 连接）", channel, len(self._channels[channel]))

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._channels.get(channel)
            if connections and websocket in connections:
                connections.discard(websocket)
                if not connections:
                    self._channels.pop(channel, None)

    @staticmethod
    def _envelope(msg_type: str, payload: Any) -> str:
        return json.dumps(
            {
                "type": msg_type,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        )

    async def broadcast(self, channel: str, msg_type: str, payload: Any) -> None:
        message = self._envelope(msg_type, payload)
        async with self._lock:
            targets = list(self._channels.get(channel, ()))
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(channel, ws)

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            async with self._lock:
                channels = {name: list(conns) for name, conns in self._channels.items() if conns}
            for channel, conns in channels.items():
                for ws in conns:
                    with contextlib.suppress(Exception):
                        await ws.send_text(self._envelope("heartbeat", {}))

    def start_heartbeat(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
