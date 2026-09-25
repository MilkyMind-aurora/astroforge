# -*- coding: utf-8 -*-
"""解析中心（方案 §3.3，替换占位页）：MinerU / WPD 两 Tab 最小可用表单。

- MinerU：input_path + 线程上限（config.max_threads，默认 4）→ POST /tasks
- WPD：input_path + 坐标轴手动修正（config.axis 四值）→ POST /tasks
- F 键联动文件浏览器选路径回填；输出目录预览行实时跟随输入
任务进度卡属 V1-T.2.5（MF2），本页先落创建 + Ctrl+` 日志指引。
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, RadioButton, RadioSet, Static, Switch
from tui.theme.generated import tokens as design

MINERU_TAB, WPD_TAB = "MinerU 文档解析", "WPD 图表数值提取"
_AXIS_KEYS = ("x_min", "x_max", "y_min", "y_max")


class ParserPage(VerticalScroll):
    """解析中心：MinerU / WPD 双 Tab 表单。"""

    BINDINGS = [Binding("f", "pick_path", "选路径")]

    def __init__(self, client, app_ref=None) -> None:  # noqa: ANN001（App 循环依赖）
        super().__init__(id="page-parser")
        self.client = client
        self._app = app_ref
        self._tab = MINERU_TAB

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.parser')} 解析中心[/b]"
            f"  [dim]MinerU 文档解析 · WebPlotDigitizer 图表提值[/dim]",
            id="par-title", classes="page-body",
        )
        yield RadioSet(
            RadioButton(MINERU_TAB, value=True),
            RadioButton(WPD_TAB),
            id="par-tab",
        )
        yield Input(placeholder="输入路径（PDF/图片/目录，必填；F 打开文件浏览器）", id="par-input")
        yield Input(placeholder="线程上限（MinerU 默认 4，防 ONNX/BLAS 抢核）", id="par-threads")
        yield Static("坐标轴手动修正（WPD，不开则自动检测）", id="par-axis-label",
                     classes="page-body")
        yield Switch(value=False, id="par-axis-switch")
        for key in _AXIS_KEYS:
            yield Input(placeholder=f"axis.{key}（数值，可选）", id=f"par-axis-{key}",
                        classes="par-axis-input")
        yield Static("[dim]输出目录：填写输入后显示[/dim]", id="par-out-preview")
        yield Button("启动解析任务", id="par-run", variant="primary")
        yield Static("", id="par-result")

    def on_mount(self) -> None:
        self._sync_tab()

    def _sync_tab(self) -> None:
        is_wpd = self._tab == WPD_TAB
        self.query_one("#par-threads", Input).display = not is_wpd
        self.query_one("#par-axis-label", Static).display = is_wpd
        self.query_one("#par-axis-switch", Switch).display = is_wpd
        for node in self.query(".par-axis-input"):
            node.display = is_wpd
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
            self._app.push_screen(FileBrowserScreen(self.client, pick=True), self._fill_path)

    def _fill_path(self, path: str | None) -> None:
        if path:
            self.query_one("#par-input", Input).value = path
            self._preview()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "par-run":
            return
        result = self.query_one("#par-result", Static)
        source = self.query_one("#par-input", Input).value.strip()
        if not source:
            result.update(f"[$nova]{design.icon('status.warn')} 输入路径必填[/$nova]")
            return
        config: dict = {"input_path": source}
        if self._tab == MINERU_TAB:
            task_type = "mineru"
            threads = self.query_one("#par-threads", Input).value.strip()
            if threads:
                try:
                    config["max_threads"] = int(threads)
                except ValueError:
                    result.update(f"[$nova]{design.icon('status.warn')} 线程上限须为整数[/$nova]")
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
                            result.update(f"[$nova]{design.icon('status.warn')}"
                                          f" axis.{key} 须为数值[/$nova]")
                            return
                if axis:
                    config["axis"] = axis
        try:
            data = await self.client.create_task(task_type, config, title=self._tab)
        except Exception as exc:
            result.update(f"[$nova]创建失败[/$nova]  {exc}")
            return
        result.update(
            f"[$aurora]{design.icon('task.success')} 任务已创建[/$aurora]"
            f" {str(data['task_uuid'])[:8]}（{task_type}）· Ctrl+` 打开日志面板实时跟踪"
        )
