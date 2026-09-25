# -*- coding: utf-8 -*-
"""任务历史 · 星图志（方案 §3.5，MF2 重写）。

状态筛选 chips（全部/运行/成功/失败/取消，选中胶囊=chipsSelectedBg）+
DataTable（星符状态列/类型/标题/耗时 mono/时刻）+ 行详情=右侧滑入抽屉
（T_SLIDE out_cubic）：步骤时间线（复用 components.timeline，失败步骤可单步
重试）+ 日志尾 20 行 + 操作行（任务级重试/取消/导出日志）；失败任务重试带
#16 撤销倒计时（10s 内可撤——服务契约重试=新任务，撤销=取消该新任务）。
注：全局任务列表无 WS 通道（服务端仅按任务广播），保留 5s 轮询；单任务进度
走 WS（进度卡/时间线内）。产物列表暂缺：服务端 artifacts 表未暴露查询路由，
详情抽屉如实不渲染产物区（禁伪造）。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Button, DataTable, RichLog, Static

from tui.components.chips import ChipBar
from tui.components.theme import theme_token as _theme_token
from tui.components.timeline import StepTimeline
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

STATUS_FILTERS: list[tuple[str | None, str]] = [
    (None, "全部"), ("running", "运行"), ("success", "成功"),
    ("failed", "失败"), ("canceled", "取消"),
]
UNDO_WINDOW_S = 10       # #16 撤销倒计时（10s 内可撤）
REFRESH_S = 5.0
LOG_TAIL_LINES = 20

STATUS_META: dict[str, tuple[str, str]] = {
    "running": ("task.running", "aurora"),
    "success": ("task.success", "aurora"),
    "failed": ("task.failed", "nova"),
    "canceled": ("task.canceled", "ink-400"),
}


def duration_text(started_at: str | None, finished_at: str | None) -> str:
    """耗时 mono 文本（纯函数，单测覆盖）：无起止回落 -。"""
    try:
        start = dt.datetime.fromisoformat(str(started_at))
        end = dt.datetime.fromisoformat(str(finished_at))
    except (TypeError, ValueError):
        return "-"
    seconds = max(0, int((end - start).total_seconds()))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def local_time(iso: str | None) -> str:
    """时刻列（本地时区 HH:MM:SS；解析失败回落 -）。"""
    try:
        parsed = dt.datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return "-"
    return parsed.astimezone().strftime("%H:%M:%S")


class HistoryDetailScreen(Screen):
    """行详情右侧抽屉：步骤时间线 + 日志尾 20 行 + 操作行（重试/取消/导出）。"""

    CSS = """
    HistoryDetailScreen { align: right middle; }
    #hd-box { width: 62%; min-width: 56; height: 100%; border-left: thick $aurora;
        background: $card; padding: 0 2; }
    #hd-title { color: $ink-900; margin-top: 1; }
    #hd-meta { color: $ink-600; margin-bottom: 1; }
    #hd-ops { height: auto; margin-top: 1; }
    #hd-ops Button { margin-right: 1; }
    #hd-undo { height: 1; color: $molten; display: none; margin-top: 1; }
    #hd-undo.undo-on { display: block; }
    #hd-logs { height: 1fr; border: round $border-subtle; background: $sunken;
        padding: 0 1; margin-top: 1; }
    """

    BINDINGS = [Binding("escape", "dismiss_drawer", "关闭", show=False)]

    def __init__(self, client: ServiceClient, task: dict) -> None:
        super().__init__()
        self.client = client
        self.task = dict(task)
        self._undo_left = 0
        self._undo_task: str | None = None

    def compose(self) -> ComposeResult:
        task = self.task
        glyph, color = STATUS_META.get(str(task.get("status")),
                                       ("task.pending", "ink-400"))
        with Vertical(id="hd-box"):
            yield Static(
                f"[b]{design.icon(glyph)} {task.get('title', task.get('task_type', '?'))}[/b]"
                f"  [${color}]{task.get('status', '?')}[/${color}]",
                id="hd-title")
            yield Static(
                f"{task.get('task_type', '?')} · {str(task.get('task_uuid'))[:8]} · "
                f"进度 {task.get('progress', 0)}%"
                + (f" · [$nova]code {task.get('error_code')}[/]"
                   if task.get("error_code") else ""),
                id="hd-meta")
            yield StepTimeline(self.client, str(task.get("task_uuid")),
                               list(task.get("steps", [])),
                               title="步骤时间线（失败步骤可单步重试）")
            yield RichLog(id="hd-logs", markup=False, wrap=True, highlight=False)
            with Horizontal(id="hd-ops"):
                if task.get("status") in ("failed", "canceled"):
                    yield Button(f"{design.icon('task.running')} 重试（新任务）",
                                 id="hd-retry")
                if task.get("status") in ("running", "pending"):
                    yield Button(f"{design.icon('task.failed')} 取消", id="hd-cancel")
                yield Button("导出日志", id="hd-export")
            yield Static("", id="hd-undo")

    def on_mount(self) -> None:
        # 右侧滑入（T_SLIDE out_cubic，§1.4/#21 的 TUI 抽屉近似）
        box = self.query_one("#hd-box", Vertical)
        box.styles.offset = Offset(int(self.app.size.width * 0.62), 0)
        duration = design.MOTION_TUI["t_slide"]["duration_ms"] / 1000
        box.animate("offset", Offset(0, 0), duration=duration,
                    easing=design.MOTION_TUI["t_slide"]["easing"])
        self.run_worker(self._load_tail_logs(), exclusive=True)

    async def _load_tail_logs(self) -> None:
        log_widget = self.query_one("#hd-logs", RichLog)
        try:
            data = await self.client.task_logs(str(self.task.get("task_uuid")), offset=0)
        except Exception as exc:
            log_widget.write(Text(
                f"日志尾行拉取失败：{exc}",
                style=_theme_token(self.app, "nova")))
            return
        lines = list((data or {}).get("lines", []))[-LOG_TAIL_LINES:]
        if not lines:
            log_widget.write(Text("（暂无日志）", style=_theme_token(self.app, "ink-400")))
            return
        for line in lines:
            style = ("nova" if "[ERROR]" in line else
                     "molten" if "[WARN]" in line else "ink-600")
            log_widget.write(Text(line, style=_theme_token(self.app, style)))

    async def on_step_timeline_step_retried(self, event: StepTimeline.StepRetried) -> None:
        """时间线内单步重试成功：刷新详情状态行。"""
        self.query_one("#hd-meta", Static).update(
            "已请求步骤级续跑（前序产物已保留）· 刷新中…")
        try:
            detail = await self.client.task_detail(event.task_uuid)
        except Exception:
            return
        self.task = detail
        await self.query_one(StepTimeline).set_steps(list(detail.get("steps", [])))

    # ---- 操作行 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        task_uuid = str(self.task.get("task_uuid"))
        if button_id == "hd-retry":
            await self._retry_with_undo(task_uuid)
        elif button_id == "hd-cancel":
            await self._cancel(task_uuid)
        elif button_id == "hd-export":
            await self._export_logs(task_uuid)

    async def _retry_with_undo(self, task_uuid: str) -> None:
        """任务级重试（服务契约=新任务）+ #16 撤销倒计时：10s 内可取消新任务。"""
        try:
            created = await self.client.retry_task(task_uuid)
        except Exception as exc:
            self.app.notify(f"重试失败：{exc}", severity="error")
            return
        new_uuid = str(created.get("task_uuid", ""))
        self._undo_task = new_uuid
        self._undo_left = UNDO_WINDOW_S
        undo = self.query_one("#hd-undo", Static)
        undo.add_class("undo-on")
        self._render_undo()
        self.set_interval(1.0, self._tick_undo)

    def _render_undo(self) -> None:
        left = self._undo_left
        width = 10
        filled = round(left / UNDO_WINDOW_S * width)
        self.query_one("#hd-undo", Static).update(
            f"{design.icon('task.running')} 已重试为新任务 {str(self._undo_task)[:8]} · "
            f"[${'molten'}]{'█' * filled}{'░' * (width - filled)}[/] "
            f"撤销窗口 {left}s（u=撤销，即取消新任务）")

    async def _tick_undo(self) -> None:
        self._undo_left -= 1
        if not self.is_current:  # 抽屉已关（撤销完成/手动退出）即停表
            return
        if self._undo_left > 0:
            self._render_undo()
            return
        self.query_one("#hd-undo", Static).remove_class("undo-on")
        self.app.notify("重试已生效", severity="information")
        self.action_dismiss_drawer()

    async def _undo(self) -> None:
        """撤销：取消刚创建的新任务（pending 态可取消）。"""
        if not self._undo_task:
            return
        try:
            await self.client.cancel_task(self._undo_task)
        except Exception as exc:
            self.app.notify(f"撤销失败：{exc}", severity="error")
            return
        self.app.notify(f"已撤销重试（新任务 {self._undo_task[:8]} 已取消）",
                        severity="warning")
        self._undo_task = None
        self.action_dismiss_drawer()

    async def _cancel(self, task_uuid: str) -> None:
        try:
            await self.client.cancel_task(task_uuid)
        except Exception as exc:
            self.app.notify(f"取消失败：{exc}", severity="error")
            return
        self.app.notify("已请求取消", severity="warning")

    async def _export_logs(self, task_uuid: str) -> None:
        """导出日志到 data/exports/<uuid 前 8>.log（本地文件，如实路径回执）。"""
        try:
            data = await self.client.task_logs(task_uuid, offset=0)
        except Exception as exc:
            self.app.notify(f"导出失败：{exc}", severity="error")
            return
        lines = list((data or {}).get("lines", []))
        export_dir = Path("data") / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        path = export_dir / f"{task_uuid[:8]}.log"
        path.write_text("\n".join(lines), encoding="utf-8")
        self.app.notify(f"日志已导出：{path}", severity="information")

    def on_key(self, event) -> None:  # noqa: ANN001
        if event.key == "u" and self._undo_left > 0 and self._undo_task:
            self.run_worker(self._undo(), exclusive=True)

    def action_dismiss_drawer(self) -> None:
        self.dismiss()


