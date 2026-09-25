# -*- coding: utf-8 -*-
"""日志面板（方案 §3.6，MF2 重写，替换 MF1 居中 Modal 版 LogScreen）。

形态：底部 60% 高抽屉（非居中 Modal）；RichLog 流式 + 级别过滤 chips
（INFO/WARN/ERROR，切换时按缓冲重渲——过滤作用于滚动缓冲语义，非逐帧路径）；
任务切换器（优先级：运行中 > 最近失败 > 最近成功/其他）；断线 REST 补拉
GET /tasks/{uuid}/logs?offset=N 后重订阅（指数退避封顶 5 次）。
注：服务端日志事件目前只发 INFO/ERROR 两级（task_scheduler._make_line_callback），
WARN 级留档待服务端补级；文本内 [WARN] 前缀亦识别，行为向前兼容。
"""
from __future__ import annotations

import asyncio
import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, RichLog, Select, Static

from tui.components.chips import ChipBar
from tui.components.theme import theme_token as _theme_token
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

LEVEL_ALL = "ALL"
LEVEL_TOKEN = {"INFO": "ink-600", "WARN": "molten", "ERROR": "nova"}
RESUB_BACKOFF_S = 1.0
RESUB_MAX = 5
TAIL_RENDER_LIMIT = 400  # 过滤重渲与补拉渲染的单次上限（RichLog 滚动缓冲保护）

TASK_PRIORITY = {"running": 0, "failed": 1}


def detect_level(level: str | None, text: str) -> str:
    """日志级别判定（纯函数，单测覆盖）：level 字段优先，文本 [WARN]/[ERROR] 兜底。"""
    if level in LEVEL_TOKEN:
        return level
    for name in ("ERROR", "WARN"):
        if f"[{name}]" in text:
            return name
    return "INFO"


def sort_tasks(items: list[dict]) -> list[dict]:
    """任务切换排序（纯函数，单测覆盖）：运行中 > 最近失败 > 其他，同级按创建升序。"""
    return sorted(
        items,
        key=lambda t: (TASK_PRIORITY.get(str(t.get("status")), 2),
                       str(t.get("created_at", ""))),
    )


