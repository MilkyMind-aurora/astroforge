# -*- coding: utf-8 -*-
"""流水线中心（Phase 5）：NovaFlow 模板列表 / 运行 / 自定义保存。"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option
from tui.service_client import ServiceClient


class PipelinePage(VerticalScroll):
    """流水线：模板选择运行 + YAML 保存为自定义模板。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__(id="page-pipeline")
        self.client = client
        self._pipelines: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("[bold cyan]流水线[/bold cyan]  NovaFlow 编排引擎", id="pl-title")
        yield Static("加载模板中…", id="pl-list-wrap")
        yield Button("▶ 运行所选流水线", id="pl-run", variant="primary")
        yield Static("", id="pl-result")
        yield Static("[bold]保存自定义模板[/bold]（粘贴流水线 YAML）", id="pl-save-title")
        yield TextArea(id="pl-yaml")
        yield Button("💾 保存模板", id="pl-save", variant="default")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_pipelines(), exclusive=True)

    async def refresh_pipelines(self) -> None:
        try:
            data = await self.client.list_pipelines()
        except Exception as exc:
            self.query_one("#pl-result", Static).update(f"[red]模板加载失败[/red] {exc}")
            return
        self._pipelines = (data or {}).get("items", [])
        option_list = OptionList(
            *[Option(
                f"{'🔧' if p['is_builtin'] else '⭐'} {p['title']}  "
                f"[dim]{p['name']} · {len(p['steps'])} 步[/dim]",
                id=p["name"],
            ) for p in self._pipelines],
            id="pl-list",
        )
        wrap = self.query_one("#pl-list-wrap", Static)
        await wrap.mount(option_list)
        wrap.update("")

    async def on_option_list_option_selected(self, event) -> None:  # noqa: ANN001
        pass  # 选中即高亮；运行走按钮

    def _selected_name(self) -> str | None:
        option_list = self.query_one("#pl-list", OptionList)
        if option_list.option_count == 0 or option_list.highlighted is None:
            return None
        return option_list.get_option_at_index(option_list.highlighted).id

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        result = self.query_one("#pl-result", Static)
        if event.button.id == "pl-run":
            name = self._selected_name()
            if not name:
                result.update("[red]❌ 请先选择流水线模板[/red]")
                return
            try:
                data = await self.client.run_pipeline(name)
            except Exception as exc:
                result.update(f"[red]运行失败[/red] {exc}")
                return
            result.update(
                f"[green]✅ 流水线已启动[/green] {data['task_uuid'][:8]}，"
                f"Ctrl+` 跟踪日志。"
            )
        elif event.button.id == "pl-save":
            yaml_text = self.query_one("#pl-yaml", TextArea).text
            try:
                data = await self.client.save_pipeline(yaml_text)
            except Exception as exc:
                result.update(f"[red]保存失败[/red] {exc}")
                return
            result.update(f"[green]✅ 模板已保存[/green] {data['name']}（已落 PostgreSQL）")
            await self.refresh_pipelines()
