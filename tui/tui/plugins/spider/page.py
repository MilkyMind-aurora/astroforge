# -*- coding: utf-8 -*-
"""采集中心（方案 §3.3 表单卡族升级，MF2）：四类任务 + 输入井 + 高级折叠 + 中止。

- 功能选择 RadioSet 胶囊化（单页转 MD ☄ / 整站结构化 ✺ / PDF 批量 ⬇ / 表格抓取 ▦，
  星符语义映射见 _TASK_TYPES）
- URL 输入井：sunken 底 + 聚焦描边升档（border-active=aurora，V1.2-1 盒式语言）
- 高级参数折叠区：「✧ 高级 ▸/▾」行内展开（TUI 无 animateContentSize，瞬时展开）
- 提交钮全宽 aurora 实底；busy 态转「中止」（nova 描边，POST /tasks/{uuid}/cancel）
- 提交后下半区挂共用任务进度卡（components.task_card，WS progress 事件驱动）
数据契约：POST /tasks → 订阅 /ws/logs/{uuid}；GET /tasks/{uuid} 兜底。
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Input, RadioButton, RadioSet, Static

from tui.components.task_card import TaskProgressCard
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

# 四类任务（方案 §3.3 星符：☄/✺/⬇/▦ → icons.yaml 语义名）
_TASK_TYPES: list[tuple[str, str, str]] = [
    ("spider_single", "nav.spider", "单页转 Markdown"),
    ("spider_site", "nav.pipeline", "整站结构化爬取"),
    ("spider_pdf", "task.pdf", "PDF 批量下载"),
    ("spider_table", "task.table", "表格抓取"),
]


class SpiderPage(VerticalScroll):
    """采集中心：表单卡 + 任务进度卡 + 最近任务。"""

    BINDINGS = [Binding("f", "pick_path", "选路径", show=False)]

    CSS = """
    #sp-form { border: round $border-subtle; background: $card; padding: 0 2;
        margin-top: 1; }
    #sp-title { color: $ink-900; margin-top: 1; }
    #sp-url, #sp-adv-box Input { background: $sunken; border: round $border-subtle; }
    #sp-url:focus, #sp-adv-box Input:focus { border: round $border-active; }
    #sp-adv-head { color: $ink-600; margin-top: 1; }
    #sp-adv-head:hover { color: $ink-900; }
    #sp-run { width: 100%; margin-top: 1; }
    #sp-run.busy { background: $card; border: round $nova; color: $nova; }
    #sp-recent { color: $ink-600; margin-top: 1; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-spider")
        self.client = client
        self._app = app_ref
        self._task_uuid: str | None = None
        self._busy = False

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.spider')} 采集中心[/b]"
            f"  [dim]Scrapling 四类爬取 · 数据不出本机[/dim]", id="sp-title",
            classes="page-body")
        with Vertical(id="sp-form"):
            yield Static("任务类型", classes="page-body")
            yield RadioSet(
                *[RadioButton(
                    f"{design.icon(icon)} {label}", value=(i == 0))
                  for i, (_key, icon, label) in enumerate(_TASK_TYPES)],
                id="sp-type",
            )
            yield Input(placeholder="目标 URL（必填，https://…）", id="sp-url")
            yield Static(f"{design.icon('status.hint')} 高级 "
                         f"{design.icon('misc.caret_right')}", id="sp-adv-head")
            with Vertical(id="sp-adv-box") as adv:
                adv.display = False
                yield Input(placeholder="输出目录（默认 data/output/spider）",
                            id="sp-output")
                yield Input(placeholder="最大页面数（仅整站，默认 200）", id="sp-pages")
                yield Input(placeholder="请求间隔秒（默认 1.0）", id="sp-interval")
            yield Button(f"{design.icon('ai.done')} 启动任务", id="sp-run",
                         variant="primary")
        yield Static("", id="sp-result")
        yield Static("[b]最近任务[/b]  （加载中…）", id="sp-recent")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_recent(), exclusive=True)

    # ---- 表单 ----
    def _selected_type(self) -> str:
        selected = self.query_one("#sp-type", RadioSet).selected or ""
        for key, _icon, label in _TASK_TYPES:
            if label in selected:
                return key
        return "spider_single"

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """整站才有 max_pages；类型切换时联动高级区字段显隐（轻交互）。"""
        if event.radio_set.id == "sp-type":
            key = self._selected_type()
            self.query_one("#sp-pages", Input).display = key == "spider_site"

    def on_static_click(self, event: Static.Click) -> None:
        """「✧ 高级」折叠区行内展开/收起（§3.3）。"""
        if event.static.id == "sp-adv-head":
            box = self.query_one("#sp-adv-box", Vertical)
            box.display = not box.display
            caret = design.icon("misc.caret_down" if box.display else "misc.caret_right")
            event.static.update(
                f"{design.icon('status.hint')} 高级 {caret}")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "sp-url":
            self.query_one("#sp-run", Button).focus()

    # ---- 提交 / 中止 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "sp-run":
            return
        if self._busy:
            await self._cancel()
            return
        await self._submit()

    async def _submit(self) -> None:
        result = self.query_one("#sp-result", Static)
        url = self.query_one("#sp-url", Input).value.strip()
        if not url:
            result.update(f"[${'nova'}]{design.icon('status.error')} URL 必填[/]")
            return
        task_type = self._selected_type()
        config: dict = {"url": url}
        output = self.query_one("#sp-output", Input).value.strip()
        if output:
            config["output_dir"] = output
        if task_type == "spider_site":
            pages = self.query_one("#sp-pages", Input).value.strip()
            if pages:
                try:
                    config["max_pages"] = int(pages)
                except ValueError:
                    result.update(f"[${'nova'}]{design.icon('status.warn')} "
                                  "最大页面数须为整数[/]")
                    return
        interval = self.query_one("#sp-interval", Input).value.strip()
        if interval:
            try:
                config["request_interval"] = float(interval)
            except ValueError:
                result.update(f"[${'nova'}]{design.icon('status.warn')} "
                              "请求间隔须为数字[/]")
                return
        try:
            data = await self.client.create_task(task_type, config, title=task_type)
        except Exception as exc:
            result.update(f"[${'nova'}]创建失败[/] {exc}")
            return
        self._task_uuid = str(data["task_uuid"])
        result.update(
            f"[${'aurora'}]{design.icon('task.success')} 任务已创建[/] "
            f"{self._task_uuid[:8]}（{task_type}）")
        self._set_busy(True)
        await self._mount_progress_card()

    async def _cancel(self) -> None:
        """busy 态中止（服务契约：cancel 置位，调度器在步骤间隙收尾）。"""
        if not self._task_uuid:
            return
        try:
            await self.client.cancel_task(self._task_uuid)
        except Exception as exc:
            self.app.notify(f"中止请求失败：{exc}", severity="error")
            return
        self.query_one("#sp-result", Static).update(
            f"[${'molten'}]{design.icon('status.warn')} 已请求中止[/] "
            f"{self._task_uuid[:8]}")

    def _set_busy(self, busy: bool) -> None:
        """提交钮状态机：idle=aurora 实底「启动任务」/ busy=nova 描边「中止」。"""
        self._busy = busy
        run_btn = self.query_one("#sp-run", Button)
        run_btn.set_class(busy, "busy")
        run_btn.label = (f"{design.icon('task.failed')} 中止" if busy
                         else f"{design.icon('ai.done')} 启动任务")

    async def _mount_progress_card(self) -> None:
        content = self.query_one("#sp-result").parent
        for old in self.query(TaskProgressCard):
            await old.remove()
        if content is not None:
            await content.mount(TaskProgressCard(
                self.client, self._task_uuid or "", self._selected_type()))

    def on_task_progress_card_finished(self, event: TaskProgressCard.Finished) -> None:
        """任务终态：提交钮复位 + 刷新最近任务。"""
        self._set_busy(False)
        self.query_one("#sp-result", Static).update(
            f"[${'aurora' if event.status == 'success' else 'nova'}]"
            f"{design.icon('task.success' if event.status == 'success' else 'task.failed')}"
            f" 任务{event.status}[/] {event.card.task_uuid[:8]}")
        self.run_worker(self.refresh_recent(), exclusive=True)

    # ---- 最近任务 ----
    async def refresh_recent(self) -> None:
        try:
            recent = self.query_one("#sp-recent", Static)
        except Exception:
            return  # 页面已被换装移除（换页竞态），worker 静默退出
        try:
            data = await self.client.list_tasks(page=1)
        except Exception as exc:
            recent.update(f"[$nova]任务列表失败[/] {exc}")
            return
        lines = ["[b]最近任务[/b]"]
        for task in (data or {}).get("items", [])[:5]:
            status = str(task["status"])
            glyph, color = {
                "running": ("task.running", "aurora"), "success": ("task.success", "aurora"),
                "failed": ("task.failed", "nova"), "canceled": ("task.canceled", "ink-400"),
            }.get(status, ("task.pending", "ink-400"))
            lines.append(
                f"  {task['task_uuid'][:8]}  {task['task_type']}  "
                f"[${color}]{design.icon(glyph)}[/] {status} 进度 {task['progress']}%")
        try:
            recent.update("\n".join(lines))
        except Exception:
            return  # 更新间隙被移除，同上静默

    def action_pick_path(self) -> None:
        if self._app is not None:
            from tui.ui.file_browser import FileBrowserScreen

            self._app.push_screen(FileBrowserScreen(self.client, pick=True))
