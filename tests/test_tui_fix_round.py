# -*- coding: utf-8 -*-
"""TUI 遗留全清轮定向测试（M3/L9/L10/L11/L12/L13/L14/L15/L16/L17/L18）。

覆盖：dispatch 语义（QuoteDirector cap_session/cap_lifetime_once/cooldown_s）、
env_gate 缺失推导与门禁挂载、九宫格 CJK 计宽与修复闪帧、hero 行序与台词缓存、
连接面板探活阶段/计时尾缀/壳内嵌复原、历史行键精确 uuid、AI 入口三态文本、
监控 WS alert 并列与 uuid 定位、chips 选中 aurora 底深字。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tui"))

import pytest  # noqa: E402
from rich.cells import cell_len  # noqa: E402
from tui.components.chips import ChipBar  # noqa: E402
from tui.components.env_gate import (  # noqa: E402
    EnvGateMixin,
    missing_card_text,
    missing_deps,
)
from tui.plugins import collect_plugins  # noqa: E402
from tui.plugins.home.page import HomePage, render_grid  # noqa: E402
from tui.plugins.monitor.page import MonitorState  # noqa: E402
from tui.shell.connect import ConnectPanel, render_phase_line  # noqa: E402
from tui.shell.format import spinner_frame  # noqa: E402
from tui.theme.generated import tokens as design  # noqa: E402
from tui.ui.mascot import (  # noqa: E402
    DispatchRule,
    QuoteDirector,
    get_quote,
    load_dispatch,
    resolve_group,
)

# ============================================================
# M3 · dispatch 语义（quotes.yaml dispatch 段落地）
# ============================================================

def test_dispatch规则表_yaml同源() -> None:
    rules = load_dispatch()
    assert rules["boot"].cap_session == 1
    assert rules["first_task"].cap_lifetime_once is True
    assert rules["task_success"].cooldown_s == 30
    assert rules["task_fail"].cooldown_s == 10


def test_director_cap_session_boot每会话一次() -> None:
    director = QuoteDirector(rules={"boot": DispatchRule(cap_session=1)},
                             clock=lambda: 0.0)
    pool = {"boot": ["氢料就位。", "恒星入列。"]}
    first = director.announce("boot", now_hour=12, pool=pool)
    assert first in {"氢料就位。", "恒星入列。"}
    assert director.announce("boot", now_hour=12, pool=pool) is None  # 会话上限拒绝


def test_director_cooldown_冷却窗口() -> None:
    now = [100.0]
    director = QuoteDirector(rules={"task_fail": DispatchRule(cooldown_s=10)},
                             clock=lambda: now[0])
    pool = {"task_fail": ["只此一条。"]}
    assert director.announce("task_fail", now_hour=12, pool=pool) == "只此一条。"
    now[0] += 5
    assert director.announce("task_fail", now_hour=12, pool=pool) is None  # 冷却中
    now[0] += 11
    assert director.announce("task_fail", now_hour=12, pool=pool) == "只此一条。"


def test_director_cap_lifetime_once() -> None:
    director = QuoteDirector(rules={"first_task": DispatchRule(cap_lifetime_once=True)},
                             clock=lambda: 0.0)
    pool = {"first_task": ["首锻出炉。"]}
    assert director.announce("first_task", now_hour=12, pool=pool) == "首锻出炉。"
    assert director.announce("first_task", now_hour=12, pool=pool) is None


def test_resolve_group_深夜改投与白天不投() -> None:
    pool = {"boot": ["氢。"], "midnight": ["夜。"]}
    assert resolve_group("boot", pool, 12) == "boot"
    hits = {resolve_group("boot", pool, 2) for _ in range(200)}
    assert "midnight" in hits and "boot" in hits      # 概率改投存在
    assert all(resolve_group("boot", pool, 12) == "boot" for _ in range(50))


def test_get_quote_行为保持_缺组回落() -> None:
    pool = {"boot": ["氢。"], "idle_long": ["守炉中。"]}
    assert get_quote("task_fail", now_hour=12, pool=pool) == "守炉中。"


# ============================================================
# L9② · env_gate 缺失推导
# ============================================================

def test_missing_deps_子串匹配与空表不误禁() -> None:
    items = [{"name": "Chromium 浏览器", "ok": False, "detail": "未配置"},
             {"name": "Conda", "ok": True, "detail": "ok"}]
    assert missing_deps(items, ("Chromium",)) == [items[0]]
    assert missing_deps(items, ("PostgreSQL",)) == []
    assert missing_deps(items, ()) == []              # 无依赖恒放行
    assert missing_deps([], ("Chromium",)) == []      # 体检未到达不误禁


def test_missing_card_text_含项名与修复指引() -> None:
    text = missing_card_text([{"name": "Conda", "ok": False, "detail": "未找到 conda"}])
    assert "Conda" in text and "未找到 conda" in text
    assert design.icon("status.warn") in text


@pytest.mark.anyio
async def test_env_gate_缺失禁用与自动恢复() -> None:
    from textual.app import App, ComposeResult
    from tui.plugins.spider.page import SpiderPage

    class Host(App):
        env_items: list[dict] = []
        pages: list = []

        def get_css_variables(self) -> dict[str, str]:
            variables = super().get_css_variables()
            variables.update(design.css_variables(design.DEFAULT_THEME))
            variables.update({
                "border-subtle": design.BORDER_LEVELS["subtle"],
                "border-normal": design.BORDER_LEVELS["normal"],
                "border-active": design.BORDER_LEVELS["active"],
                "thinking-opacity": str(design.THINKING_OPACITY),
            })
            return variables

        def compose(self) -> ComposeResult:
            yield SpiderPage(None, None)

    app = Host()
    async with app.run_test(size=(100, 32)) as pilot:
        page = app.query_one(SpiderPage)
        page._app = app
        app.pages = collect_plugins()
        app.env_items = [{"name": "Chromium 浏览器", "ok": False, "detail": "未配置"}]
        await page.apply_env_gate()
        await pilot.pause()
        assert page.query_one("#sp-run").disabled          # 表单禁用
        assert page.query_one("#sp-url").disabled
        card = page.query_one(".env-missing-card")
        assert card.has_class("env-missing-on")            # 缺失卡在场
        assert "Chromium" in str(card.content)
        app.env_items = [{"name": "Chromium 浏览器", "ok": True, "detail": "ok"}]
        await page.apply_env_gate()
        await pilot.pause()
        assert not page.query_one("#sp-run").disabled      # 修复即解禁
        assert not card.has_class("env-missing-on")        # 缺失卡撤下


def test_env_gate_默认选择器为空() -> None:
    assert EnvGateMixin.GATE_DISABLE == ()


# ============================================================
# L10/L11/L18 · 首页九宫格与 hero
# ============================================================

def _plain(markup: str) -> str:
    """去 rich markup 标签（计宽断言用）。"""
    return re.sub(r"\[[^\]]*\]", "", markup)


def test_render_grid_CJK计宽不溢出() -> None:
    # CJK 名「名字」占 4 格：cell_len 口径房间 = 30-4-4 = 22 格 → 11 个全角汉；
    # 旧 len() 口径会放到 24 字（48 格）溢出对齐
    item = {"name": "名字", "ok": True, "detail": "汉" * 40}
    plain = _plain(render_grid([item])[0])
    assert "汉" * 11 in plain and "汉" * 12 not in plain
    assert cell_len(plain) <= 32                          # 单格 ≤ width+2 显示列


def test_render_grid_修复行单格闪帧高亮() -> None:
    items = [{"name": "Chromium 浏览器", "ok": True, "detail": "d"}]
    flash_line = render_grid(items, flash={"Chromium 浏览器"})[0]
    normal_line = render_grid(items)[0]
    assert f"[${'aurora'}]Chromium 浏览器" in flash_line   # L10：整列临时 aurora
    assert f"[${'aurora'}]Chromium 浏览器" not in normal_line


def test_hero_星野行序与台词不重摇() -> None:
    from tui.ui.starfield import render_starfield

    page = HomePage(None, None)
    page._boot_quote = "氢料就位。"
    hero = page._hero()
    star_lines = render_starfield(width=56).splitlines()
    g = hero.find("指挥官")
    r1 = hero.find(star_lines[1]) if star_lines[1] else -1
    r2 = hero.find(star_lines[2]) if star_lines[2] else -1
    assert g != -1
    if r1 != -1:                                          # row1 在问候前（L18 row0→row1→问候→row2）
        assert r1 < g
    if r2 != -1:                                          # row2 在问候后
        assert g < r2
    quote_at = hero.find("星仔 ·")
    assert "氢料就位。" in hero[quote_at:quote_at + 40]
    hero2 = page._hero()                                  # M3：缓存台词不随渲染重摇
    assert hero2[hero2.find("星仔 ·"):] == hero[quote_at:]


# ============================================================
# L12 · 侧栏 AI 入口三态与彩蛋行
# ============================================================

def test_sidebar_AI入口三态文本() -> None:
    from tui.shell.sidebar import Sidebar

    bar = Sidebar([])
    bar._narrow = False
    bar._ai_state, bar._think_frame = "idle", 0
    assert design.icon("ai.idle") in bar._ai_entry()
    bar._ai_state, bar._think_frame = "thinking", 1
    assert design.icon("ai.thinking_f2") in bar._ai_entry()   # ✶✷✸ 旋转帧
    bar._ai_state = "done"
    assert design.icon("ai.done") in bar._ai_entry()          # 毕☄
    bar._narrow = True
    bar._ai_state, bar._think_frame = "idle", 0
    plain = _plain(bar._ai_entry())
    assert design.icon("ai.fallback") in plain
    assert cell_len(plain) == 10 - 2                          # 窄屏计宽恰好占满（L9⑥）


@pytest.mark.anyio
async def test_sidebar彩蛋行点击弹语录卡() -> None:
    from textual.app import App, ComposeResult
    from tui.shell.quote_card import QuoteCardScreen
    from tui.shell.sidebar import Sidebar

    class Host(App):
        env_items: list[dict] = []
        pages: list = []

        def get_css_variables(self) -> dict[str, str]:
            variables = super().get_css_variables()
            variables.update(design.css_variables(design.DEFAULT_THEME))
            variables.update({
                "border-subtle": design.BORDER_LEVELS["subtle"],
                "border-normal": design.BORDER_LEVELS["normal"],
                "border-active": design.BORDER_LEVELS["active"],
                "thinking-opacity": str(design.THINKING_OPACITY),
            })
            return variables

        @property
        def current_page_index(self) -> int:
            return 0

        def action_mascot_quote(self) -> None:
            self.push_screen(QuoteCardScreen())

        def compose(self) -> ComposeResult:
            yield Sidebar(collect_plugins())

    app = Host()
    async with app.run_test(size=(100, 34)) as pilot:
        await pilot.pause()
        app.query_one("#nav-egg")                              # 彩蛋行在场（L12）
        app.query_one("#nav-ai")
        await pilot.click("#nav-egg")
        await pilot.pause()
        assert isinstance(app.screen, QuoteCardScreen)         # 点击弹语录卡
        await pilot.press("a")
        await pilot.pause()
        assert not isinstance(app.screen, QuoteCardScreen)     # 任意键关闭


# ============================================================
# L13/L14 · 连接面板
# ============================================================

def test_连接面板阶段行_探活跑圈与计时尾缀() -> None:
    line = render_phase_line(ConnectPanel.PHASES, -1, "探活", 1, 3.0, True, 60.0)
    assert "探活" in line                                   # L13：探活入列
    assert spinner_frame(1) in line                          # 跑圈帧
    assert "3s/60s" in line                                  # L13：_launching 计时尾缀
    idle = render_phase_line(ConnectPanel.PHASES, -1, None, 1, 3.0, False, 60.0)
    assert "s/60s" not in idle                               # 非进行态无尾缀
    assert ConnectPanel.PHASES[0] == "探活" and ConnectPanel.PHASES[-1] == "就绪"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_连接面板壳内嵌_重试复原(monkeypatch: pytest.MonkeyPatch) -> None:
    from tui.app import AstroForgeApp
    from tui.service_client import ServiceClient

    async def fake_health(self):  # noqa: ANN001
        return {"db": True, "ai_engine": True, "version": "test", "uptime_s": 1}

    monkeypatch.setattr(ServiceClient, "health", fake_health)
    app = AstroForgeApp()
    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause()
        app.pop_screen()                                   # 关启动过渡屏
        await pilot.pause()
        await app.show_connect_panel()                     # 壳内嵌换装（L14）
        await pilot.pause()
        panel = app.query_one(ConnectPanel)
        assert panel.query_one("#btn-copy-diag")           # 复制诊断钮在场（L14）
        panel._launching = False
        await panel._retry()                               # 探活成功路径
        deadline_last = 20.0
        while deadline_last > 0 and app.query(ConnectPanel):
            await pilot.pause(0.1)
            deadline_last -= 0.1
        assert not app.query(ConnectPanel)                 # 面板被撤
        children = app.query_one("#content").children
        assert children and children[0].id == "page-home"  # 复原回当前页


@pytest.mark.anyio
async def test_boot超时自然转入壳内嵌连接面板() -> None:
    """回归：boot 探活超时须先换装面板再 pop（pop 后屏 worker 即取消，顺序
    反了面板永远挂不上——2026-10 遗留全清轮实测抓到并修复）。"""
    from tui.app import AstroForgeApp
    from tui.shell.boot import BootScreen
    from tui.shell.connect import ConnectPanel

    app = AstroForgeApp()
    async with app.run_test(size=(110, 34)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, BootScreen)          # 不手动 pop，等超时
        for _ in range(120):                               # 最多 12s（探活超时 5s）
            await pilot.pause(0.1)
            if app.query(ConnectPanel):
                break
        else:
            raise AssertionError("boot 超时未转入壳内嵌连接面板")
        assert app.screen.__class__.__name__ == "Screen"   # 过渡屏已撤
        kids = [c.id for c in app.query_one("#content").children]
        assert kids and kids[0] is None                    # content=连接面板（无 id）


# ============================================================
# L9⑦/L9⑧ · 历史页
# ============================================================

@pytest.mark.anyio
async def test_history行键全uuid_精确匹配(monkeypatch: pytest.MonkeyPatch) -> None:
    from textual.app import App, ComposeResult
    from tui.plugins.history.page import HistoryPage
    from tui.service_client import ServiceClient

    uuid_a, uuid_b = "aaaaaaaa-1111-4", "aaaaaaaa-2222-4"  # 前 8 位相同（旧逻辑碰撞）

    async def fake_list(self, page=1, status=None, page_size=20):  # noqa: ANN001
        return {"items": [
            {"task_uuid": uuid_a, "status": "failed", "task_type": "t",
             "title": "A", "progress": 0, "created_at": None},
            {"task_uuid": uuid_b, "status": "failed", "task_type": "t",
             "title": "B", "progress": 0, "created_at": None},
        ]}

    monkeypatch.setattr(ServiceClient, "list_tasks", fake_list)

    class Host(App):
        env_items: list[dict] = []
        pages: list = []

        def get_css_variables(self) -> dict[str, str]:
            variables = super().get_css_variables()
            variables.update(design.css_variables(design.DEFAULT_THEME))
            variables.update({
                "border-subtle": design.BORDER_LEVELS["subtle"],
                "border-normal": design.BORDER_LEVELS["normal"],
                "border-active": design.BORDER_LEVELS["active"],
                "thinking-opacity": str(design.THINKING_OPACITY),
            })
            return variables

        def compose(self) -> ComposeResult:
            yield HistoryPage(ServiceClient(), None)

    app = Host()
    async with app.run_test(size=(110, 30)) as pilot:
        page = app.query_one(HistoryPage)
        page._app = app
        await page.refresh_table()
        await pilot.pause()
        table = page.query_one("#his-table")
        assert {key.value for key in table.rows} == {uuid_a, uuid_b}  # 行键=完整 uuid


def test_history撤销定时器句柄去重_源码断言() -> None:
    """L9⑦：重试路径只经 _start_undo_timer（先 stop 旧句柄再 set_interval）。"""
    source = (REPO_ROOT / "tui" / "tui" / "plugins" / "history" / "page.py"
              ).read_text(encoding="utf-8")
    assert source.count("self.set_interval(1.0, self._tick_undo)") == 1  # 仅句柄封装内
    assert "self._undo_timer.stop()" in source


# ============================================================
# L15/L16 · 监控页
# ============================================================

def test_monitor_state_alert入队() -> None:
    state = MonitorState.create(warn_gb=10, crit_gb=12)
    state.push_alert({"level": "error", "source": "spider", "message": "任务崩溃",
                      "task_uuid": "u-1"})
    assert state["ws_alerts"][0]["task_uuid"] == "u-1"
    assert state["ws_alerts"][0]["source"] == "spider"


@pytest.mark.anyio
async def test_monitor告警并列与uuid定位() -> None:
    from textual.app import App, ComposeResult
    from tui.plugins.monitor.page import MonitorPage
    from tui.service_client import ServiceClient

    captured: list[str] = []

    async def fake_detail(self, task_uuid):  # noqa: ANN001
        captured.append(task_uuid)
        return {"task_uuid": task_uuid, "status": "failed", "task_type": "spider_site",
                "title": "x", "progress": 0, "steps": []}

    monkey = pytest.MonkeyPatch()
    monkey.setattr(ServiceClient, "task_detail", fake_detail)

    class Host(App):
        env_items: list[dict] = []
        pages: list = []
        monitor_state = MonitorState.create(warn_gb=10.0, crit_gb=12.0)

        def get_css_variables(self) -> dict[str, str]:
            variables = super().get_css_variables()
            variables.update(design.css_variables(design.DEFAULT_THEME))
            variables.update({
                "border-subtle": design.BORDER_LEVELS["subtle"],
                "border-normal": design.BORDER_LEVELS["normal"],
                "border-active": design.BORDER_LEVELS["active"],
                "thinking-opacity": str(design.THINKING_OPACITY),
            })
            return variables

        def switch_page_by_key(self, key: str) -> None:
            pass  # 测试宿主无页面注册表；跳转位由壳层冒烟覆盖

        def compose(self) -> ComposeResult:
            yield MonitorPage(ServiceClient(), None)

    app = Host()
    try:
        async with app.run_test(size=(110, 34)) as pilot:
            page = app.query_one(MonitorPage)
            page._app = app
            page._render_alerts(
                [("warn", "内存 11.0GB 超预警 10GB")],
                [{"level": "error", "source": "spider", "message": "任务崩溃",
                  "task_uuid": "u-42"}],
            )
            await pilot.pause()
            board = page.query_one("#mon-alerts")
            assert board.option_count == 2                  # 本地推导 + WS 事件并列
            assert page._alert_targets["alert-1"] == "u-42"
            page.run_worker(page._open_task_detail("u-42"), exclusive=True)
            await pilot.pause(0.3)
            assert captured == ["u-42"]                     # 按 uuid 拉详情（L16）
    finally:
        monkey.undo()


def test_monitor进程行_交替帧图标序列() -> None:
    from tui.plugins.monitor.page import RUN_ICONS

    assert [design.icon(name) for name in RUN_ICONS] == [
        design.icon("task.running"), design.icon("task.running_f2")]  # ◈/◉


# ============================================================
# L17 · 统一胶囊 chips
# ============================================================

def test_chips_选中aurora底深字() -> None:
    assert "background: $aurora" in ChipBar.DEFAULT_CSS
    assert "color: $onAurora" in ChipBar.DEFAULT_CSS        # 选中=aurora 底深字


@pytest.mark.anyio
async def test_首页快捷入口与监控range用统一胶囊() -> None:
    from textual.app import App, ComposeResult
    from tui.components.chips import ChipAction
    from tui.plugins.home.page import HomePage
    from tui.plugins.monitor.page import MonitorPage
    from tui.service_client import ServiceClient

    class Host(App):
        env_items: list[dict] = []
        pages: list = []

        def get_css_variables(self) -> dict[str, str]:
            variables = super().get_css_variables()
            variables.update(design.css_variables(design.DEFAULT_THEME))
            variables.update({
                "border-subtle": design.BORDER_LEVELS["subtle"],
                "border-normal": design.BORDER_LEVELS["normal"],
                "border-active": design.BORDER_LEVELS["active"],
                "thinking-opacity": str(design.THINKING_OPACITY),
            })
            return variables

        def compose(self) -> ComposeResult:
            yield HomePage(ServiceClient(), None)
            yield MonitorPage(ServiceClient(), None)

    app = Host()
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        home = app.query_one("#page-home", HomePage)
        actions = list(home.query(ChipAction))
        assert {w.id for w in actions} == {"chip-spider", "chip-pipeline",
                                           "chip-cmd", "chip-ai"}  # L17 快捷胶囊化
        app.query_one("#mon-range", ChipBar)               # L17 range 统一 chips
        assert MonitorPage.GATE_DISABLE == ("#mon-range",)
