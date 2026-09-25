# -*- coding: utf-8 -*-
"""AstroForge TUI 星舰壳层（方案 §3.1/§3.2/§3.4，MF1）。

结构：启动屏（银河横幅+星仔+探活跑圈）→ 主壳（星轨侧栏+主内容区+底部状态栏）
→ 连接引导屏（一键拉起 60s 阶段化轮询 + stderr 尾行诊断卡）。
快捷键：1-8 切页（30ms 去抖）· / 命令面板 · Ctrl+Shift+A 或 A 星伴 · Ctrl+` 日志 ·
f 文件浏览器 · q 退出。
数据：/ws/monitor 1s 驱动状态栏与监控看板（MonitorState 共享态）；/system/health +
/system/env-check 5s 轮询（侧栏健康点与首页体检同源）；内存阈值取 config-summary。
纪律：颜色一律 $语义变量（生成物 tokens.tcss/css_variables，§3.7 门禁①）；星符一律
design.icon()（门禁④）；终端无连续背景动画（性能红线，仅断连指示闪烁与跑圈字符）。
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from rich.cells import cell_len
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hits, Provider
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import Button, Input, Static

from tui.pages.converter import ConverterPage
from tui.pages.history import HistoryPage
from tui.pages.home import HomePage
from tui.pages.monitor import MonitorPage, MonitorState, mem_severity
from tui.pages.parser import ParserPage
from tui.pages.pipeline import PipelinePage
from tui.pages.settings import SettingsPage
from tui.pages.spider import SpiderPage
from tui.service_client import ServiceClient, get_client
from tui.theme import astro_theme
from tui.theme.generated import tokens as design
from tui.ui.file_browser import FileBrowserScreen
from tui.ui.mascot import get_frame

TAGLINE = "AstroForge — Forging Order from Stellar Chaos."
VERSION = "Sidereal Core v0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]

# 8 页导航（key, 星符语义名, 标签）——数字键 1-8 直达（§3.1）
PAGES: list[tuple[str, str, str]] = [
    ("home", "nav.home", "首页"),
    ("spider", "nav.spider", "采集中心"),
    ("parser", "nav.parser", "解析中心"),
    ("converter", "nav.converter", "转换中心"),
    ("pipeline", "nav.pipeline", "流水线"),
    ("monitor", "nav.monitor", "监控看板"),
    ("history", "nav.history", "任务历史"),
    ("settings", "nav.settings", "设置"),
]

# 模块健康点 ← env-check 项名子串匹配（与首页体检同源；空元组=聚合全部项）
NAV_HEALTH: dict[str, tuple[str, ...]] = {
    "home": (),
    "spider": ("Chromium",),
    "parser": ("MinerU",),
    "converter": ("anydoc", "DOCX 模板"),
    "pipeline": ("Conda",),
    "monitor": ("PostgreSQL",),
    "history": ("PostgreSQL",),
    "settings": ("PostgreSQL",),
}

# 导航键去抖（tokens.yaml interaction.keyboard.nav_debounce_ms，§1.7）
NAV_DEBOUNCE_S = design.INTERACTION["keyboard"]["nav_debounce_ms"] / 1000
# 侧栏胶囊滑移（§1.8 #4 变体，motion.tui.t_press）
T_PRESS_S = design.MOTION_TUI["t_press"]["duration_ms"] / 1000
T_PRESS_EASING = design.MOTION_TUI["t_press"]["easing"]
SPIN_INTERVAL_S = 0.3  # 跑圈 4 帧 × 0.3s = 1.2s 一圈（#17 dur-loop 档）


def _spinner_frame(frame: int) -> str:
    """跑圈字符（icons.yaml misc.spinner_f1..f4，#17 边缘高亮跑圈）。"""
    return design.icon(f"misc.spinner_f{frame % 4 + 1}")


def _seg(text: str, color: str) -> str:
    """状态栏色段（$语义变量；[/] 自动闭合）。"""
    return f"[${color}]{text}[/]"


