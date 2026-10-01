# -*- coding: utf-8 -*-
"""星轨侧栏（方案 §3.1，插件注册表驱动）：选中胶囊滑移 + 模块健康点 + 窄屏折叠。

胶囊 = container 底 + aurora 左竖条，绝对定位于导航项之下层，页切换时 offset
以 T_PRESS 滑移（#4）；选中项文字 ink-900 加粗；导航项右缘健康点与首页体检
同源（env-check，env_dep 子串匹配，缺失=○ / 异常=✕ / 就绪=●）。窄屏（<100 列）
折叠为 10 列图标轨（tooltip 提示），计宽一律 rich.cells.cell_len（L9⑥，CJK
双宽与首页九宫格同口径）。
AI 入口三态（L12）：闲✵ / 思✶旋转帧（仅思考期间起 0.4s 帧表）/ 毕☄ 短亮 2s；
底部「☄ 星仔彩蛋」行点击弹语录卡（QuoteCardScreen）。
"""
from __future__ import annotations

from rich.cells import cell_len
from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.geometry import Offset
from textual.widget import Widget
from textual.widgets import Static

from tui.plugins import PagePlugin
from tui.shell.format import seg
from tui.theme.generated import tokens as design

AI_THINK_FRAMES = ("ai.thinking", "ai.thinking_f2", "ai.thinking_f3")
AI_THINK_INTERVAL_S = 0.4  # ✶✷✸ 1.2s 一循环（仅思考期间，组件级有界帧）
AI_DONE_GLOW_S = 2.0       # 毕☄ 短亮时长


class NavLink(Static):
    """侧栏导航项（高 3 行）：星符+数字键+标签，右缘健康点由 Sidebar 渲染。"""

    def __init__(self, page_index: int, plugin: PagePlugin) -> None:
        super().__init__(classes="nav-link")
        self.page_index = page_index
        self.plugin = plugin
        self.tooltip = f"{page_index + 1} {plugin.title}"


class Sidebar(Vertical):

    def __init__(self, plugins: list[PagePlugin]) -> None:
        super().__init__(id="sidebar")
        self._plugins = list(plugins)
        self._narrow = False
        self._ai_state = "idle"     # 闲/思/毕（app.set_ai_state 驱动，L12）
        self._think_frame = 0
        self._think_timer = None
        self._done_timer = None

    def compose(self) -> ComposeResult:
        yield Static(f"{design.icon('nav.home')} 星轨导航", id="sidebar-title")
        yield Static("", id="nav-capsule")
        for index, plugin in enumerate(self._plugins):
            yield NavLink(index, plugin)
        yield Static("─" * 8, id="nav-sep", classes="nav-sep")
        ai_entry = Static(self._ai_entry(), id="nav-ai")
        ai_entry.tooltip = "Ctrl+Shift+A 或 A 唤起星伴"
        yield ai_entry
        egg = Static(f"{design.icon('misc.meteor')} 星仔彩蛋", id="nav-egg")
        egg.tooltip = "点一下，听星仔说句话"
        yield egg

    # ---- 渲染 ----
    def _inner_width(self) -> int:
        return (10 if self._narrow else 26) - 2  # 减 NavLink 左右 padding

    def _dot(self, plugin: PagePlugin) -> tuple[str, str]:
        """模块健康点 → (星符语义名, 色 token)：与首页体检同源（env_items）。"""
        items = self.app.env_items
        wanted = plugin.env_dep
        if not items:
            return "status.idle", "ink-400"
        matched = ([it for it in items
                    if any(w in str(it.get("name", "")) for w in wanted)]
                   if wanted else list(items))
        if not matched:
            return "status.idle", "ink-400"
        if all(it.get("ok") for it in matched):
            return "status.ok", "aurora"
        from tui.plugins.home.page import check_glyph  # 局部导入避免 plugins↔shell 环

        return check_glyph(next(it for it in matched if not it.get("ok")))

    def _refresh_items(self) -> None:
        width = self._inner_width()
        for link in self.query(NavLink):
            dot_icon, dot_color = self._dot(link.plugin)
            dot = seg(design.icon(dot_icon), dot_color)
            glyph = design.icon(link.plugin.icon)
            if self._narrow:
                # L9⑥：补齐公式按显示宽（cell_len）计算，与宽屏同口径
                pad = max(1, width - cell_len(glyph) - 1)  # 末尾健康点 1 格
                link.update(f"{glyph}{' ' * pad}{dot}")
            else:
                plain = f"{glyph} {link.page_index + 1} {link.plugin.title}"
                pad = max(1, width - cell_len(plain) - 1)
                link.update(f"{plain}{' ' * pad}{dot}")
        self._refresh_ai_entry()
        self._refresh_egg()

    def _ai_entry(self) -> str:
        """AI 入口三态文本：闲✵ / 思✶旋转帧 / 毕☄（L12）。"""
        if self._ai_state == "thinking":
            icon = AI_THINK_FRAMES[self._think_frame % len(AI_THINK_FRAMES)]
            label = "星伴思考中"
        elif self._ai_state == "done":
            icon, label = "ai.done", "星伴回复完毕"
        else:
            icon, label = "ai.idle", "星伴 AI"
        glyph = design.icon(icon)
        if self._narrow:
            tail = design.icon("ai.fallback")
            pad = max(1, self._inner_width() - cell_len(glyph) - cell_len(tail))
            return f"{glyph}{' ' * pad}{tail}"
        return f"{glyph} {label}  [dim]Ctrl+Shift+A[/dim]"

    def _refresh_ai_entry(self) -> None:
        try:
            self.query_one("#nav-ai", Static).update(self._ai_entry())
        except Exception:
            pass  # 未挂载/已卸载

    def _refresh_egg(self) -> None:
        try:
            egg = self.query_one("#nav-egg", Static)
        except Exception:
            return
        if self._narrow:
            glyph = design.icon("misc.meteor")
            pad = max(0, self._inner_width() - cell_len(glyph))
            egg.update(f"{glyph}{' ' * pad}")
        else:
            egg.update(f"{design.icon('misc.meteor')} 星仔彩蛋")

    # ---- AI 入口三态（L12，app.set_ai_state 调用）----
    def set_ai_state(self, state: str) -> None:
        if state not in ("idle", "thinking", "done"):
            return
        self._ai_state = state
        if state == "thinking":
            if self._think_timer is None:  # 仅思考期间起帧表（有界）
                self._think_timer = self.set_interval(AI_THINK_INTERVAL_S,
                                                      self._tick_think)
        elif self._think_timer is not None:
            self._think_timer.stop()
            self._think_timer = None
        if state == "done":
            if self._done_timer is not None:
                self._done_timer.stop()
            self._done_timer = self.set_timer(AI_DONE_GLOW_S, self._done_glow_over)
        elif self._done_timer is not None:
            self._done_timer.stop()
            self._done_timer = None
        self._refresh_ai_entry()

    def _tick_think(self) -> None:
        self._think_frame += 1
        self._refresh_ai_entry()

    def _done_glow_over(self) -> None:
        """毕☄ 短亮结束 → 回闲态。"""
        self._done_timer = None
        if self._ai_state == "done":
            self.set_ai_state("idle")

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
        capsule.animate("offset", Offset(0, 2 + index * 3),
                        duration=design.MOTION_TUI["t_press"]["duration_ms"] / 1000,
                        easing=design.MOTION_TUI["t_press"]["easing"])

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
        elif isinstance(control, Widget) and control.id == "nav-egg":
            self.app.action_mascot_quote()
