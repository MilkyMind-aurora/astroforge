# -*- coding: utf-8 -*-
"""首页 · 星桥 Hub（方案 §3.2）：一屏答三问——服务是否健康、环境缺什么、从哪出发。

骨架：星野框（静态 3 行）+ 星仔帧 → 问候 → 环境体检九宫格（3×3）
→ 服务核心行（版本/运行时长/DB/AI 引擎）→ 快捷 chips 横排 + 合规行。
数据：app 层 _health_loop 5s 轮询 /system/health + /system/env-check（本页只消费
同一份状态，侧栏健康点与体检九宫格同源）；命令面板「刷新体检」手动触发。
动效：九宫格错峰入场（§1.8 #13，stagger 30ms/行，一次性入场非循环）。
"""
from __future__ import annotations

import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Static
from tui.theme.generated import tokens as design
from tui.ui.mascot import get_frame, get_quote
from tui.ui.starfield import render_starfield

_ERR_HINTS = ("失败", "错误", "未初始化")  # detail 含这些词按「异常」而非「缺失」记
STAGGER_S = 0.03  # 九宫格错峰入场（§1.8 #13，30ms/项）


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


def render_grid(items: list[dict], width: int = 30) -> list[str]:
    """九宫格 3×3：每格 = 状态星符 + 名 + detail 一行（三列等宽）。"""
    lines: list[str] = []
    for row_start in range(0, len(items), 3):
        cells = []
        for item in items[row_start:row_start + 3]:
            glyph, color = check_glyph(item)
            mark = f"[${color}]{design.icon(glyph)}[/${color}]"
            name = str(item.get("name", "?"))
            detail = str(item.get("detail", "")).replace("\n", " ")
            room = max(4, width - len(name) - 4)
            cells.append(f" {mark} {name}  [dim]{detail[:room]}[/dim]")
        lines.append("".join(cell.ljust(width + 2) for cell in cells).rstrip())
    return lines


class HomePage(VerticalScroll):
    """星桥 Hub：体检九宫格 + 服务核心行 + 快捷 chips。"""

    def __init__(self, client, app_ref=None) -> None:  # noqa: ANN001（App 存在循环导入，宽型注解）
        super().__init__(id="page-home")
        self.client = client
        self._app = app_ref
        self._staggered = False  # 错峰入场只播一次（首帧到达）

    def compose(self) -> ComposeResult:
        yield Static("正在探测环境…", id="home-hero", classes="page-body")
        with Horizontal(id="home-chips"):
            yield Button("2 采集", id="chip-spider", classes="chip")
            yield Button("5 流水线", id="chip-pipeline", classes="chip")
            yield Button("/ 命令面板", id="chip-cmd", classes="chip")
            yield Button("A 星伴", id="chip-ai", classes="chip")
        yield Static("数据不出本机 · 本地引擎驱动", id="home-compliance")

    def on_mount(self) -> None:
        self.set_interval(5.0, self.render_state)
        self.render_state()

    # ---- 渲染（数据来自 app 共享态）----
    def _hero(self) -> str:
        star_lines = render_starfield(width=56).splitlines()
        star_rows = [star_lines[i] if i < len(star_lines) else "" for i in range(3)]
        return "\n".join([
            f"[dim]{star_rows[0]}[/dim]",
            f"[b]{greeting_by_hour(datetime.datetime.now().hour)}[/b]"
            f"  [dim]把一堆氢，锻成重元素。[/dim]",
            f"[dim]{star_rows[2]}[/dim]",
            f"[dim]{star_rows[1]}[/dim]",
            f"[dim]{get_frame('idle').rstrip()}[/dim]",
            f"[i][${'molten'}]星仔 ·[/] {get_quote('boot')}[/i]",
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
        grid = render_grid(items)
        if self._staggered:  # 已入场：直接整幅更新（阈值修复 ✕→✓ 单格变色随渲染生效）
            hero.update("\n".join([head, *grid]))
            return
        self._staggered = True
        hero.update(head)
        # 九宫格错峰入场：30ms/行逐行显现（一次性入场动画，非持续背景动画）
        for index in range(len(grid)):
            self.set_timer(
                STAGGER_S * (index + 1),
                lambda shown=index: hero.update("\n".join([head, *grid[:shown + 1]])))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._app is None:
            return
        if event.button.id == "chip-spider":
            self._app.switch_page(1)
        elif event.button.id == "chip-pipeline":
            self._app.switch_page(4)
        elif event.button.id == "chip-cmd":
            self._app.run_action("command_palette")
        elif event.button.id == "chip-ai":
            self._app.action_ai_panel()
