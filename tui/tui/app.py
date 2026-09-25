# -*- coding: utf-8 -*-
"""AstroForge TUI 星舰壳层（方案 §2.4 / §3.1，MF2 插件化收敛版）。

壳只保留：导航/主题/面板/快捷键 + 共享监控态（V1-B.3 门禁：≤300 行）。
- 页面全部由 tui/plugins/* 提供：内置 8 页 + entry_points 组 astroforge.tui_pages
  合并注册，config/design/pages.yaml 显隐/排序覆盖（方案 §2.4）；
- 启动/连接屏、侧栏、状态栏、命令面板、后台轮询见 tui/shell/；
- 星伴 AI 右抽屉与日志面板见 tui/panels/；任务进度卡/步骤时间线见 tui/components/。
快捷键：1-8 切页（30ms 去抖）· / 命令面板 · Ctrl+Shift+A 或 A 星伴 · Ctrl+` 日志 ·
f 文件浏览器 · q 退出。
纪律：颜色一律 $语义变量或 tokens 生成物常量（§3.7 门禁①）；星符一律 design.icon()
（门禁④）；终端无连续背景动画（性能红线）。
"""
from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from tui.panels.ai_drawer import AiDrawerScreen
from tui.panels.log_panel import LogPanelScreen
from tui.plugins import collect_plugins
from tui.plugins.monitor import MonitorState
from tui.service_client import get_client
from tui.shell.boot import BootScreen
from tui.shell.commands import ForgeCommands
from tui.shell.connect import ConnectScreen
from tui.shell.format import seg
from tui.shell.loops import ServiceLoopsMixin
from tui.shell.sidebar import Sidebar
from tui.shell.status_bar import StatusBar
from tui.theme import astro_theme
from tui.theme.generated import tokens as design
from tui.ui.file_browser import FileBrowserScreen

TAGLINE = "AstroForge — Forging Order from Stellar Chaos."
VERSION = "Sidereal Core v0.1.0"

# 导航键去抖（tokens.yaml interaction.keyboard.nav_debounce_ms，§1.7）
NAV_DEBOUNCE_S = design.INTERACTION["keyboard"]["nav_debounce_ms"] / 1000


class AstroForgeApp(ServiceLoopsMixin, App):
    """AstroForge TUI 主壳：导航/主题/面板/快捷键（页面由插件注册表驱动）。"""

    TITLE = "AstroForge 衍星台"
    SUB_TITLE = TAGLINE
    CSS_PATH = "theme/generated/tokens.tcss"  # 生成物工具类（.c-*/.bg-*/.border-*）
    # 壳层样式：颜色/边框一律 $语义变量（tokens.css_variables 注入，§3.7 门禁①）
    CSS = """
    #app-header { dock: top; height: 1; background: $card; color: $ink-900;
        padding: 0 2; }
    #main { height: 1fr; }
    #content { padding: 1 2; }
    #status-bar { dock: bottom; height: 1; background: $card; color: $ink-600;
        padding: 0 2; border-top: solid $faint; }
    #too-small { display: none; position: absolute; offset-x: 0; offset-y: 0;
        width: 100%; height: 100%; background: $bg; color: $warning;
        content-align: center middle; }
    #too-small.too-small-on { display: block; }
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
        # 页面插件注册表（内置 + entry_points + pages.yaml；会话内固定）
        self.pages = collect_plugins()
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
        for index, plugin in enumerate(self.pages):
            if plugin.key == self._current_page:
                return index
        return 0

    def get_css_variables(self) -> dict[str, str]:
        """注入星空语义变量（$aurora/$card/$border-normal…）；主题热切随 self.theme
        换档（§1.5 CSS 变量化）。"""
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
            f"{seg(design.icon('nav.home'), 'aurora')} [b]衍星台 AstroForge[/b]"
            f"  [dim]{VERSION}[/dim]", id="app-header")
        with Horizontal(id="main"):
            yield Sidebar(self.pages)
            with Vertical(id="content"):
                first = self.pages[0] if self.pages else None
                if first is not None:
                    yield first.factory(get_client(), self)
        yield StatusBar(id="status-bar")
        yield Static(
            f"{design.icon('status.warn')} 窗口过小（<80×24）——请拉大终端窗口",
            id="too-small")

    def on_mount(self) -> None:
        self.theme = astro_theme.DEFAULT_THEME  # 默认 deep-space（夜）
        self.run_worker(self._restore_appearance(), group="appearance", exclusive=True)
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
            self.query_one("#too-small", Static).set_class(small, "too-small-on")
        except Exception:  # 组合未挂载完成
            pass
        try:
            self.query_one(Sidebar).set_narrow(size.width < 100)
        except Exception:
            pass

    # ---- 导航（插件注册表驱动）----
    def switch_page(self, index: int) -> None:
        now = time.monotonic()
        if now - self._last_nav < NAV_DEBOUNCE_S:  # 连续导航键去抖 30ms（§1.7）
            return
        self._last_nav = now
        index = max(0, min(len(self.pages) - 1, index))
        self._current_page = self.pages[index].key
        # 页面换装走 exclusive worker 串行化（remove_children 是 AwaitRemove，
        # 同 id 换页必须先卸后挂；exclusive 保证快速连按只落最后一页）
        self.run_worker(self._mount_page(index), group="page-mount", exclusive=True)

    def switch_page_by_key(self, key: str) -> None:
        """按键切页（首页 chips / 监控告警跳转等跨页动作位；未注册键忽略）。"""
        for index, plugin in enumerate(self.pages):
            if plugin.key == key:
                self.switch_page(index)
                return

    async def _mount_page(self, index: int) -> None:
        try:
            content = self.query_one("#content", Vertical)
            await content.remove_children()
            await content.mount(self.pages[index].factory(get_client(), self))
            self.query_one(Sidebar).set_page(index)
        except Exception as exc:
            self.notify(f"页面加载失败：{exc}", severity="error")

    def action_page(self, index: str) -> None:
        self.switch_page(int(index))

    # ---- 快捷键动作 ----
    def action_ai_panel(self) -> None:
        self.push_screen(AiDrawerScreen(get_client()))

    def action_file_browser(self) -> None:
        self.push_screen(FileBrowserScreen(get_client()))

    def action_toggle_log(self) -> None:
        self.push_screen(LogPanelScreen(get_client()))

    def action_set_theme(self, name: str) -> None:
        """主题热切（§1.5）：refresh_css 瞬时生效；持久化经 app_settings（尽力）。"""
        if name not in design.THEMES:
            self.notify(f"未知主题：{name}", severity="error")
            return
        self.theme = name
        self.notify(f"主题已切换：{name}", severity="information")
        self.run_worker(self._persist_theme(name), exclusive=True)

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
