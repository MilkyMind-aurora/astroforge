# -*- coding: utf-8 -*-
"""TUI 设置页（方案 1.3.3）：配置摘要 + 覆盖设置编辑 + token 重置。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Static
from tui.service_client import ServiceClient

EDITABLE = {
    "memory_warning_gb": "内存黄色预警 (GB)",
    "memory_critical_gb": "内存红色告警 (GB)",
    "request_interval": "爬虫请求间隔 (秒)",
    "default_template": "默认 DOCX 模板",
}


class SettingsPage(VerticalScroll):
    """真实设置页：读 config-summary + app-settings，支持阈值保存与 token 重置。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__(id="page-settings")
        self.client = client

    def compose(self) -> ComposeResult:
        yield Static("设置  正在加载…", id="settings-body")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_settings(), exclusive=True)

    async def refresh_settings(self) -> None:
        from textual.containers import Vertical

        try:
            summary = (await self.client.config_summary()) or {}
            overrides = ((await self.client.list_app_settings()) or {}).get("items", {})
        except Exception as exc:
            await self.mount(Static(f"[red]加载失败[/red] {exc}", id="settings-body"))
            return

        box = Vertical(id="settings-box")
        await self.mount(box)
        monitor = summary.get("monitor", {})
        lines = [
            "[bold cyan]设置[/bold cyan]",
            f"服务核心: {summary.get('service', {})}",
            f"数据库: {summary.get('database', {})}",
            f"AI: {summary.get('ai', {})}",
            f"监控: {monitor}",
            "",
            "[bold]覆盖设置（保存到 PostgreSQL app_settings）[/bold]",
        ]
        await box.mount(Static("\n".join(lines)))
        for key, label in EDITABLE.items():
            current = overrides.get(key, {}).get("value", monitor.get(key, ""))
            await box.mount(Input(value=str(current), placeholder=label, id=f"in-{key}"))
        await box.mount(Button("保存覆盖设置", id="btn-save", variant="primary"))
        await box.mount(Button("重置服务 Token（旧 token 立即失效）", id="btn-token", variant="warning"))
        self.query_one("#settings-body", Static).display = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            payload = {}
            for key in EDITABLE:
                raw = self.query_one(f"#in-{key}", Input).value.strip()
                if raw == "":
                    continue
                payload[key] = raw if key in {"default_template"} else float(raw)
            try:
                for key, val in payload.items():
                    await self.client.set_app_setting(key, val)
                self.app.notify("覆盖设置已保存", severity="information")
            except Exception as exc:
                self.app.notify(f"保存失败: {exc}", severity="error")
        elif event.button.id == "btn-token":
            try:
                await self.client.reset_token()
                # 重置后重新读取 token 文件

                self.client.__init__()  # 重新解析 token
                self.app.notify("Token 已重置并重新读取", severity="warning")
            except Exception as exc:
                self.app.notify(f"重置失败: {exc}", severity="error")