class ForgeCommands(Provider):
    """全局命令面板（§3.6）：/ 唤起，输入防抖 150ms（Textual Provider 自带）。"""

    def _commands(self) -> list[tuple[str, object]]:
        app = self.app
        items: list[tuple[str, object]] = [
            (f"{design.icon(icon)} {index + 1} {label}",
             lambda idx=index: app.switch_page(idx))
            for index, (_key, icon, label) in enumerate(PAGES)
        ]
        items += [
            ("打开文件浏览器", app.action_file_browser),
            ("打开日志面板", app.action_toggle_log),
            ("星伴 AI", app.action_ai_panel),
            ("刷新体检", app.action_refresh_env),
            (f"主题：{astro_theme.DEFAULT_THEME}（夜·默认）",
             lambda: app.action_set_theme(astro_theme.DEFAULT_THEME)),
            ("主题：dawn（晨昏·昼）", lambda: app.action_set_theme("dawn")),
            ("重连服务核心", app.reconnect),
        ]
        return items

    async def discover(self) -> Hits:
        for title, callback in self._commands():
            yield DiscoveryHit(title, callback)

    async def search(self, query: str) -> Hits:
        for title, callback in self._commands():
            if query.lower() in title.lower():
                yield DiscoveryHit(title, callback)


class BootScreen(Screen):
    """启动屏（§3.1）：银河渐变横幅（白名单 tui_boot_banner，fg 按行三停驻色）
    + ASCII 星仔 + 标语；探活期间跑圈字符（#17）；超时 5s 转连接引导屏。"""

    TIMEOUT_S = 5.0

    def __init__(self) -> None:
        super().__init__()
        self._frame = 0
        self._message = "正在探活 Sidereal Core…"

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
            f"{_seg(_spinner_frame(self._frame), 'aurora')} {self._message}")

    def _message_set(self, text: str) -> None:
        self._message = text

    async def _probe(self) -> None:
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


class ConnectScreen(Screen):
    """连接引导屏（§3.1 + UX P0-5）：星仔 sleeping + 启动命令卡 + 重试/一键拉起。

    一键拉起：Windows 经 cmd /c scripts\\start_service.bat 后台拉起（管道捕获
    stderr 供诊断卡）；持续轮询至 60s，阶段化反馈＝激活环境→端口监听→数据库
    握手→就绪（真实探针：进程存活→TCP 连通→/system/health 200）；失败捕获
    stderr 尾行进 nova 诊断卡。非 Windows 按方案提示手动命令。
    """

    LAUNCH_TIMEOUT_S = 60.0
    POLL_INTERVAL_S = 0.5
    PHASES = ("激活环境", "端口监听", "数据库握手", "就绪")

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
        base = get_client().base_url
        with Vertical(id="connect-box"):
            yield Static(get_frame("sleeping"), id="connect-mascot")
            yield Static(
                f"{_seg(design.icon('status.idle'), 'nova')} "
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
                parts.append(_seg(f"{design.icon('task.success')} {name}", "aurora"))
            elif name == self._phase_current:
                parts.append(_seg(f"{_spinner_frame(self._frame)} {name}", "aurora"))
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
            f"{_seg(design.icon('status.error') + f' {title}', 'nova')}\n"
            f"[dim]{body}[/dim]\n"
            "[dim]修复后可再次「一键拉起」或手动运行启动命令。[/dim]"
        )
        diag.add_class("diag-on")

    def _set_buttons(self, disabled: bool) -> None:
        self.query_one("#btn-retry", Button).disabled = disabled
        self.query_one("#btn-launch", Button).disabled = disabled

    # ---- 重试 ----
    async def _retry(self) -> None:
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
        parsed = urlparse(get_client().base_url)
        return parsed.hostname or "127.0.0.1", parsed.port or 80

    async def _poll_launch(self) -> None:
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


class NavLink(Static):
    """侧栏导航项（高 3 行，§3.1）：星符+数字键+标签，右缘健康点由 Sidebar 渲染。"""

    def __init__(self, page_index: int, icon_name: str, label: str) -> None:
        super().__init__(classes="nav-link")
        self.page_index = page_index
        self.icon_name = icon_name
        self.label = label
        self.tooltip = f"{page_index + 1} {label}"


