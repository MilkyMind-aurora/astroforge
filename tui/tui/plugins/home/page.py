# -*- coding: utf-8 -*-
"""首页 · 星桥 Hub（方案 §3.2）：一屏答三问——服务是否健康、环境缺什么、从哪出发。

骨架：星野框（静态 3 行，row0→row1→问候→row2）+ 星仔帧 → 问候 → 环境体检
九宫格（3×3）→ 服务核心行（版本/运行时长/DB/AI 引擎）→ 快捷 chips 横排 + 合规行。
数据：app 层 _health_loop 5s 轮询 /system/health + /system/env-check（本页只消费
同一份状态，侧栏健康点与体检九宫格同源）；命令面板「刷新体检」手动触发。
动效：九宫格错峰入场（§1.8 #13，stagger 30ms/行，一次性入场非循环）；体检项
✕→✓ 修复行单格 aurora 高亮一帧后复原（L10，一次性边界闪烁）；星仔 5s 定时器
只推进 idle/idle_blink 状态帧（M3：boot 台词每会话 1 次，QuoteDirector dispatch
落地，不随渲染重摇）。
计宽：九宫格列宽一律 rich.cells.cell_len（L11，CJK 双宽与 sidebar 同口径）。
"""
from __future__ import annotations

import datetime

from rich.cells import cell_len
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static

from tui.components.chips import ChipAction
from tui.theme.generated import tokens as design
from tui.ui.mascot import QuoteDirector, get_frame
from tui.ui.starfield import render_starfield

_ERR_HINTS = ("失败", "错误", "未初始化")  # detail 含这些词按「异常」而非「缺失」记
STAGGER_S = 0.03  # 九宫格错峰入场（§1.8 #13，30ms/项）
GRID_WIDTH = 30   # 九宫格单格宽（含detail房间；L11 计宽口径 cell_len）


def greeting_by_hour(hour: int) -> str:
    """问候语三段（早/午/晚，§3.2 文案全集）。"""
    if 5 <= hour < 12:
        return "早安，指挥官"
    if 12 <= hour < 18:
        return "午安，指挥官"
    return "晚上好，指挥官"


def check_glyph(item: dict) -> tuple[str, str]:
    """体检项 → (星符语义名, 颜色 token 名)：✓ 极光 / ○ 占位灰 / ✕ nova。"""
    if item.get("ok"):
        return "task.success", "aurora"
    detail = str(item.get("detail", ""))
    if any(hint in detail for hint in _ERR_HINTS):
        return "task.failed", "nova"
    return "task.pending", "ink-400"


def cut_by_cells(text: str, limit: int) -> str:
    """按显示宽截断（CJK 双宽敏感，L11；cell_len 口径）。"""
    out: list[str] = []
    used = 0
    for char in text:
        width = cell_len(char)
        if used + width > limit:
            break
        out.append(char)
        used += width
    return "".join(out)


def render_grid(items: list[dict], width: int = GRID_WIDTH,
                flash: set[str] | None = None) -> list[str]:
    """九宫格 3×3：每格 = 状态星符 + 名 + detail 一行（三列等宽，cell_len 计宽）。

    flash（L10）：本帧 ✕→✓ 修复项的名单——单格整列临时 aurora 高亮，一帧后
    由渲染复原（一次性边界闪烁，非循环动画）。
    """
    lines: list[str] = []
    flash = flash or set()
    for row_start in range(0, len(items), 3):
        cells = []
        for item in items[row_start:row_start + 3]:
            glyph, color = check_glyph(item)
            mark_plain = design.icon(glyph)
            name = str(item.get("name", "?"))
            detail = str(item.get("detail", "")).replace("\n", " ")
            room = max(4, width - cell_len(name) - 4)
            detail_cut = cut_by_cells(detail, room)
            # 纯文本计宽补齐（markup 标签不计显示宽，L11 CJK 对齐）
            plain = f" {mark_plain} {name}  {detail_cut}"
            pad = " " * max(0, width + 2 - cell_len(plain))
            if name in flash:
                body = (f" [${color}]{mark_plain}[/${color}]"
                        f" [${'aurora'}]{name}  {detail_cut}[/]")
            else:
                body = (f" [${color}]{mark_plain}[/${color}]"
                        f" {name}  [dim]{detail_cut}[/dim]")
            cells.append(body + pad)
        lines.append("".join(cells).rstrip())
    return lines


