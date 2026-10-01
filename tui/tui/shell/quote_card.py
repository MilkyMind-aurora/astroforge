# -*- coding: utf-8 -*-
"""星仔语录卡（L12 侧栏彩蛋行点击弹出）：静态卡 + 随机台词，任意键关闭。

台词经 mascot.get_quote（用户主动触发位，不计 dispatch 调度限额）；静态渲染，
无循环动画（终端红线）。
"""
from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from tui.ui.mascot import get_frame, get_quote


class QuoteCardScreen(ModalScreen):
    """星仔语录卡：☄ 彩蛋入口弹出，任意键/Esc 关闭。"""

    CSS = """
    QuoteCardScreen { align: center middle; background: $bg 60%; }
    #quote-box { width: 48; border: round $aurora; background: $card; padding: 1 2; }
    #quote-mascot { content-align: center middle; color: $molten; }
    #quote-line { content-align: center middle; color: $ink-900; margin-top: 1; }
    #quote-hint { content-align: center middle; color: $ink-400; margin-top: 1; }
    """

    def __init__(self, event: str = "meteor") -> None:
        super().__init__()
        self._event = event

    def compose(self) -> ComposeResult:
        with Vertical(id="quote-box"):
            yield Static(get_frame("happy"), id="quote-mascot")
            yield Static(
                f"[i][${'molten'}]星仔 ·[/] {get_quote(self._event)}[/i]",
                id="quote-line")
            yield Static("[dim]任意键关闭[/dim]", id="quote-hint")

    def on_key(self, event: events.Key) -> None:
        if self.is_current:
            self.dismiss()