class Sidebar(Vertical):
    """星轨侧栏（§3.1）：选中极光胶囊滑移（#4）+ 模块健康点 + 窄屏折叠图标轨。

    胶囊 = container 底 + aurora 左竖条，绝对定位于导航项之下层，页切换时
    offset 以 T_PRESS 滑移；选中项文字 ink-900 加粗。窄屏（<100 列）折叠为
    10 列图标轨（tooltip 提示）。
    """

    def __init__(self) -> None:
        super().__init__(id="sidebar")
        self._narrow = False

    def compose(self) -> ComposeResult:
        yield Static(f"{design.icon('nav.home')} 星轨导航", id="sidebar-title")
        yield Static("", id="nav-capsule")
        for index, (_key, icon, label) in enumerate(PAGES):
            yield NavLink(index, icon, label)
        yield Static("─" * 8, id="nav-sep", classes="nav-sep")
        ai_entry = Static(f"{design.icon('ai.idle')} 星伴 AI", id="nav-ai")
        ai_entry.tooltip = "Ctrl+Shift+A 或 A 唤起星伴"
        yield ai_entry

    # ---- 渲染 ----
    def _inner_width(self) -> int:
        return (10 if self._narrow else 26) - 2  # 减 NavLink 左右 padding

    def _dot(self, key: str) -> tuple[str, str]:
        """模块健康点 → (星符语义名, 色 token)：与首页体检同源（env_items）。"""
        items = self.app.env_items
        wanted = NAV_HEALTH.get(key, ())
        if not items:
            return "status.idle", "ink-400"
        matched = ([it for it in items
                    if any(w in str(it.get("name", "")) for w in wanted)]
                   if wanted else list(items))
        if not matched:
            return "status.idle", "ink-400"
        if all(it.get("ok") for it in matched):
            return "status.ok", "aurora"
        from tui.pages.home import check_glyph  # 局部导入避免 pages↔app 环

        return check_glyph(next(it for it in matched if not it.get("ok")))

    def _refresh_items(self) -> None:
        width = self._inner_width()
        for link in self.query(NavLink):
            key = PAGES[link.page_index][0]
            dot_icon, dot_color = self._dot(key)
            dot = _seg(design.icon(dot_icon), dot_color)
            glyph = design.icon(link.icon_name)
            if self._narrow:
                pad = max(1, width - 1)
                link.update(f"{glyph}{' ' * pad}{dot}")
            else:
                plain = f"{glyph} {link.page_index + 1} {link.label}"
                pad = max(1, width - cell_len(plain) - 1)
                link.update(f"{plain}{' ' * pad}{dot}")
        if self._narrow:
            self.query_one("#nav-ai", Static).update(
                f"{design.icon('ai.idle')}{' ' * (width - 1)}{design.icon('ai.fallback')}")
        else:
            self.query_one("#nav-ai", Static).update(
                f"{design.icon('ai.idle')} 星伴 AI  [dim]Ctrl+Shift+A[/dim]")

    def _refresh_capsule(self) -> None:
        """胶囊定位：标题 2 行 + 索引 × 3 行（NavLink 高度固定 3）。"""
        y = 2 + self.app.current_page_index * 3
        capsule = self.query_one("#nav-capsule", Static)
        for index, link in enumerate(self.query(NavLink)):
            link.set_class(index == self.app.current_page_index, "selected")
        capsule.styles.offset = (0, y)

    # ---- 状态入口（app 调用）----
    def set_page(self, index: int) -> None:
        for link_i, link in enumerate(self.query(NavLink)):
            link.set_class(link_i == index, "selected")
        capsule = self.query_one("#nav-capsule", Static)
        # #4 选中胶囊滑移：offset 动画 T_PRESS（in_out_cubic）
        capsule.animate("offset", (0, 2 + index * 3), duration=T_PRESS_S,
                        easing=T_PRESS_EASING)

    def set_health(self) -> None:
        self._refresh_items()

    def set_narrow(self, narrow: bool) -> None:
        if narrow == self._narrow:
            return
        self._narrow = narrow
        self.set_class(narrow, "narrow")
        self._refresh_items()

    def on_mount(self) -> None:
        self._refresh_items()
        self._refresh_capsule()

    def on_click(self, event: events.Click) -> None:
        control = event.control
        if isinstance(control, NavLink):
            self.app.switch_page(control.page_index)
        elif isinstance(control, Widget) and control.id == "nav-ai":
            self.app.action_ai_panel()


