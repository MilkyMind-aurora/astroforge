# -*- coding: utf-8 -*-
"""连接引导屏（方案 §3.1 + UX P0-5）：星仔 sleeping + 启动命令卡 + 重试/一键拉起。

一键拉起：Windows 经 cmd /c scripts\\start_service.bat 后台拉起（管道捕获
stderr 供诊断卡）；持续轮询至 60s，阶段化反馈＝激活环境→端口监听→数据库
握手→就绪（真实探针：进程存活→TCP 连通→/system/health 200）；失败捕获
stderr 尾行进 nova 诊断卡。非 Windows 按方案提示手动命令。
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from tui.shell.boot import SPIN_INTERVAL_S
from tui.shell.format import seg, spinner_frame
from tui.theme.generated import tokens as design
from tui.ui.mascot import get_frame

REPO_ROOT = Path(__file__).resolve().parents[3]


class ConnectScreen(Screen):
    """连接引导屏：重试 / 一键拉起（60s 阶段化轮询 + stderr 诊断卡）。"""

    LAUNCH_TIMEOUT_S = 60.0
    POLL_INTERVAL_S = 0.5
    PHASES = ("激活环境", "端口监听", "数据库握手", "就绪")

    CSS = """
    ConnectScreen { align: center middle; background: $bg; }
    #connect-box { width: 66; padding: 1 2; border: round $border-active;
        background: $card; }
    #connect-mascot { content-align: center middle; color: $ink-600; }
    #connect-title { content-align: center middle; color: $ink-900; margin-top: 1; }
    #connect-cmd { border: round $border-subtle; background: $sunken;
        padding: 0 1; margin-top: 1; color: $ink-600; }
    #connect-phase { margin-top: 1; color: $ink-900; }
    #connect-btns { height: auto; margin-top: 1; }
    #connect-btns Button { margin-right: 1; }
    .diag-card { display: none; border: round $nova; background: $errorWashBg;
        padding: 0 1; margin-top: 1; color: $ink-900; }
    .diag-card.diag-on { display: block; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._proc: subprocess.Popen | None = None
        self._stderr_tail: deque[str] = deque(maxlen=12)
        self._launching = False
        self._frame = 0
        self._phase_done = -1            # 已完成阶段序号（-1=未开始）
        self._phase_current: str | None = None
        self._phase_started = 0.0

    def compose(self) -> ComposeResult:
        base = self._client_base()
        with Vertical(id="connect-box"):
            yield Static(get_frame("sleeping"), id="connect-mascot")
            yield Static(
                f"{seg(design.icon('status.idle'), 'nova')} "
                f"[b]Sidereal Core 未响应[/b]（{base}）", id="connect-title")
            with Vertical(id="connect-cmd"):
                yield Static("[dim]服务未启动时手动拉起：[/dim]")
                yield Static("  Windows: scripts\\start_service.bat")
                yield Static("  macOS:   bash scripts/start_service.sh")
            yield Static("", id="connect-phase")
            with Horizontal(id="connect-btns"):
                yield Button("重试连接", id="btn-retry", variant="primary")
                yield Button("一键拉起服务", id="btn-launch", variant="default")
            yield Static("", id="connect-diag", classes="diag-card")

    @staticmethod
    def _client_base() -> str:
        from tui.service_client import get_client

        return get_client().base_url

    def on_mount(self) -> None:
        self.set_interval(SPIN_INTERVAL_S, self._spin)

    # ---- 渲染助手 ----
    def _spin(self) -> None:
        self._frame += 1
        if self._phase_current is not None:
            self._render_phase()

    def _render_phase(self) -> None:
        """阶段化反馈：✓（aurora）/ 跑圈进行中 / ○ 未到（dim）。"""
        parts: list[str] = []
        for index, name in enumerate(self.PHASES):
            if index <= self._phase_done:
                parts.append(seg(f"{design.icon('task.success')} {name}", "aurora"))
            elif name == self._phase_current:
                parts.append(seg(f"{spinner_frame(self._frame)} {name}", "aurora"))
            else:
                parts.append(f"[dim]{design.icon('task.pending')} {name}[/dim]")
        waited = time.monotonic() - self._phase_started
        tail = f"  [dim]{waited:.0f}s/{self.LAUNCH_TIMEOUT_S:.0f}s[/dim]" if self._launching else ""
        self.query_one("#connect-phase", Static).update("  →  ".join(parts) + tail)

    def _set_phase(self, done: int, current: str | None) -> None:
        self._phase_done = done
        self._phase_current = current
        self._render_phase()

    def _show_diag(self, lines: list[str], title: str = "拉起失败 · stderr 尾行") -> None:
        """nova 诊断卡（UX P0-5 失败分支）：stderr 尾行原文。"""
        body = "\n".join(f"  {line}" for line in lines) or "  （无输出）"
        diag = self.query_one("#connect-diag", Static)
        diag.update(
            f"{seg(design.icon('status.error') + f' {title}', 'nova')}\n"
            f"[dim]{body}[/dim]\n"
            "[dim]修复后可再次「一键拉起」或手动运行启动命令。[/dim]"
        )
        diag.add_class("diag-on")

    def _set_buttons(self, disabled: bool) -> None:
        self.query_one("#btn-retry", Button).disabled = disabled
        self.query_one("#btn-launch", Button).disabled = disabled

    # ---- 重试 ----
    async def _retry(self) -> None:
        from tui.service_client import get_client

        self._set_buttons(True)
        self._phase_started = time.monotonic()
        self._set_phase(-1, "探活")
        try:
            await get_client().health()
        except Exception as exc:
            self._set_phase(-1, None)
            self._show_diag([f"服务仍不可达：{exc}"], title="重试失败")
        else:
            self._set_phase(3, None)
            await asyncio.sleep(SPIN_INTERVAL_S)
            self.app.pop_screen()
            return
        self._set_buttons(False)

    # ---- 一键拉起 ----
    def _launch(self) -> None:
        self._launching = True
        self._phase_started = time.monotonic()
        self._set_buttons(True)
        self._set_phase(-1, "激活环境")
        if not sys.platform.startswith("win"):
            self._launching = False
            self._set_phase(-1, None)
            self._set_buttons(False)
            self._show_diag(
                ["当前平台请手动运行：bash scripts/start_service.sh"],
                title="一键拉起暂不支持非 Windows")
            return
        bat = REPO_ROOT / "scripts" / "start_service.bat"
        if not bat.exists():
            self._launching = False
            self._set_phase(-1, None)
            self._set_buttons(False)
            self._show_diag([f"未找到 {bat}"], title="一键拉起失败")
            return
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        # CREATE_NO_WINDOW=0x08000000：后台拉起，stderr 管道留诊断；参数为仓库内
        # 固定脚本路径列表（cmd /c 批处理），不经 shell 字符串拼接
        self._proc = subprocess.Popen(
            [comspec, "/c", str(bat)], cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=0x08000000,
        )
        self._stderr_tail.clear()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self.run_worker(self._poll_launch(), exclusive=True)

    def _drain_stderr(self) -> None:
        """后台线程读 stderr 尾行（deque 只留最后 12 行，供失败诊断卡）。"""
        stream = self._proc.stderr if self._proc else None
        if stream is None:
            return
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip()
                if line:
                    self._stderr_tail.append(line)
        except Exception:  # 进程退出时管道关闭属正常
            pass

    def _host_port(self) -> tuple[str, int]:
        parsed = urlparse(self._client_base())
        return parsed.hostname or "127.0.0.1", parsed.port or 80

    async def _poll_launch(self) -> None:
        from tui.service_client import get_client

        host, port = self._host_port()
        client = get_client()
        while time.monotonic() - self._phase_started < self.LAUNCH_TIMEOUT_S:
            # 阶段 1：激活环境（启动进程存活即过；退出即失败诊断）
            if self._proc is not None and self._proc.poll() is not None:
                self._launching = False
                self._set_phase(-1, None)
                self._set_buttons(False)
                self._show_diag(list(self._stderr_tail), title="启动进程已退出 · stderr 尾行")
                return
            if self._phase_done < 0:
                self._set_phase(0, "端口监听")
            # 阶段 2：端口监听（TCP 真连）
            try:
                _reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=1.0)
                writer.close()
                if self._phase_done < 1:
                    self._set_phase(1, "数据库握手")
            except Exception:
                await asyncio.sleep(self.POLL_INTERVAL_S)
                continue
            # 阶段 3+4：/system/health 200（内部做 DB ping）→ 就绪
            try:
                health = await client.health()
            except Exception:
                await asyncio.sleep(self.POLL_INTERVAL_S)
                continue
            self._set_phase(3, None)
            if not health.get("db"):
                self.app.notify("服务已就绪，但数据库未连接（历史/设置暂不可用）",
                                severity="warning")
            await asyncio.sleep(SPIN_INTERVAL_S)
            self._launching = False
            self.app.pop_screen()
            return
        # 60s 超时（UX P0-5：持续轮询至 60s 后给诊断卡）
        self._launching = False
        self._set_phase(-1, None)
        self._set_buttons(False)
        tail = list(self._stderr_tail)
        self._show_diag(
            tail or [f"{self.LAUNCH_TIMEOUT_S:.0f}s 内未见端口监听/健康应答（stderr 无输出）"],
            title="拉起超时 · 诊断信息")

    # ---- 事件 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-retry":
            await self._retry()
        elif event.button.id == "btn-launch":
            self._launch()
