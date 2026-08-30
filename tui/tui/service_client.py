# -*- coding: utf-8 -*-
"""Sidereal Core 服务客户端（TUI 薄客户端 SDK，方案 2.4 机制 10）。

token 读取优先级：环境变量 ASTROFORGE_SERVICE_TOKEN → 文件
（ASTROFORGE_TOKEN_FILE 指定，默认 ./data/service_token）。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8420"
_TOKEN_FILE = os.environ.get("ASTROFORGE_TOKEN_FILE", "./data/service_token")


class ServiceError(RuntimeError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _resolve_token() -> str:
    env_token = os.environ.get("ASTROFORGE_SERVICE_TOKEN")
    if env_token:
        return env_token
    token_file = Path(_TOKEN_FILE)
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()
    return ""


class ServiceClient:
    def __init__(self, base_url: str | None = None, token: str | None = None):
        self.base_url = (base_url or os.environ.get("ASTROFORGE_SERVICE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.token = token if token is not None else _resolve_token()

    def _headers(self) -> dict[str, str]:
        return {"X-AstroForge-Token": self.token} if self.token else {}

    async def _request(self, method: str, path: str, json_body: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.request(
                method, f"{self.base_url}{path}", json=json_body, headers=self._headers()
            )
        if resp.status_code == 401:
            raise ServiceError(2001, "未认证：token 缺失或失效（重置后需重新读取）")
        payload = resp.json()
        if payload.get("code") not in (0, None):
            raise ServiceError(payload.get("code", -1), payload.get("message", "unknown"))
        return payload.get("data")

    # ---- 常用端点 ----
    async def health(self) -> dict:
        return await self._request("GET", "/api/v1/system/health")

    async def env_check(self) -> dict:
        return await self._request("GET", "/api/v1/system/env-check")

    async def list_tasks(self, page: int = 1) -> dict:
        return await self._request("GET", f"/api/v1/tasks?page={page}")

    async def create_task(self, task_type: str, config: dict, title: str | None = None) -> dict:
        return await self._request(
            "POST", "/api/v1/tasks",
            {"task_type": task_type, "config": config, "title": title, "mode": "standalone"},
        )

    async def task_detail(self, task_uuid: str) -> dict:
        return await self._request("GET", f"/api/v1/tasks/{task_uuid}")

    # ---- Phase 1 收尾新增端点 ----
    async def list_app_settings(self) -> dict:
        return await self._request("GET", "/api/v1/app-settings")

    async def set_app_setting(self, key: str, value) -> dict:
        return await self._request("PUT", f"/api/v1/app-settings/{key}", {"value": value})

    async def config_summary(self) -> dict:
        return await self._request("GET", "/api/v1/system/config-summary")

    async def reset_token(self) -> dict:
        return await self._request("POST", "/api/v1/service/token/reset")

    async def running_task(self) -> dict | None:
        """最近一个运行中任务（日志面板订阅目标）。"""
        data = await self._request("GET", "/api/v1/tasks?status=running&page=1")
        items = (data or {}).get("items") or []
        return items[0] if items else None

    async def browse_files(self, path: str = "") -> dict:
        return await self._request("GET", f"/api/v1/files/browse?path={path}")

    async def preview_file(self, path: str) -> dict:
        return await self._request("GET", f"/api/v1/files/preview?path={path}")

    async def subscribe_logs(self, task_uuid: str):
        """连接 WS 日志通道，返回异步消息迭代器（websockets 库）。"""
        import websockets

        ws_url = f"{self.base_url.replace('http', 'ws')}/ws/logs/{task_uuid}?token={self.token}"
        return await websockets.connect(ws_url)


_client: ServiceClient | None = None


def get_client() -> ServiceClient:
    global _client
    if _client is None:
        _client = ServiceClient()
    return _client
