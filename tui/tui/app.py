# -*- coding: utf-8 -*-
"""AstroForge TUI 工作台（kitty + Warp 融合风格骨架，方案 3.1）。

启动流程：探活 Sidereal Core → 失败进连接引导屏 / 成功进主界面。
快捷键：1-8 切页 · Ctrl+Shift+A AI 面板 · Ctrl+` 日志 · q 退出。
"""
from __future__ import annotations

import asyncio
import json

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hits, Provider
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Static

from tui.pages.history import HistoryPage
from tui.pages.pipeline import PipelinePage
from tui.pages.settings import SettingsPage
from tui.pages.spider import SpiderPage
from tui.service_client import ServiceClient, ServiceError, get_client
from tui.ui.file_browser import FileBrowserScreen

TAGLINE = "AstroForge — Forging Order from Stellar Chaos."
VERSION = "Sidereal Core v0.1.0"

PAGES = [
    ("home", "首页"),
    ("spider", "采集中心"),
    ("parser", "解析中心"),
    ("converter", "转换中心"),
    ("pipeline", "流水线"),
    ("monitor", "监控看板"),
    ("history", "任务历史"),
    ("settings", "设置"),
]

PAGE_PHASE = {
    "spider": ("Phase 2", "Scrapling 爬虫：单页转 MD / 整站结构化 / PDF 批量下载 / 表格抓取"),
    "parser": ("Phase 3", "MinerU 文档解析 + WebPlotDigitizer 图表数值提取"),
    "converter": ("Phase 4", "anydoc 办公文档入库 / md2docx 模板化出 Word"),
    "pipeline": ("Phase 5", "NovaFlow 流水线编排：内置模板一键全链路 + 断点续跑"),
    "monitor": ("Phase 1.2", "NovaFlow 实时监控看板：资源曲线 / 告警 / 历史回放"),
    "history": ("Phase 1.4", "任务历史：状态筛选 / 日志回看 / 一键重试"),
}


class ForgeCommands(Provider):
    """全局命令面板（方案 1.1.5）：/ 唤起，模糊搜索。"""

    def _commands(self) -> list[tuple[str, object]]:
        app = self.app
        items: list[tuple[str, object]] = [
            ("首页", lambda: app.switch_page(0)),
            ("采集中心", lambda: app.switch_page(1)),
            ("解析中心", lambda: app.switch_page(2)),
            ("转换中心", lambda: app.switch_page(3)),
            ("流水线", lambda: app.switch_page(4)),
            ("监控看板", lambda: app.switch_page(5)),
            ("任务历史", lambda: app.switch_page(6)),
            ("设置", lambda: app.switch_page(7)),
            ("打开文件浏览器", app.action_file_browser),
            ("打开日志面板", app.action_toggle_log),
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


class ConnectScreen(ModalScreen):
    """连接引导屏：服务未启动时的落点（方案 3.10 连接引导页的 TUI 版）。"""

    CSS = """
    ConnectScreen { align: center middle; }
    #connect-box { width: 60; padding: 2 4; border: round #8B7CF6; background: $surface; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="connect-box"):
            yield Static("🔭 连不上 Sidereal Core（127.0.0.1:8420）", id="connect-title")
            yield Static("服务核心未启动。请在仓库根目录运行：\n\n"
                         "  Windows: scripts\\start_service.bat\n"
                         "  macOS:   bash scripts/start_service.sh\n\n"
                         "启动后点重试，或按 q 退出。")
            yield Button("重试连接", id="btn-retry", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-retry":
            self.app.call_later(self.app.reconnect)


class AiPanel(ModalScreen):
    """AI 抽屉占位（对接 AI 引擎属 Phase 6.3）。"""

    CSS = """
    AiPanel { align: right middle; }
    #ai-box { width: 48; height: 70%; padding: 1 2; border: tall #4FC3F7; background: $surface; }
    #ai-out { height: 1fr; margin-bottom: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-box"):
            yield Static("✦ 星伴 AI（对话引擎属 Phase 6）", id="ai-title")
            placeholder = Static(
                "本地 GGUF 引擎未接入。\n自然语言指令驱动、流式回复与任务卡片将在此展示。"
            )
            yield VerticalScroll(placeholder, id="ai-out")
            yield Input(placeholder="输入指令（当前仅本地回显）", id="ai-in")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        out = self.query_one("#ai-out Static", Static)
        out.update(out.renderable + f"\n\n[你] {event.value}\n[星伴] 已收到（引擎对接属 Phase 6）")
        event.input.value = ""


class PlaceholderPage(Static):
    """统一占位页：页面名 + 功能说明 + 建设中徽标。"""

    def __init__(self, page_key: str) -> None:
        phase, desc = PAGE_PHASE[page_key]
        title = dict(PAGES)[page_key]
        super().__init__(
            f"\n[bold cyan]{title}[/bold cyan]  [dim]🚧 建设中 · {phase}[/dim]\n\n{desc}\n\n"
            f"数据通道已就绪：REST + WebSocket（X-AstroForge-Token）。\n"
            f"本页将复用与服务端已联通的 {VERSION} 接口。",
            classes="page-body",
        )


class HomePage(VerticalScroll):
    """首页：环境状态卡（调 env-check）+ 快捷入口。"""

    def compose(self) -> ComposeResult:
        yield Static("\n[bold cyan]首页[/bold cyan]  正在探测环境…", id="home-summary", classes="page-body")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_summary(), exclusive=True)

    async def refresh_summary(self) -> None:
        client = get_client()
        try:
            summary = await client.env_check()
            health = await client.health()
        except ServiceError as exc:
            self.query_one("#home-summary", Static).update(
                f"\n[red]服务错误 {exc.code}[/red] {exc}"
            )
            return
        except Exception as exc:
            self.query_one("#home-summary", Static).update(f"\n[red]连接失败[/red] {exc}")
            return
        lines = [
            f"\n[bold cyan]首页[/bold cyan]  [dim]{TAGLINE}[/dim]",
            f"\n[bold]服务核心[/bold] v{health['version']} · 运行 {health['uptime_s']}s · "
            f"DB {'✅' if health['db'] else '❌'} · AI 引擎 {'✅' if health['ai_engine'] else '💤'}",
            f"[bold]环境体检[/bold] {summary['ok_count']}/{summary['total']} 通过：",
        ]
        for item in summary["items"]:
            mark = "✅" if item["ok"] else "❌"
            lines.append(f"  {mark} {item['name']}  [dim]{item['detail']}[/dim]")
        lines.append("\n[dim]快捷入口：2 采集 · 3 解析 · 4 转换 · 5 流水线 · Ctrl+Shift+A 星伴 AI[/dim]")
        self.query_one("#home-summary", Static).update("\n".join(lines))