class StatusBar(Static):
    """底部状态栏（§3.1，1 行全宽）：WS /ws/monitor 1s 驱动、500ms 刷新节流。

    ●已连接（aurora）/ ◌重连中（nova，仅断连时 1Hz 闪烁——状态反馈而非背景动画）；
    内存 used/totalGB（>warn 熔金 / >crit nova）；任务运行数；AI；时刻；版本代号。
    <80 列裁剪中间段仅留连接态与时间。
    """

    def on_mount(self) -> None:
        self._last_line = ""
        self._blink = False
        self.set_interval(0.5, self._tick)

    def _tick(self) -> None:
        app = self.app
        state = app.monitor_state
        sample = state.get("sample")
        narrow = app.size.width < 80
        segments: list[str] = []
        # 连接态
        if state.get("ws_connected"):
            segments.append(_seg(f"{design.icon('status.ok')} 已连接", "aurora"))
        else:
            self._blink = not self._blink
            mark = design.icon("status.idle") if self._blink else " "
            segments.append(_seg(f"{mark} 重连中 · 数据冻结", "nova"))
        if not narrow:
            # 内存（阈值：config-summary monitor 段，缺省 10/12GB）
            if sample:
                used = float(sample.get("mem_used_gb", 0.0))
                percent = float(sample.get("mem_percent", 0.0))
                total = used / (percent / 100) if percent > 0 else 0.0
                color = mem_severity(used, state["warn_gb"], state["crit_gb"])
                total_txt = f"{total:.0f}" if total > 0 else "?"
                segments.append(
                    f"内存 {_seg(f'{used:.1f}/{total_txt}GB', color)}")
            else:
                segments.append("[dim]内存 --[/dim]")
            running = int(state.get("running_count", 0))
            if running:
                segments.append(
                    f"任务 {running} 运行 {_seg(design.icon('task.running'), 'aurora')}")
            else:
                segments.append(f"[dim]任务 0 待命 {design.icon('task.pending')}[/dim]")
            segments.append(
                _seg(f"AI {design.icon('ai.idle')}", "nebula"))
        segments.append(datetime.now().strftime("%H:%M"))
        if not narrow:
            version = str((app.health_data or {}).get("version", "")) or VERSION
            segments.append(f"[dim]{version}[/dim]")
            segments.append("[dim]/ 命令 · q 退出[/dim]")
        line = " · ".join(segments)
        if line != self._last_line:  # 内容不变不重绘（节流纪律）
            self._last_line = line
            self.update(line)