class LogPanelScreen(Screen):
    """日志面板底部抽屉：Ctrl+` 唤起，Esc 退出。"""

    CSS = """
    LogPanelScreen { align: center bottom; }
    #lp-box { width: 100%; height: 60%; border-top: solid $border-active;
        background: $card; padding: 0 2; }
    #lp-head { height: 1; color: $ink-900; margin-top: 1; }
    #lp-controls { height: auto; margin-bottom: 1; }
    #lp-task { width: 46; margin-right: 1; }
    #lp-log { height: 1fr; border: round $border-subtle; background: $sunken;
        padding: 0 1; }
    """

    BINDINGS = [Binding("escape", "dismiss_panel", "关闭", show=False)]

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self._filter = LEVEL_ALL
        self._buffer: list[tuple[str, str]] = []  # (level, text) 全量缓冲
        self._task_uuid: str | None = None
        self._resub_backoff = RESUB_BACKOFF_S

    def compose(self) -> ComposeResult:
        with Vertical(id="lp-box"):
            yield Static(
                f"{design.icon('status.hint')} [b]日志面板[/b]"
                f"  [dim]运行中 > 最近失败 > 最近成功 · 断线自动 REST 补拉[/dim]",
                id="lp-head")
            with Horizontal(id="lp-controls"):
                yield Select([], prompt="选择任务", id="lp-task", allow_blank=True)
                yield ChipBar(
                    [(LEVEL_ALL, "全部"), ("INFO", "INFO"), ("WARN", "WARN"),
                     ("ERROR", "ERROR")], id="lp-levels")
                yield Button("刷新", id="lp-refresh")
            yield RichLog(id="lp-log", markup=False, wrap=True, highlight=False)

    def on_mount(self) -> None:
        self.run_worker(self._bootstrap(), exclusive=True)

    async def _bootstrap(self) -> None:
        try:
            data = await self.client.list_tasks(page=1, page_size=20)
        except Exception as exc:
            self._system_line(f"任务列表加载失败：{exc}", "nova")
            return
        items = sort_tasks(list((data or {}).get("items", [])))
        select = self.query_one("#lp-task", Select)
        select.set_options([
            (self._task_label(task), str(task["task_uuid"])) for task in items
        ] or [("（暂无任务）", "")])
        target = next((str(t["task_uuid"]) for t in items
                       if t.get("status") == "running"), None)
        if target is None:
            failed = next((t for t in items if t.get("status") == "failed"), None)
            target = str((failed or next(iter(items), {})).get("task_uuid", "")) or None
        if target:
            select.value = target  # 触发 on_select_changed → _follow
        else:
            self._system_line("当前没有任务。启动任务后这里会实时滚动其日志。", "ink-400")

    @staticmethod
    def _task_label(task: dict) -> str:
        status = str(task.get("status", "?"))
        glyph, _ = {
            "running": ("task.running", "aurora"), "success": ("task.success", "aurora"),
            "failed": ("task.failed", "nova"), "canceled": ("task.canceled", "ink-400"),
        }.get(status, ("task.pending", "ink-400"))
        return (f"{design.icon(glyph)} {str(task.get('task_uuid'))[:8]} "
                f"{task.get('task_type', '?')} · {status}")

    # ---- 级别过滤与渲染 ----
    def on_chip_bar_changed(self, event: ChipBar.Changed) -> None:
        if event.chip_bar.id != "lp-levels":
            return
        self._filter = event.value or LEVEL_ALL
        self._rerender()

    def _passes(self, level: str) -> bool:
        return self._filter in (LEVEL_ALL, level)

    def _line_text(self, level: str, text: str) -> Text:
        return Text(text, style=_theme_token(self.app, LEVEL_TOKEN.get(level, "ink-600")))

    def _system_line(self, text: str, token: str) -> None:
        self.query_one("#lp-log", RichLog).write(
            Text(text, style=_theme_token(self.app, token)))

    def _rerender(self) -> None:
        """过滤切换：按缓冲重渲（≤TAIL_RENDER_LIMIT 尾部；非逐帧路径）。"""
        log_widget = self.query_one("#lp-log", RichLog)
        log_widget.clear()
        shown = [entry for entry in self._buffer if self._passes(entry[0])]
        for level, text in shown[-TAIL_RENDER_LIMIT:]:
            log_widget.write(self._line_text(level, text))

    # ---- 任务跟随（WS 主通道 + REST 补拉兜底） ----
    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "lp-task" or not event.value:
            return
        self._follow(str(event.value))

    def _follow(self, task_uuid: str) -> None:
        if task_uuid == self._task_uuid:
            return
        self._task_uuid = task_uuid
        self._buffer.clear()
        self.query_one("#lp-log", RichLog).clear()
        self.run_worker(self._follow_worker(task_uuid), group="log-follow",
                        exclusive=True)

    async def _follow_worker(self, task_uuid: str) -> None:
        log_widget = self.query_one("#lp-log", RichLog)
        # 先 REST 全量补拉（断线兜底也靠它），再挂 WS 增量
        try:
            data = await self.client.task_logs(task_uuid, offset=0)
        except Exception as exc:
            self._system_line(f"日志补拉失败：{exc}", "nova")
            return
        for line in list((data or {}).get("lines", [])):
            level = detect_level(None, line)
            self._buffer.append((level, line))
            log_widget.write(self._line_text(level, line))
        backoff = RESUB_BACKOFF_S
        for _ in range(RESUB_MAX):
            try:
                ws = await self.client.subscribe_logs(task_uuid)
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") != "log":
                        continue
                    payload = msg.get("payload") or {}
                    level = detect_level(payload.get("level"), str(payload.get("text", "")))
                    text = str(payload.get("text", ""))
                    self._buffer.append((level, text))
                    if self._passes(level):
                        log_widget.write(self._line_text(level, text))
                backoff = RESUB_BACKOFF_S
            except asyncio.CancelledError:
                raise
            except Exception:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
                continue
            # 正常断开：REST 补拉缺口后重订阅
            try:
                data = await self.client.task_logs(task_uuid, offset=len(self._buffer))
            except Exception:
                continue
            for line in list((data or {}).get("lines", [])):
                level = detect_level(None, line)
                self._buffer.append((level, line))
                if self._passes(level):
                    log_widget.write(self._line_text(level, line))
        self._system_line(f"日志通道重连 {RESUB_MAX} 次未恢复，已停止跟随。", "molten")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "lp-refresh":
            if self._task_uuid:
                self._buffer.clear()
                self.query_one("#lp-log", RichLog).clear()
                self._task_uuid = None
                select = self.query_one("#lp-task", Select)
                select.value = None
                await self._bootstrap()

    def action_dismiss_panel(self) -> None:
        self.dismiss()