class HomePage(VerticalScroll):
    """星桥 Hub：体检九宫格 + 服务核心行 + 快捷 chips。"""

    def __init__(self, client, app_ref=None) -> None:  # noqa: ANN001（App 循环依赖，宽型注解）
        super().__init__(id="page-home")
        self.client = client
        self._app = app_ref
        self._staggered = False  # 错峰入场只播一次（首帧到达）
        self._director = QuoteDirector()   # M3：dispatch 语义（boot cap_session:1）
        self._boot_quote: str | None = None  # 台词播报缓存（5s 刷新不重摇）
        self._blink = False                  # 星仔状态帧（idle/idle_blink 交替）
        self._prev_ok: dict[str, bool] = {}  # 体检项上一帧 ok 态（L10 闪帧检测）
        self._flash_timer = None

    def compose(self) -> ComposeResult:
        yield Static("正在探测环境…", id="home-hero", classes="page-body")
        with Horizontal(id="home-chips"):
            yield ChipAction("2 采集", id="chip-spider")
            yield ChipAction("5 流水线", id="chip-pipeline")
            yield ChipAction("/ 命令面板", id="chip-cmd")
            yield ChipAction("A 星伴", id="chip-ai")
        yield Static("数据不出本机 · 本地引擎驱动", id="home-compliance")

    def on_mount(self) -> None:
        self.set_interval(5.0, self._tick)  # M3：只推进状态帧，不重摇台词
        self.render_state()

    def _tick(self) -> None:
        self._blink = not self._blink
        self.render_state()

    # ---- 渲染（数据来自 app 共享态）----
    def _hero(self) -> str:
        star_lines = render_starfield(width=56).splitlines()
        star_rows = [star_lines[i] if i < len(star_lines) else "" for i in range(3)]
        frame = get_frame("idle_blink" if self._blink else "idle").rstrip()
        return "\n".join([
            f"[dim]{star_rows[0]}[/dim]",
            f"[dim]{star_rows[1]}[/dim]",
            f"[b]{greeting_by_hour(datetime.datetime.now().hour)}[/b]"
            f"  [dim]把一堆氢，锻成重元素。[/dim]",
            f"[dim]{star_rows[2]}[/dim]",
            f"[dim]{frame}[/dim]",
            f"[i][${'molten'}]星仔 ·[/] {self._boot_quote or ''}[/i]",
            "",
        ])

    @staticmethod
    def _service_line(health: dict) -> str:
        db_mark = (f"[${'aurora'}]{design.icon('status.ok')}[/]"
                   if health.get("db")
                   else f"[${'nova'}]{design.icon('status.error')}[/]")
        ai_mark = (f"[${'aurora'}]{design.icon('status.ok')}[/]"
                   if health.get("ai_engine")
                   else f"[${'ink-400'}]{design.icon('status.idle')}[/]")
        uptime = int(float(health.get("uptime_s", 0)))
        return (
            f"[b]服务核心[/b]  v{health.get('version', '?')} · "
            f"运行 {uptime // 3600}h{(uptime % 3600) // 60:02d}m · "
            f"DB {db_mark} · AI 引擎 {ai_mark}"
        )

    def render_state(self) -> None:
        """从 app 共享态渲染（无独立请求；5s 定时 + app 健康循环完成即刷）。"""
        app = self._app
        if app is None:
            return
        if self._boot_quote is None:  # M3：boot 台词每会话播报一次（dispatch cap_session:1）
            self._boot_quote = self._director.announce("boot") or ""
        hero = self.query_one("#home-hero", Static)
        items = list(app.env_items)
        health = app.health_data
        if not items or health is None:
            if app.service_error and not health:
                hero.update(
                    f"\n[${'nova'}]{design.icon('status.error')} 服务不可达[/]"
                    f"  {app.service_error}\n"
                    "从命令面板执行「重连服务核心」，或等状态栏恢复自动重试。"
                )
            return
        ok_count = sum(1 for item in items if item.get("ok"))
        head = "\n".join([
            self._hero(),
            self._service_line(health),
            "",
            f"[b]环境体检[/b]  [${'aurora'}]{ok_count}/{len(items)} 项就绪[/]",
        ])
        # L10：对上一帧 ✕（或 ○）本帧 ✓ 的修复行，单格 aurora 高亮一帧后复原
        flash = {str(item.get("name", "")) for item in items
                 if item.get("ok")
                 and self._prev_ok.get(str(item.get("name", ""))) is False}
        self._prev_ok = {str(item.get("name", "")): bool(item.get("ok"))
                         for item in items}
        grid = render_grid(items, flash=flash)
        if self._staggered:  # 已入场：直接整幅更新
            hero.update("\n".join([head, *grid]))
            if flash and self._flash_timer is None:
                self._flash_timer = self.set_timer(
                    design.MOTION_TUI["t_fade"]["duration_ms"] / 1000,
                    self._clear_flash)
            return
        self._staggered = True
        hero.update(head)
        # 九宫格错峰入场：30ms/行逐行显现（一次性入场动画，非持续背景动画）
        for index in range(len(grid)):
            self.set_timer(
                STAGGER_S * (index + 1),
                lambda shown=index: hero.update("\n".join([head, *grid[:shown + 1]])))

    def _clear_flash(self) -> None:
        """L10 高亮帧复原（一次性定时器，非循环）。"""
        self._flash_timer = None
        try:
            self.render_state()
        except Exception:
            pass  # 页面已被换装移除

    def on_button_pressed(self, event: Button.Pressed) -> None:  # ChipAction 同为 Button
        if self._app is None:
            return
        if event.button.id == "chip-spider":
            self._app.switch_page_by_key("spider")
        elif event.button.id == "chip-pipeline":
            self._app.switch_page_by_key("pipeline")
        elif event.button.id == "chip-cmd":
            self._app.run_action("command_palette")
        elif event.button.id == "chip-ai":
            self._app.action_ai_panel()