class LogScreen(ModalScreen):
    """日志面板（方案 §3.6 MF1 保形：底部抽屉化 + token 配色；MF2 重写 RichLog 流式）。
    自动订阅最近运行中任务的 WS 日志流。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self._ws = None

    def compose(self) -> ComposeResult:
        with Vertical(id="log-box"):
            yield Static(
                f"{design.icon('status.hint')} 日志面板（订阅最近运行中任务）", id="log-title")
            yield Static("正在查找运行中的任务…", id="log-body")
            yield Button("关闭 (Esc)", id="log-close", variant="default")

    def on_mount(self) -> None:
        self.run_worker(self._follow(), exclusive=True)

    async def _follow(self) -> None:
        body = self.query_one("#log-body", Static)
        try:
            task = await self.client.running_task()
        except Exception as exc:
            body.update(build_error_mark("查询失败", str(exc)))
            return
        if task is None:
            body.update("[dim]当前没有运行中的任务。启动任务后这里会实时滚动其日志。[/dim]")
            return
        task_uuid = task["task_uuid"]
        buffer = f"[dim]已连接 ws/logs/{task_uuid}[/dim]\n"  # 本地累积（Static 无 renderable）
        body.update(buffer)
        try:
            self._ws = await self.client.subscribe_logs(task_uuid)
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    payload = msg.get("payload", {})
                    text = payload.get("text") or msg.get("type", "")
                except json.JSONDecodeError:
                    text = str(raw)
                buffer += f"\n{text}"
                body.update(buffer)
        except Exception as exc:
            buffer += f"\n{build_error_mark('日志流断开', str(exc))}"
            body.update(buffer)

    def on_key(self, event) -> None:  # noqa: ANN001
        if event.key == "escape":
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-close":
            self.dismiss()

    def on_unmount(self) -> None:
        if self._ws is not None:
            asyncio.create_task(self._ws.close())


def build_error_mark(head: str, detail: str) -> str:
    """nova 色错误行（token 变量，统一页面错误文案格式）。"""
    return f"{_seg(design.icon('status.error') + ' ' + head, 'nova')} {detail}"


class AiPanel(ModalScreen):
    """星伴 AI（方案 §3.6；MF1 保形换 token 配色，MF2 重写右抽屉+合批流式）。"""

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self._busy = False

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-box"):
            yield Static(
                f"{_seg(design.icon('ai.idle'), 'nebula')} [b]星伴 AI[/b]"
                f"  [dim]Sidereal 本地引擎[/dim]", id="ai-title")
            placeholder = Static(
                "输入自然语言，星伴会解析为任务指令并自动执行。\n"
                "示例：帮我爬取 https://example.com 转成 Markdown")
            yield VerticalScroll(placeholder, id="ai-out")
            yield Static("", id="ai-status")
            yield Input(placeholder="输入消息，回车发送", id="ai-in")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text or self._busy:
            return
        self._busy = True
        event.input.value = ""
        self.run_worker(self._stream_chat(text), exclusive=False)

    async def _stream_chat(self, message: str) -> None:
        """WS /ws/ai 流式对话：ai_delta 增量渲染（12 帧节流），ai_done 指令卡。"""
        out = self.query_one("#ai-out Static", Static)
        status = self.query_one("#ai-status", Static)
        status.update("连接流式通道…")
        import websockets

        base = self.client.base_url.replace("http", "ws")
        try:
            async with websockets.connect(
                f"{base}/ws/ai?token={self.client.token}"
            ) as ws:
                await ws.send(json.dumps({"message": message}, ensure_ascii=False))
                chunks: list[str] = []
                frame_count = 0
                while True:
                    frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
                    ftype = frame.get("type")
                    if ftype == "ai_delta":
                        chunks.append(frame["payload"].get("text", ""))
                        frame_count += 1
                        status.update(f"生成中… {len(chunks)} 段")
                        if frame_count % 12 == 0:  # 节流刷新，避免每帧重排
                            out.update(f"[你] {message}\n\n[星伴] {''.join(chunks)}")
                    elif ftype == "ai_done":
                        payload = frame["payload"]
                        self._render_done(out, message, payload)
                        status.update("")
                        return
                    elif ftype == "ai_error":
                        err = frame["payload"].get("message", "引擎错误")
                        out.update(f"[你] {message}\n\n{build_error_mark('星伴', err)}")
                        status.update("")
                        return
        except Exception as exc:
            status.update("")
            out.update(f"[你] {message}\n\n{build_error_mark('流式通道失败', str(exc))}")
        finally:
            self._busy = False

    def _render_done(self, out: Static, message: str, payload: dict) -> None:
        """ai_done：最终回复 + 指令任务卡片。"""
        lines = [f"[你] {message}", "", f"[星伴] {payload.get('reply', '')}"]
        instruction = payload.get("instruction")
        if instruction:
            task_type = instruction.get("task_type", "?")
            params = instruction.get("params", {})
            key_param = params.get("url") or params.get("input_path") or params.get("pipeline") or ""
            lines += [
                "",
                f"{_seg(design.icon('nav.task') + ' 已解析任务', 'hydrogen')}"
                f" {task_type}  [dim]{str(key_param)[:40]}[/dim]",
            ]
            if payload.get("task_uuid"):
                created = _seg(
                    design.icon("task.success") + " 已创建任务 "
                    + str(payload["task_uuid"])[:8], "aurora")
                lines.append(f"{created}（Ctrl+` 看日志）")
            if payload.get("notice"):
                lines.append(_seg(payload["notice"], "molten"))
        out.update("\n".join(lines))


class TooSmallOverlay(Static):
    """窗口过小覆盖层（§3.7 边界：<80×24 给提示页；absolute 覆盖全屏）。"""


class AstroForgeApp(App):
    """AstroForge TUI 主壳：导航/主题/面板/快捷键 + 共享监控态。"""

    TITLE = "AstroForge 衍星台"
    SUB_TITLE = TAGLINE
    CSS_PATH = "theme/generated/tokens.tcss"  # 生成物工具类（.c-*/.bg-*/.border-*）
    # 壳层样式：颜色/边框一律 $语义变量（tokens.css_variables 注入，§3.7 门禁①）
    CSS = """
    #app-header { dock: top; height: 1; background: $card; color: $ink-900;
        padding: 0 2; }
    #main { height: 1fr; }

    /* ---- 星轨侧栏（§3.1：宽 26 列；胶囊层在下、导航项层在上）---- */
    #sidebar {
        width: 26;
        background: $bg;
        border-right: solid $stroke;
        layers: capsule items;
    }
    #sidebar.narrow { width: 10; }
    #sidebar-title { height: 2; padding: 1 1 0 1; color: $ink-600; }
    #nav-capsule {
        position: absolute;
        offset-x: 0;
        offset-y: 0;
        width: 100%;
        height: 3;
        background: $container;
        border-left: thick $aurora;
        layer: capsule;
    }
    .nav-link { height: 3; padding: 0 1; color: $ink-600; layer: items; }
    .nav-link.selected { color: $ink-900; text-style: bold; }
    .nav-sep { height: 1; color: $faint; padding: 0 1; }
    #nav-ai { height: 3; padding: 0 1; color: $ink-600; layer: items; }
    #nav-ai:hover { background: $containerPressed; }

    /* ---- 主内容区与状态栏 ---- */
    #content { padding: 1 2; }
    #status-bar { dock: bottom; height: 1; background: $card; color: $ink-600;
        padding: 0 2; border-top: solid $faint; }
    #too-small { display: none; position: absolute; offset-x: 0; offset-y: 0;
        width: 100%; height: 100%; background: $bg; color: $warning;
        content-align: center middle; }
    #too-small.too-small-on { display: block; }

    /* ---- 启动屏（§3.1）---- */
    BootScreen { align: center middle; background: $bg; }
    #boot-box { width: auto; height: auto; align: center middle; padding: 2 4; }
    #boot-banner { content-align: center middle; color: $ink-900; }
    #boot-mascot { content-align: center middle; color: $molten; margin-top: 1; }
    #boot-tagline { content-align: center middle; margin-top: 1; }
    #boot-status { content-align: center middle; color: $ink-600; margin-top: 1; }

    /* ---- 连接引导屏（聚焦盒=aurora，V1.2-1 盒式语言）---- */
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

    /* ---- 星伴 AI（MF1 保形换 token；MF2 重写右抽屉+合批流式）---- */
    AiPanel { align: right middle; }
    #ai-box { width: 60; height: 80%; padding: 1 2; border-left: thick $nebula;
        background: $card; }
    #ai-title { color: $ink-900; }
    #ai-out { height: 1fr; margin-bottom: 1; }
    #ai-status { height: 1; color: $ink-600; }

    /* ---- 日志面板（MF1 保形：底部抽屉化；MF2 重写 RichLog 流式）---- */
    LogScreen { align: center bottom; }
    #log-box { width: 100%; height: 60%; border-top: solid $stroke;
        background: $card; padding: 1 2; }
    #log-title { color: $ink-900; }
    #log-body { height: 1fr; overflow-y: auto; color: $ink-600; }

    /* ---- 首页（§3.2：快捷 chips 胶囊 + 合规行）---- */
    #home-chips { height: auto; margin-top: 1; }
    #home-chips Button { margin-right: 1; min-width: 10; background: $container;
        color: $ink-600; border: none; text-align: center; }
    #home-chips Button:hover { background: $containerPressed; color: $ink-900; }
    #home-compliance { color: $ink-400; margin-top: 1; }

    /* ---- 监控看板（§3.4）---- */
    #mon-sparks { height: 6; margin-top: 1; }
    #mon-sparks Sparkline { width: 1fr; }
    #mon-range { layout: horizontal; height: auto; margin-top: 1; }
    #mon-alerts { height: 4; margin-top: 0; }
    #mon-alerts.alerted { background: $alertWashBg; }
    #mon-procs { margin-top: 1; height: auto; max-height: 12; }

    /* ---- 解析/转换中心（表单卡）---- */
    .par-axis-input, #conv-tpl { margin-bottom: 1; }
    #conv-tpl { height: 6; border: round $border-subtle; background: $sunken; }
    """
    COMMANDS = App.COMMANDS | {ForgeCommands}
    BINDINGS = [
        Binding("1", "page(0)", "首页", show=False),
        Binding("2", "page(1)", "采集", show=False),
        Binding("3", "page(2)", "解析", show=False),
        Binding("4", "page(3)", "转换", show=False),
        Binding("5", "page(4)", "流水线", show=False),
        Binding("6", "page(5)", "监控", show=False),
        Binding("7", "page(6)", "历史", show=False),
        Binding("8", "page(7)", "设置", show=False),
        Binding("/", "command_palette", "命令面板"),
        Binding("ctrl+shift+a", "ai_panel", "星伴 AI"),
        Binding("a", "ai_panel", show=False),
        Binding("ctrl+grave", "toggle_log", "日志"),
        Binding("f", "file_browser", "文件"),
        Binding("q", "quit", "退出"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # 监控共享态（app 层 WS worker 写入，状态栏/监控页共读；阈值默认 10/12GB）
        self.monitor_state = MonitorState.create(warn_gb=10.0, crit_gb=12.0)
        self.health_data: dict | None = None
        self.env_items: list[dict] = []
        self.service_error: str | None = None
        self._current_page = "home"
        self._last_nav = 0.0
        self._thresholds_loaded = False
        for theme in astro_theme.ASTRO_THEMES.values():
            self.register_theme(theme)

    @property
    def current_page_index(self) -> int:
        for index, (key, _icon, _label) in enumerate(PAGES):
            if key == self._current_page:
                return index
        return 0

    def get_css_variables(self) -> dict[str, str]:
        """注入星空语义变量（$aurora/$card/$border-normal…）。

        App.__init__ 解析 CSS 时自定义主题尚未注册（Textual 先用内建
        textual-dark 变量校验），此处保证 $语义变量全时可解析；主题热切后
        变量随 self.theme 换档（§1.5 CSS 变量化）。
        """
        variables = super().get_css_variables()
        name = self.theme if self.theme in design.THEMES else design.DEFAULT_THEME
        variables.update(design.css_variables(name))
        variables.update({
            "border-subtle": design.BORDER_LEVELS["subtle"],
            "border-normal": design.BORDER_LEVELS["normal"],
            "border-active": design.BORDER_LEVELS["active"],
            "thinking-opacity": str(design.THINKING_OPACITY),
        })
        return variables

    def compose(self) -> ComposeResult:
        yield Static(
            f"{_seg(design.icon('nav.home'), 'aurora')} [b]衍星台 AstroForge[/b]"
            f"  [dim]{VERSION}[/dim]", id="app-header")
        with Horizontal(id="main"):
            yield Sidebar()
            with Vertical(id="content"):
                yield HomePage(get_client(), self)
        yield StatusBar(id="status-bar")
        yield TooSmallOverlay(
            f"{design.icon('status.warn')} 窗口过小（<80×24）——请拉大终端窗口",
            id="too-small")

    def on_mount(self) -> None:
        self.theme = astro_theme.DEFAULT_THEME  # 默认 deep-space（夜）
        self.run_worker(self._health_loop(), group="health", exclusive=True)
        self.run_worker(self._monitor_loop(), group="monitor", exclusive=True)
        self.run_worker(self._running_loop(), group="running", exclusive=True)
        self.set_interval(0.3, self._check_size)  # 尺寸哨兵：属性直读，代价可忽略
        self._check_size()
        self.push_screen(BootScreen())

    # ---- 尺寸边界（§3.7：<80×24 提示层；<100 列侧栏折叠；<80 列状态栏裁剪）----
    def _check_size(self) -> None:
        size = self.size
        small = size.width < 80 or size.height < 24
        try:
            overlay = self.query_one("#too-small", TooSmallOverlay)
            overlay.set_class(small, "too-small-on")
        except Exception:  # 组合未挂载完成
            pass
        try:
            self.query_one(Sidebar).set_narrow(size.width < 100)
        except Exception:
            pass

    # ---- 健康轮询（侧栏健康点与首页体检同源）----
    async def _health_loop(self) -> None:
        client = get_client()
        while True:
            try:
                self.health_data = await client.health()
                self.service_error = None
                summary = await client.env_check()
                self.env_items = list(summary.get("items", []))
                if not self._thresholds_loaded:
                    self._thresholds_loaded = True
                    await self._load_thresholds(client)
            except Exception as exc:
                self.service_error = str(exc)
            self._sync_health_ui()
            await asyncio.sleep(5.0)

    async def _load_thresholds(self, client: ServiceClient) -> None:
        """内存阈值取 config-summary monitor 段（设置页可改，>warn 熔金 >crit nova）。"""
        try:
            summary = (await client.config_summary()) or {}
            monitor = summary.get("monitor", {})
            self.monitor_state["warn_gb"] = float(
                monitor.get("memory_warning_gb", self.monitor_state["warn_gb"]))
            self.monitor_state["crit_gb"] = float(
                monitor.get("memory_critical_gb", self.monitor_state["crit_gb"]))
        except Exception:
            pass  # 摘要不可用保留缺省 10/12GB

    def _sync_health_ui(self) -> None:
        try:
            self.query_one(Sidebar).set_health()
        except Exception:
            pass
        try:
            self.query_one("#page-home", HomePage).render_state()
        except Exception:
            pass

    async def action_refresh_env(self) -> None:
        """命令面板「刷新体检」：单次拉取（§3.2 手动触发位）。"""
        client = get_client()
        try:
            self.health_data = await client.health()
            self.service_error = None
            summary = await client.env_check()
            self.env_items = list(summary.get("items", []))
            self.notify("体检已刷新", severity="information")
        except Exception as exc:
            self.service_error = str(exc)
            self.notify(f"刷新失败：{exc}", severity="error")
        self._sync_health_ui()

    # ---- WS 监控通道（1s 采样；指数退避重连；心跳保活标记）----
    async def _monitor_loop(self) -> None:
        client = get_client()
        backoff = 1.0
        while True:
            try:
                ws = await client.subscribe_monitor()
                self.monitor_state["ws_connected"] = True
                backoff = 1.0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("type") == "monitor":
                        self.monitor_state.ingest(msg.get("payload") or {})
                    elif msg.get("type") == "heartbeat":
                        self.monitor_state["updated_at"] = time.monotonic()
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            self.monitor_state["ws_connected"] = False
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 5.0)

    async def _running_loop(self) -> None:
        """运行中任务数（5s 轮询；状态栏与监控页共用 MonitorState）。"""
        client = get_client()
        while True:
            try:
                data = await client.list_tasks(page=1, status="running")
                self.monitor_state["running_count"] = len((data or {}).get("items") or [])
            except Exception:
                self.monitor_state["running_count"] = 0
            await asyncio.sleep(5.0)

    # ---- 导航 ----
    def switch_page(self, index: int) -> None:
        now = time.monotonic()
        if now - self._last_nav < NAV_DEBOUNCE_S:  # 连续导航键去抖 30ms（§1.7）
            return
        self._last_nav = now
        index = max(0, min(len(PAGES) - 1, index))
        self._current_page = PAGES[index][0]
        # 页面换装走 exclusive worker 串行化（remove_children 是 AwaitRemove，
        # 同 id 换页必须先卸后挂；exclusive 保证快速连按只落最后一页）
        self.run_worker(self._mount_page(index), group="page-mount", exclusive=True)

    async def _mount_page(self, index: int) -> None:
        try:
            key = PAGES[index][0]
            content = self.query_one("#content", Vertical)
            await content.remove_children()
            client = get_client()
            pages = {
                "home": lambda: HomePage(client, self),
                "spider": lambda: SpiderPage(client),
                "parser": lambda: ParserPage(client, self),
                "converter": lambda: ConverterPage(client, self),
                "pipeline": lambda: PipelinePage(client),
                "monitor": lambda: MonitorPage(client, self),
                "history": lambda: HistoryPage(client),
                "settings": lambda: SettingsPage(client),
            }
            await content.mount(pages[key]())
            self.query_one(Sidebar).set_page(index)
        except Exception as exc:
            self.notify(f"页面加载失败：{exc}", severity="error")

    def action_page(self, index: str) -> None:
        self.switch_page(int(index))

    # ---- 快捷键动作 ----
    def action_ai_panel(self) -> None:
        self.push_screen(AiPanel(get_client()))

    def action_file_browser(self) -> None:
        self.push_screen(FileBrowserScreen(get_client()))

    def action_toggle_log(self) -> None:
        self.push_screen(LogScreen(get_client()))

    def action_set_theme(self, name: str) -> None:
        """主题热切（§1.5）：refresh_css 瞬时生效。

        注：appearance.theme 持久化依赖服务端 app_settings 白名单扩键
        （方案 V1-B.6，未在本里程碑范围），当前主题选择会话内生效。
        """
        if name not in design.THEMES:
            self.notify(f"未知主题：{name}", severity="error")
            return
        self.theme = name
        self.notify(f"主题已切换：{name}", severity="information")

    async def reconnect(self) -> None:
        try:
            await get_client().health()
        except Exception:
            return  # 仍不可达，停留在引导屏
        if isinstance(self.screen, ConnectScreen):
            self.pop_screen()
        self.notify("服务核心已恢复连接", severity="information")


def main() -> None:
    AstroForgeApp().run()


if __name__ == "__main__":
    main()
