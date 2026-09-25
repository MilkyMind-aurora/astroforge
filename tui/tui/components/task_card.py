# -*- coding: utf-8 -*-
"""共用任务进度卡（方案 §3.3 / V1-T.2.5，采集/解析/转换/流水线四页共用）。

数据契约：订阅 /ws/logs/{uuid}（status/progress 事件负载 {status, progress,
error_code}；log 事件取「步骤 i/N: …」行更新当前步骤行）；建卡与断线时
GET /tasks/{uuid} 兜底补拉，运行中 2s 轮询至终态。
动效勾账（§1.8，TUI 离散近似，终端无逐帧插值）：#10 进度底色前推=填充段随
进度增长、推满 card-flash 提亮 160ms；#11 完成过冲=显示值先 +8% 后回落；
#14 状态文字推进=TUI 直接换字（无逐帧位移）。
"""
from __future__ import annotations

import asyncio
import json

from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static

from tui.theme.generated import tokens as design

TERMINAL_STATUS = {"success", "failed", "canceled"}
BAR_MAX_COLS = 40      # §1.3：进度条宽 = min(终端宽-20, 40) 列
BAR_MIN_COLS = 10
OVERSHOOT_RATIO = 0.08  # #11 完成过冲 +8%
FLASH_S = 0.16          # 推满轻提亮 160ms（#10）

STATUS_META: dict[str, tuple[str, str]] = {
    "pending": ("task.pending", "ink-400"),
    "running": ("task.running", "aurora"),
    "success": ("task.success", "aurora"),
    "failed": ("task.failed", "nova"),
    "canceled": ("task.canceled", "ink-400"),
}


def bar_fill(percent: int, width: int) -> str:
    """进度条渲染：aurora 填充段 + faint 余段（填充宽随进度=底色前推 #10）。

    width ≤0 视为未布局，返回纯百分数；确定性纯函数（单测覆盖）。
    """
    percent = max(0, min(100, int(percent)))
    if width <= 0:
        return f"{percent}%"
    filled = round(percent / 100 * width)
    filled = max(0, min(width, filled))
    return f"{'█' * filled}{'░' * (width - filled)} {percent}%"


def bar_width(terminal_width: int) -> int:
    """进度条宽 = min(终端宽-20, 40)，下限 10（§1.3 TUI 间距纪律）。"""
    return max(BAR_MIN_COLS, min(terminal_width - 20, BAR_MAX_COLS))


class TaskProgressCard(Vertical):
    """任务进度卡：标题行（星符+UUID 前 8 位）+ 进度条 + 当前步骤 + 日志提示。"""

    DEFAULT_CSS = """
    TaskProgressCard { height: auto; border: round $border-subtle;
        background: $card; padding: 0 1; margin-top: 1; }
    TaskProgressCard.card-flash { border: round $aurora; }
    #card-title { color: $ink-900; }
    #card-bar { color: $aurora; }
    #card-step { color: $ink-600; }
    #card-hint { color: $ink-400; }
    """

    class Finished(Message):
        """任务到达终态（页面刷新最近任务列表用）。"""

        def __init__(self, card: "TaskProgressCard", status: str) -> None:
            super().__init__()
            self.card = card
            self.status = status

    def __init__(self, client, task_uuid: str, task_type: str) -> None:
        super().__init__(classes="task-card")
        self.client = client
        self.task_uuid = task_uuid
        self.task_type = task_type
        self._status = "pending"
        self._percent = 0
        self._shown_percent = 0     # 过冲显示值（#11）
        self._step_text = "等待调度…"
        self._settle_timer = None   # 过冲回落定时器（重复事件先取消）

    def compose(self):
        yield Static("", id="card-title")
        yield Static("", id="card-bar")
        yield Static(self._step_text, id="card-step")
        yield Static("[dim]Ctrl+` 看日志[/dim]", id="card-hint")

    def on_mount(self) -> None:
        self.run_worker(self._bootstrap(), exclusive=True)

    # ---- 数据接入 ----
    async def _bootstrap(self) -> None:
        try:
            detail = await self.client.task_detail(self.task_uuid)
        except Exception as exc:
            self.query_one("#card-step", Static).update(f"任务详情获取失败：{exc}")
            return
        self._apply(detail)
        await self._follow_ws()

    async def _follow_ws(self) -> None:
        """WS 主通道：status/progress 事件驱动；断线降级 REST 轮询。"""
        try:
            ws = await self.client.subscribe_logs(self.task_uuid)
        except Exception:
            await self._poll_rest()
            return
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                mtype = msg.get("type")
                payload = msg.get("payload") or {}
                if mtype in ("status", "progress"):
                    self._apply(payload)
                elif mtype == "log":
                    text = str(payload.get("text", ""))
                    if text.startswith("步骤"):
                        self._step_text = text
                        self._render()
        except Exception:
            if self._status not in TERMINAL_STATUS:
                await self._poll_rest()

    async def _poll_rest(self) -> None:
        """断线兜底：GET /tasks/{uuid} 2s 轮询至终态（数据冻结提示行）。"""
        while self.is_mounted and self._status not in TERMINAL_STATUS:
            await asyncio.sleep(2.0)
            try:
                detail = await self.client.task_detail(self.task_uuid)
            except Exception:
                self._step_text = "连接中断，重试补拉中…"
                self._render()
                continue
            self._apply(detail)

    # ---- 状态机 ----
    def _apply(self, payload: dict) -> None:
        status = str(payload.get("status", self._status))
        percent = int(payload.get("progress", self._percent))
        status_changed = status != self._status
        progress_changed = percent != self._percent
        self._status, self._percent = status, percent
        if payload.get("error_message"):
            self._step_text = str(payload["error_message"])
        if progress_changed and status == "running":
            self._overshoot()
        elif status_changed or progress_changed:
            self._shown_percent = percent
        self._render()
        if status in TERMINAL_STATUS:
            self._settle_flash(status == "success")
            self.post_message(self.Finished(self, status))

    def _overshoot(self) -> None:
        """#11 完成过冲：显示值先 +8% 再回落（Textual 离散近似，160ms 后落定）。"""
        if self._settle_timer is not None:
            self._settle_timer.stop()
        overshoot = min(100, round(self._percent * (1 + OVERSHOOT_RATIO)))
        self._shown_percent = max(self._shown_percent, overshoot)
        self._settle_timer = self.set_timer(FLASH_S, self._settle)

    def _settle(self) -> None:
        self._shown_percent = self._percent
        self._render()

    def _settle_flash(self, ok: bool) -> None:
        """推满/终态轻提亮一次（160ms 后回落，#10 收尾）。"""
        if not ok:
            return
        self.add_class("card-flash")
        self.set_timer(FLASH_S, lambda: self.remove_class("card-flash"))

    # ---- 渲染 ----
    def _render(self) -> None:
        if not self.is_mounted:
            return
        glyph, color = STATUS_META.get(self._status, ("task.pending", "ink-400"))
        title = (
            f"{design.icon('nav.task')} [b]{self.task_type}[/b] · "
            f"{self.task_uuid[:8]}  [${color}]{design.icon(glyph)} {self._status}[/${color}]"
        )
        self.query_one("#card-title", Static).update(title)
        self.query_one("#card-bar", Static).update(
            bar_fill(self._shown_percent, bar_width(self.app.size.width)))
        self.query_one("#card-step", Static).update(self._step_text)
