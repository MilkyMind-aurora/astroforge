# -*- coding: utf-8 -*-
"""壳层后台服务循环（自 app.py 拆出，V1-B.3 壳收敛）：健康轮询 / WS 监控 /
运行任务数 / 外观持久化。以 Mixin 挂进 AstroForgeApp，行为与 MF1 一致。"""
from __future__ import annotations

import asyncio
import json
import time

from tui.service_client import get_client
from tui.shell.sidebar import Sidebar
from tui.theme.generated import tokens as design


class ServiceLoopsMixin:
    """App 生命周期内的轮询/订阅 worker（on_mount 由壳统一拉起）。"""

    async def _restore_appearance(self) -> None:
        """外观持久化（app_settings appearance.theme，V1-B.6；DB 不可达静默回落）。"""
        try:
            overrides = ((await get_client().list_app_settings()) or {}).get("items", {})
        except Exception:
            return
        saved = str((overrides.get("appearance.theme") or {}).get("value", "")).strip()
        if saved in design.THEMES and saved != self.theme:
            self.theme = saved  # refresh_css 热切，启动屏之后仍瞬时生效

    async def _persist_theme(self, name: str) -> None:
        try:
            await get_client().set_app_setting("appearance.theme", name)
        except Exception:
            pass  # 命令面板/快捷键路径静默；设置页路径会显式提示

    async def _health_loop(self) -> None:
        client = get_client()
        while True:
            try:
                self.health_data = await client.health()
                self.service_error = None
                summary = await client.env_check()
                self.env_items = list(summary.get("items", []))
                if not self._thresholds_loaded:
                    self._thresholds_loaded = True
                    await self._load_thresholds(client)
            except Exception as exc:
                self.service_error = str(exc)
            self._sync_health_ui()
            await asyncio.sleep(5.0)

    async def _load_thresholds(self, client) -> None:  # noqa: ANN001
        """内存阈值取 config-summary monitor 段（设置页可改，>warn 熔金 >crit nova）。"""
        try:
            summary = (await client.config_summary()) or {}
            monitor = summary.get("monitor", {})
            self.monitor_state["warn_gb"] = float(
                monitor.get("memory_warning_gb", self.monitor_state["warn_gb"]))
            self.monitor_state["crit_gb"] = float(
                monitor.get("memory_critical_gb", self.monitor_state["crit_gb"]))
        except Exception:
            pass  # 摘要不可用保留缺省 10/12GB

    def _sync_health_ui(self) -> None:
        try:
            self.query_one(Sidebar).set_health()
        except Exception:
            pass
        try:
            self.query_one("#page-home").render_state()
        except Exception:
            pass

    async def action_refresh_env(self) -> None:
        """命令面板「刷新体检」：单次拉取（§3.2 手动触发位）。"""
        client = get_client()
        try:
            self.health_data = await client.health()
            self.service_error = None
            summary = await client.env_check()
            self.env_items = list(summary.get("items", []))
            self.notify("体检已刷新", severity="information")
        except Exception as exc:
            self.service_error = str(exc)
            self.notify(f"刷新失败：{exc}", severity="error")
        self._sync_health_ui()

    async def _monitor_loop(self) -> None:
        """WS 监控通道（1s 采样；指数退避重连；心跳保活标记）。"""
        client = get_client()
        backoff = 1.0
        while True:
            try:
                ws = await client.subscribe_monitor()
                self.monitor_state["ws_connected"] = True
                backoff = 1.0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "monitor":
                        self.monitor_state.ingest(msg.get("payload") or {})
                    elif msg.get("type") == "heartbeat":
                        self.monitor_state["updated_at"] = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            self.monitor_state["ws_connected"] = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5.0)

    async def _running_loop(self) -> None:
        """运行中任务数（5s 轮询；状态栏与监控页共用 MonitorState）。"""
        client = get_client()
        while True:
            try:
                data = await client.list_tasks(page=1, status="running")
                self.monitor_state["running_count"] = len((data or {}).get("items") or [])
            except Exception:
                self.monitor_state["running_count"] = 0
            await asyncio.sleep(5.0)
