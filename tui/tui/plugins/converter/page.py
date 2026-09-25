# -*- coding: utf-8 -*-
"""转换中心（方案 §3.3 表单卡族，MF2）：双向两卡 + 模板选择器 + 任务进度卡。

- 入库 anydoc（Office→MD）：input_path（文件/目录均可，目录=批量）
- 出库 md2docx（MD→Word）：input_path + 模板选择器（OptionList，数据源
  /templates，每项=模板名+场景副题；高亮联动 /templates/{key}/preview 取
  「预览说明一行」：TOC/页码配置与文件在位状态）+ 合并单文件开关
- F 键联动文件浏览器选路径回填；输出目录预览行实时跟随输入
数据契约：POST /tasks → 提交后下半区挂 TaskProgressCard（WS progress 事件）。
"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Input,
    OptionList,
    RadioButton,
    RadioSet,
    Static,
    Switch,
)
from textual.widgets.option_list import Option

from tui.components.task_card import TaskProgressCard
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

ANYDOC_TAB, MD2DOCX_TAB = "入库 anydoc（Office→MD）", "出库 md2docx（MD→Word）"


class ConverterPage(VerticalScroll):
    """转换中心：anydoc 入库 / md2docx 出库双卡表单 + 任务进度卡。"""

    BINDINGS = [Binding("f", "pick_path", "选路径")]

    CSS = """
    #conv-form { border: round $border-subtle; background: $card; padding: 0 2;
        margin-top: 1; }
    #conv-title { color: $ink-900; margin-top: 1; }
    #conv-form Input { background: $sunken; border: round $border-subtle; }
    #conv-form Input:focus { border: round $border-active; }
    #conv-tpl { height: 6; border: round $border-subtle; background: $sunken; }
    #conv-tpl-preview { color: $ink-400; }
    #conv-run { width: 100%; margin-top: 1; }
    #conv-out-preview { color: $ink-400; margin-top: 1; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-converter")
        self.client = client
        self._app = app_ref
        self._tab = ANYDOC_TAB
        self._templates: list[dict] = []
        self._task_uuid: str | None = None
        self._preview_sig = ""  # 防抖：同模板重复高亮不重复请求

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.converter')} 转换中心[/b]"
            f"  [dim]anydoc 办公文档入库 · md2docx 模板化出 Word[/dim]",
            id="conv-title", classes="page-body",
        )
        with Vertical(id="conv-form"):
            yield RadioSet(
                RadioButton(ANYDOC_TAB, value=True),
                RadioButton(MD2DOCX_TAB),
                id="conv-tab",
            )
            yield Input(placeholder="输入路径（Office 文件/目录 或 MD 文件/目录，"
                                    "必填；F 浏览器）", id="conv-input")
            yield Static("[dim]模板（md2docx，数据源 /templates）：[/dim]",
                         id="conv-tpl-label")
            yield OptionList(id="conv-tpl")
            yield Static("[dim]（模板预览说明）[/dim]", id="conv-tpl-preview")
            yield Static("合并单文件（md2docx：目录内全部 MD 合并输出一个 DOCX）",
                         id="conv-merge-label")
            yield Switch(value=False, id="conv-merge")
            yield Static("[dim]输出目录：填写输入后显示[/dim]", id="conv-out-preview")
            yield Button("启动转换任务", id="conv-run", variant="primary")
        yield Static("", id="conv-result")

    def on_mount(self) -> None:
        self._sync_tab()
        self.run_worker(self._load_templates(), exclusive=True)

    # ---- 模板选择器（/templates + /templates/{key}/preview）----
    async def _load_templates(self) -> None:
        """模板清单（名称+场景副题+缺档标记），加载失败降级为占位行。"""
        option_list = self.query_one("#conv-tpl", OptionList)
        try:
            data = await self.client.list_templates()
        except Exception as exc:
            option_list.add_option(Option(f"模板加载失败：{exc}", id="tpl-error"))
            return
        self._templates = list((data or {}).get("items", []))
        default = str((data or {}).get("default", ""))
        option_list.clear_options()
        for index, tpl in enumerate(self._templates):
            missing = "" if tpl.get("exists") else "  [dim](文件缺失)[/dim]"
            mark = (f"[${'aurora'}]{design.icon('task.success')}[/] "
                    if tpl.get("template_key") == default else "  ")
            option_list.add_option(Option(
                f"{mark}{design.icon('nav.task')} {tpl.get('name', '?')}"
                f"  [dim]{tpl.get('scene', '')}{missing}[/dim]",
                id=tpl.get("template_key"),
            ))
            if tpl.get("template_key") == default:
                option_list.highlighted = index
        await self._load_template_preview()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        self.run_worker(self._load_template_preview(), exclusive=True)

    async def _load_template_preview(self) -> None:
        """预览说明一行：/templates/{key}/preview 的 TOC/页码配置与在位状态。"""
        preview = self.query_one("#conv-tpl-preview", Static)
        template = self._selected_template()
        if not template or template == "tpl-error":
            preview.update("[dim]（模板预览说明）[/dim]")
            return
        if template == self._preview_sig:
            return
        self._preview_sig = template
        try:
            data = await self.client.template_preview(template)
        except Exception as exc:
            preview.update(f"[dim]模板预览失败：{exc}[/dim]")
            return
        config = data.get("config", {})
        flags = " · ".join([
            f"目录 {'开' if config.get('enable_toc') else '关'}",
            f"页码 {'开' if config.get('enable_page_number') else '关'}",
        ])
        inplace = "模板文件在位" if data.get("exists") else "模板文件缺失"
        preview.update(f"[dim]预览：{data.get('name', template)} · {flags} · "
                       f"{inplace}[/dim]")

    def _selected_template(self) -> str | None:
        option_list = self.query_one("#conv-tpl", OptionList)
        if option_list.option_count == 0 or option_list.highlighted is None:
            return None
        return option_list.get_option_at_index(option_list.highlighted).id

    # ---- Tab 切换与预览 ----
    def _sync_tab(self) -> None:
        is_md2docx = self._tab == MD2DOCX_TAB
        self.query_one("#conv-tpl-label", Static).display = is_md2docx
        self.query_one("#conv-tpl", OptionList).display = is_md2docx
        self.query_one("#conv-tpl-preview", Static).display = is_md2docx
        self.query_one("#conv-merge-label", Static).display = is_md2docx
        self.query_one("#conv-merge", Switch).display = is_md2docx
        self._preview()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._tab = str(event.pressed.label)
        self._sync_tab()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "conv-input":
            self._preview()

    def _preview(self) -> None:
        source = self.query_one("#conv-input", Input).value.strip()
        preview = self.query_one("#conv-out-preview", Static)
        if not source:
            preview.update("[dim]输出目录：填写输入后显示[/dim]")
            return
        suffix = "docx_out" if self._tab == MD2DOCX_TAB else "md_out"
        preview.update(f"[dim]输出目录（默认）：{Path(source).parent / suffix}[/dim]")

    def action_pick_path(self) -> None:
        from tui.ui.file_browser import FileBrowserScreen

        if self._app is not None:
            self._app.push_screen(FileBrowserScreen(self.client, pick=True),
                                  self._fill_path)

    def _fill_path(self, path: str | None) -> None:
        if path:
            self.query_one("#conv-input", Input).value = path
            self._preview()

    # ---- 提交 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "conv-run":
            return
        result = self.query_one("#conv-result", Static)
        source = self.query_one("#conv-input", Input).value.strip()
        if not source:
            result.update(f"[${'nova'}]{design.icon('status.warn')} 输入路径必填[/]")
            return
        config: dict = {"input_path": source}
        if self._tab == MD2DOCX_TAB:
            task_type = "md2docx"
            template = self._selected_template()
            if template and template != "tpl-error":
                config["template"] = template
            config["merge"] = self.query_one("#conv-merge", Switch).value
        else:
            task_type = "anydoc"
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
                                              "md2docx" if self._tab == MD2DOCX_TAB
                                              else "anydoc"))
