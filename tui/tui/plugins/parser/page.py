# -*- coding: utf-8 -*-
"""解析中心（方案 §3.3 表单卡族，MF2 挂共用任务进度卡）。

- MinerU / WPD 两 Tab（RadioSet 胶囊 + 液态指示条语义）
- 文件路径输入 + F 键文件浏览器联动回填；输出目录预览行实时跟随
- MinerU 参数：max_threads（防 ONNX/BLAS 抢核；CLI 当前后端固定 pipeline，
  backend 参数待模块 CLI 扩展后接入——如实注明，不伪造选项）
- WPD 参数：坐标轴手动修正开关（axis 四值）+ append_to_md 开关
数据契约：POST /tasks → 提交后下半区挂 TaskProgressCard（WS progress 事件）。
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Input, RadioButton, RadioSet, Static, Switch

from tui.components.task_card import TaskProgressCard
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

MINERU_TAB, WPD_TAB = "MinerU 文档解析", "WPD 图表数值提取"
_AXIS_KEYS = ("x_min", "x_max", "y_min", "y_max")


class ParserPage(VerticalScroll):
    """解析中心：MinerU / WPD 双 Tab 表单 + 任务进度卡。"""

    BINDINGS = [Binding("f", "pick_path", "选路径")]

    CSS = """
    #par-form { border: round $border-subtle; background: $card; padding: 0 2;
        margin-top: 1; }
    #par-title { color: $ink-900; margin-top: 1; }
    #par-form Input { background: $sunken; border: round $border-subtle; }
    #par-form Input:focus { border: round $border-active; }
    #par-run { width: 100%; margin-top: 1; }
    .par-axis-input { margin-bottom: 0; }
    #par-out-preview { color: $ink-400; margin-top: 1; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-parser")
        self.client = client
        self._app = app_ref
        self._tab = MINERU_TAB
        self._task_uuid: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.parser')} 解析中心[/b]"
            f"  [dim]MinerU 文档解析 · WebPlotDigitizer 图表提值[/dim]",
            id="par-title", classes="page-body",
        )
        with Vertical(id="par-form"):
            yield RadioSet(
                RadioButton(MINERU_TAB, value=True),
                RadioButton(WPD_TAB),
                id="par-tab",
            )
            yield Input(placeholder="输入路径（PDF/图片/目录，必填；F 打开文件浏览器）",
                        id="par-input")
            yield Input(placeholder="线程上限（MinerU 默认 4，防 ONNX/BLAS 抢核）",
                        id="par-threads")
            yield Static("坐标轴手动修正（WPD，不开则自动检测）", id="par-axis-label")
            yield Switch(value=False, id="par-axis-switch")
            for key in _AXIS_KEYS:
                yield Input(placeholder=f"axis.{key}（数值，可选）",
                            id=f"par-axis-{key}", classes="par-axis-input")
            yield Static("结果追加到同名 Markdown（WPD append_to_md）",
                         id="par-append-label", classes="page-body")
            yield Switch(value=False, id="par-append")
            yield Static("[dim]输出目录：填写输入后显示[/dim]", id="par-out-preview")
            yield Button("启动解析任务", id="par-run", variant="primary")
        yield Static("", id="par-result")

    def on_mount(self) -> None:
        self._sync_tab()

    # ---- Tab 切换与预览 ----
    def _sync_tab(self) -> None:
        is_wpd = self._tab == WPD_TAB
        self.query_one("#par-threads", Input).display = not is_wpd
        self.query_one("#par-axis-label", Static).display = is_wpd
        self.query_one("#par-axis-switch", Switch).display = is_wpd
        for node in self.query(".par-axis-input"):
            node.display = is_wpd
        self.query_one("#par-append-label", Static).display = is_wpd
        self.query_one("#par-append", Switch).display = is_wpd
        self._preview()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._tab = str(event.pressed.label)
        self._sync_tab()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "par-input":
            self._preview()

    def _preview(self) -> None:
        source = self.query_one("#par-input", Input).value.strip()
        preview = self.query_one("#par-out-preview", Static)
        if not source:
            preview.update("[dim]输出目录：填写输入后显示[/dim]")
            return
        suffix = "wpd_out" if self._tab == WPD_TAB else "mineru_out"
        preview.update(f"[dim]输出目录（默认）：{Path(source).parent / suffix}[/dim]")

    def action_pick_path(self) -> None:
        from tui.ui.file_browser import FileBrowserScreen

        if self._app is not None:
            self._app.push_screen(FileBrowserScreen(self.client, pick=True),
                                  self._fill_path)

    def _fill_path(self, path: str | None) -> None:
        if path:
            self.query_one("#par-input", Input).value = path
            self._preview()

    # ---- 提交 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "par-run":
            return
        result = self.query_one("#par-result", Static)
        source = self.query_one("#par-input", Input).value.strip()
        if not source:
            result.update(f"[${'nova'}]{design.icon('status.warn')} 输入路径必填[/]")
            return
        config: dict = {"input_path": source}
        if self._tab == MINERU_TAB:
            task_type = "mineru"
            threads = self.query_one("#par-threads", Input).value.strip()
            if threads:
                try:
                    config["max_threads"] = int(threads)
                except ValueError:
                    result.update(f"[${'nova'}]{design.icon('status.warn')} "
                                  "线程上限须为整数[/]")
                    return
        else:
            task_type = "wpd"
            if self.query_one("#par-axis-switch", Switch).value:
                axis: dict[str, float] = {}
                for key in _AXIS_KEYS:
                    raw = self.query_one(f"#par-axis-{key}", Input).value.strip()
                    if raw:
                        try:
                            axis[key] = float(raw)
                        except ValueError:
                            result.update(f"[${'nova'}]{design.icon('status.warn')} "
                                          f"axis.{key} 须为数值[/]")
                            return
                if axis:
                    config["axis"] = axis
            if self.query_one("#par-append", Switch).value:
                config["append_to_md"] = True
        try:
            data = await self.client.create_task(task_type, config, title=self._tab)
        except Exception as exc:
            result.update(f"[${'nova'}]创建失败[/]  {exc}")
            return
        self._task_uuid = str(data["task_uuid"])
        result.update(
            f"[${'aurora'}]{design.icon('task.success')} 任务已创建[/]"
            f" {self._task_uuid[:8]}（{task_type}）")
        await self._mount_progress_card()

    async def _mount_progress_card(self) -> None:
        for old in self.query(TaskProgressCard):
            await old.remove()
        if self._task_uuid:
            await self.mount(TaskProgressCard(self.client, self._task_uuid,
                                              self._selected_type()))

    def _selected_type(self) -> str:
        return "wpd" if self._tab == WPD_TAB else "mineru"