class LogScreen(ModalScreen):
    """可折叠日志面板（方案 1.1.4）：自动订阅最近运行中任务的 WS 日志流。"""

    CSS = """
    LogScreen { align: center middle; }
    #log-box { width: 90%; height: 60%; border: tall #4FC3F7; padding: 1 2; background: $surface; }
    #log-body { height: 1fr; overflow: auto; }
    """

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self._ws = None

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical

        with Vertical(id="log-box"):
            yield Static("📜 日志面板（订阅最近运行中任务）", id="log-title")
            yield Static("正在查找运行中的任务…", id="log-body")
            yield Button("关闭 (Esc)", id="log-close", variant="default")

    def on_mount(self) -> None:
        self.run_worker(self._follow(), exclusive=True)

    async def _follow(self) -> None:
        body = self.query_one("#log-body", Static)
        try:
            task = await self.client.running_task()
        except Exception as exc:
            body.update(f"[red]查询失败[/red] {exc}")
            return
        if task is None:
            body.update("[dim]当前没有运行中的任务。启动任务后这里会实时滚动其日志。[/dim]")
            return
        task_uuid = task["task_uuid"]
        body.update(f"[dim]已连接 ws/logs/{task_uuid}[/dim]\n")
        try:
            self._ws = await self.client.subscribe_logs(task_uuid)
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                    payload = msg.get("payload", {})
                    text = payload.get("text") or msg.get("type", "")
                except json.JSONDecodeError:
                    text = str(raw)
                body.update(body.renderable + f"\n{text}")
        except Exception as exc:
            body.update(body.renderable + f"\n[red]日志流断开: {exc}[/red]")

    def on_key(self, event) -> None:  # noqa: ANN001
        if event.key == "escape":
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "log-close":
            self.dismiss()

    def on_unmount(self) -> None:
        if self._ws is not None:
            asyncio.create_task(self._ws.close())


class AstroForgeApp(App):
    TITLE = "AstroForge 衍星台"
    SUB_TITLE = TAGLINE
    CSS = """
    #main { height: 1fr; }
    #sidebar { width: 20; border-right: solid #8B7CF6; padding: 1; }
    #sidebar Button { width: 100%; margin-bottom: 1; min-height: 3; }
    #content { padding: 1 2; }
    .page-body { padding: 1 1; }
    """
    COMMANDS = App.COMMANDS | {ForgeCommands}
    BINDINGS = [
        Binding("/", "command_palette", "命令面板"),
        Binding("ctrl+shift+a", "ai_panel", "星伴 AI"),
        Binding("ctrl+grave", "toggle_log", "日志"),
        Binding("f", "file_browser", "文件"),
        Binding("q", "quit", "退出"),
    ]
    _current_page = "home"
    _log_visible = False
    _log_view: Static | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                for index, (_, label) in enumerate(PAGES, start=1):
                    yield Button(f"{index} {label}", id=f"nav-{label}", classes="nav-btn")
            with Vertical(id="content"):
                yield HomePage(id="page-home")
        yield Footer()

    def on_mount(self) -> None:
        self.run_worker(self.probe(), exclusive=True)

    async def probe(self) -> None:
        try:
            await get_client().health()
        except Exception:
            self.push_screen(ConnectScreen())

    async def reconnect(self) -> None:
        try:
            await get_client().health()
        except Exception:
            return  # 仍不可达，停留在引导屏
        if isinstance(self.screen, ConnectScreen):
            self.pop_screen()

    # ---- 导航 ----
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("nav-"):
            label = event.button.id.removeprefix("nav-")
            index = [page_label for _, page_label in PAGES].index(label)
            self.switch_page(index)

    def switch_page(self, index: int) -> None:
        content = self.query_one("#content", Vertical)
        key = PAGES[index][0]
        self._current_page = key
        content.remove_children()
        client = get_client()
        if key == "home":
            content.mount(HomePage(id="page-home"))
        elif key == "settings":
            content.mount(SettingsPage(client))
        elif key == "spider":
            content.mount(SpiderPage(client))
        elif key == "pipeline":
            content.mount(PipelinePage(client))
        elif key == "history":
            content.mount(HistoryPage(client))
        else:
            content.mount(PlaceholderPage(key))

    async def action_page(self, index: int) -> None:
        self.switch_page(index)

    # ---- 快捷键动作 ----
    def action_ai_panel(self) -> None:
        self.push_screen(AiPanel())

    def action_file_browser(self) -> None:
        self.push_screen(FileBrowserScreen(get_client()))

    def action_toggle_log(self) -> None:
        self.push_screen(LogScreen(get_client()))


def main() -> None:
    AstroForgeApp().run()


if __name__ == "__main__":
    main()
