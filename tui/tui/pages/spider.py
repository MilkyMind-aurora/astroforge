# -*- coding: utf-8 -*-
"""采集中心（Phase 2）：四类爬取任务真实表单 + 最近任务。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, RadioButton, RadioSet, Static
from tui.service_client import ServiceClient

TASK_TYPES = [
    ("spider_single", "单页转 Markdown"),
    ("spider_site", "整站结构化爬取"),
    ("spider_pdf", "PDF 批量下载"),
    ("spider_table", "表格抓取（Phase 2 开发中）"),
]


class SpiderPage(VerticalScroll):
    """采集中心：动态表单发起爬取任务，展示最近任务。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__(id="page-spider")
        self.client = client

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]采集中心[/bold cyan]  选择任务类型并填写参数", id="spider-title")
        yield RadioSet(
            *[RadioButton(label, value=(i == 0)) for i, (label_key, label) in
              enumerate(TASK_TYPES)],
            id="spider-type",
        )
        yield Input(placeholder="目标 URL（必填，https://…）", id="in-url")
        yield Input(placeholder="输出目录（默认 data/output/spider）", id="in-output")
        yield Input(placeholder="最大页面数（仅整站，默认 200）", id="in-max-pages")
        yield Input(placeholder="请求间隔秒（默认 1.0）", id="in-interval")
        yield Button("🚀 启动任务", id="btn-run", variant="primary")
        yield Static("", id="spider-result")
        yield Static("[bold]最近任务[/bold]  （加载中…）", id="spider-recent")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_recent(), exclusive=True)

    def _selected_type(self) -> str:
        selected = self.query_one("#spider-type", RadioSet).selected
        for key, label in TASK_TYPES:
            if label == selected:
                return key
        return "spider_single"

    async def refresh_recent(self) -> None:
        try:
            data = await self.client.list_tasks(page=1)
        except Exception as exc:
            self.query_one("#spider-recent", Static).update(f"[red]任务列表失败[/red] {exc}")
            return
        lines = ["[bold]最近任务[/bold]"]
        for task in (data or {}).get("items", [])[:5]:
            lines.append(
                f"  {task['task_uuid'][:8]}  {task['task_type']}  "
                f"[{task['status']}] 进度 {task['progress']}%"
            )
        self.query_one("#spider-recent", Static).update("\n".join(lines))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "btn-run":
            return
        result = self.query_one("#spider-result", Static)
        url = self.query_one("#in-url", Input).value.strip()
        if not url:
            result.update("[red]❌ URL 必填[/red]")
            return
        task_type = self._selected_type()
        config: dict = {"url": url}
        output = self.query_one("#in-output", Input).value.strip()
        if output:
            config["output_dir"] = output
        max_pages = self.query_one("#in-max-pages", Input).value.strip()
        if max_pages:
            config["max_pages"] = int(max_pages)
        interval = self.query_one("#in-interval", Input).value.strip()
        if interval:
            config["request_interval"] = float(interval)
        try:
            data = await self.client.create_task(task_type, config)
        except Exception as exc:
            result.update(f"[red]创建失败[/red] {exc}")
            return
        result.update(
            f"[green]✅ 任务已创建[/green] {data['task_uuid'][:8]}（状态 {data['status']}）"
            f"\nCtrl+` 打开日志面板可实时跟踪。"
        )
        await self.refresh_recent()