class HistoryPage(VerticalScroll):
    """任务历史：chips 筛选 + DataTable + 详情抽屉。"""

    CSS = """
    #his-title { color: $ink-900; margin-top: 1; }
    #his-table { margin-top: 1; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-history")
        self.client = client

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.history')} 任务历史[/b]"
            f"  [dim]星图志 · 回车看详情 · 5s 自动刷新[/dim]", id="his-title")
        yield ChipBar(STATUS_FILTERS, id="his-filter")
        yield DataTable(id="his-table")

    def on_mount(self) -> None:
        table = self.query_one("#his-table", DataTable)
        table.add_columns("任务", "状态", "类型", "标题", "耗时", "时刻", "错误")
        table.cursor_type = "row"
        self.set_interval(REFRESH_S, self._auto_refresh)
        self.run_worker(self.refresh_table(), exclusive=True)

    def on_chip_bar_changed(self, event: ChipBar.Changed) -> None:
        if event.chip_bar.id == "his-filter":
            self.run_worker(self.refresh_table(), exclusive=True)

    async def _auto_refresh(self) -> None:
        if self.is_mounted and self.app.screen.__class__ is not HistoryDetailScreen:
            await self.refresh_table()

    async def refresh_table(self) -> None:
        if not self.is_mounted:
            return
        table = self.query_one("#his-table", DataTable)
        try:
            data = await self.client.list_tasks(page=1,
                                                status=self.query_one("#his-filter",
                                                                      ChipBar).selected)
        except Exception as exc:
            self.app.notify(f"任务列表加载失败: {exc}", severity="error")
            return
        table.clear()
        for task in (data or {}).get("items", []):
            status = str(task.get("status", "pending"))
            glyph, color = STATUS_META.get(status, ("task.pending", "ink-400"))
            table.add_row(
                str(task.get("task_uuid"))[:8],
                f"[${color}]{design.icon(glyph)} {status}[/]",
                str(task.get("task_type", "?")),
                str(task.get("title") or "-"),
                duration_text(task.get("started_at"), task.get("finished_at")),
                local_time(task.get("created_at")),
                str(task.get("error_code") or "-"),
            )

    async def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """回车打开行详情抽屉（按 uuid 前 8 位回查完整任务字典）。"""
        row_key = event.row_key.value
        if not row_key:
            return
        try:
            data = await self.client.list_tasks(page=1,
                                                status=self.query_one("#his-filter",
                                                                      ChipBar).selected)
        except Exception:
            data = {}
        task = next((t for t in (data or {}).get("items", [])
                     if str(t.get("task_uuid", "")).startswith(row_key)), None)
        if task is None:
            self.app.notify("任务详情不存在", severity="error")
            return
        detail = await self.client.task_detail(str(task["task_uuid"]))
        self.app.push_screen(HistoryDetailScreen(self.client, detail))
