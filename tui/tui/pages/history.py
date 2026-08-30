# -*- coding: utf-8 -*-
"""任务历史（Phase 1.4）：状态筛选 + 自动刷新列表。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, DataTable, RadioButton, RadioSet, Static
from tui.service_client import ServiceClient

STATUS_FILTERS = ["全部", "pending", "running", "success", "failed", "canceled"]


class HistoryPage(VerticalScroll):
    """任务历史：筛选/刷新/5s 自动轮询，数据来自 PostgreSQL。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__(id="page-history")
        self.client = client

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]任务历史[/bold cyan]  （5s 自动刷新）", id="his-title")
        yield RadioSet(
            *[RadioButton(label, value=(i == 0)) for i, label in enumerate(STATUS_FILTERS)],
            id="his-filter",
        )
        yield Button("🔄 立即刷新", id="his-refresh", variant="default")
        yield DataTable(id="his-table")

    def on_mount(self) -> None:
        table = self.query_one("#his-table", DataTable)
        table.add_columns("任务", "类型", "模式", "状态", "进度", "错误")
        table.cursor_type = "row"
        self.set_interval(5.0, self.refresh_table)
        self.run_worker(self.refresh_table(), exclusive=True)

    def _selected_status(self) -> str | None:
        selected = self.query_one("#his-filter", RadioSet).selected
        return None if selected == "全部" else selected

    async def refresh_table(self) -> None:
        if not self.is_mounted:
            return
        table = self.query_one("#his-table", DataTable)
        try:
            data = await self.client.list_tasks(page=1, status=self._selected_status())
        except Exception as exc:
            self.app.notify(f"任务列表加载失败: {exc}", severity="error")
            return
        table.clear()
        for task in (data or {}).get("items", []):
            table.add_row(
                task["task_uuid"][:8], task["task_type"], task["mode"],
                task["status"], f"{task['progress']}%",
                task.get("error_code") or "-",
            )

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "his-refresh":
            await self.refresh_table()

    async def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        await self.refresh_table()
