# -*- coding: utf-8 -*-
"""启动屏（方案 §3.1）：银河渐变横幅 + ASCII 星仔 + 标语 + 探活跑圈。"""
from __future__ import annotations

import asyncio
import time

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Static

from tui.shell.format import seg, spinner_frame
from tui.theme.generated import tokens as design
from tui.ui.mascot import get_frame

TAGLINE = "AstroForge — Forging Order from Stellar Chaos."
SPIN_INTERVAL_S = 0.3  # 跑圈 4 帧 × 0.3s = 1.2s 一圈（#17 dur-loop 档）


class BootScreen(Screen):
    """启动屏：银河渐变横幅（白名单 tui_boot_banner，fg 按行三停驻色）
    + ASCII 星仔 + 标语；探活期间跑圈字符（#17）；超时 5s 转连接引导屏。"""

    TIMEOUT_S = 5.0

    def __init__(self) -> None:
        super().__init__()
        self._frame = 0
        self._message = "正在探活 Sidereal Core…"

    CSS = """
    BootScreen { align: center middle; background: $bg; }
    #boot-box { width: auto; height: auto; align: center middle; padding: 2 4; }
    #boot-banner { content-align: center middle; color: $ink-900; }
    #boot-mascot { content-align: center middle; color: $molten; margin-top: 1; }
    #boot-tagline { content-align: center middle; margin-top: 1; }
    #boot-status { content-align: center middle; color: $ink-600; margin-top: 1; }
    """

    @staticmethod
    def _banner() -> list[str]:
        """三行渐层块：行色取 GALAXY 夜档三停驻（设计白名单 tui_boot_banner）。"""
        stops = design.GALAXY["dark"]
        rows = [
            f"▓▓▓  {design.icon('nav.home')} ASTROFORGE · 衍星台  ▓▓▓",
            "▒▒▒  星舰工作台 · Sidereal Core  ▒▒▒",
            "░░░  Forging Order from Stellar Chaos  ░░░",
        ]
        return [f"[{stop}]{row}[/{stop}]" for row, stop in zip(rows, stops)]

    def compose(self) -> ComposeResult:
        with Vertical(id="boot-box"):
            yield Static("\n".join(self._banner()), id="boot-banner")
            yield Static(get_frame("idle"), id="boot-mascot")
            yield Static(f"[i][dim]{TAGLINE}[/dim][/i]", id="boot-tagline")
            yield Static("", id="boot-status")

    def on_mount(self) -> None:
        self.set_interval(SPIN_INTERVAL_S, self._spin)
        self.run_worker(self._probe(), exclusive=True)

    def _spin(self) -> None:
        """跑圈字符 + 当前探活文案（唯一循环动画位：探活期间）。"""
        self._frame += 1
        self.query_one("#boot-status", Static).update(
            f"{seg(spinner_frame(self._frame), 'aurora')} {self._message}")

    def _message_set(self, text: str) -> None:
        self._message = text

    async def _probe(self) -> None:
        from tui.service_client import get_client
        from tui.shell.connect import ConnectScreen

        deadline = time.monotonic() + self.TIMEOUT_S
        client = get_client()
        while True:
            try:
                await client.health()
            except Exception:
                if time.monotonic() >= deadline:
                    self._message_set("探活超时，转入连接引导…")
                    await asyncio.sleep(SPIN_INTERVAL_S * 2)
                    self.app.switch_screen(ConnectScreen())
                    return
                await asyncio.sleep(0.5)
                continue
            self._message_set("氢料就位，进入工作台…")
            await asyncio.sleep(SPIN_INTERVAL_S)
            self.app.pop_screen()
            return
