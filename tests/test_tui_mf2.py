# -*- coding: utf-8 -*-
"""MF2 TUI 单元测试：插件机制 / 任务进度卡 / 步骤时间线 / chips / 台词库 /
AI 抽屉合批与日志面板纯函数（不依赖服务与终端；壳行数门禁 grep 断言）。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tui"))

import pytest  # noqa: E402
from tui.components.chips import ChipBar  # noqa: E402
from tui.components.task_card import bar_fill, bar_width  # noqa: E402
from tui.components.timeline import render_step  # noqa: E402
from tui.panels.ai_drawer import take_batch  # noqa: E402
from tui.panels.log_panel import detect_level, sort_tasks  # noqa: E402
from tui.plugins import (  # noqa: E402
    PagePlugin,
    collect_plugins,
    entry_point_plugins,
    load_pages_overrides,
)
from tui.plugins.history.page import duration_text, local_time  # noqa: E402
from tui.plugins.settings.page import quote_preview  # noqa: E402
from tui.theme.generated import tokens as design  # noqa: E402
from tui.ui.mascot import get_quote, load_quotes  # noqa: E402

# ============================================================
# 插件机制（§2.4 / V1-B.3）
# ============================================================

def test_插件注册表_8页有序且星符语义名合法() -> None:
    pages = collect_plugins()
    assert [p.key for p in pages] == [
        "home", "spider", "parser", "converter", "pipeline", "monitor", "history", "settings"]
    for plugin in pages:
        assert plugin.icon in design.ICONS          # 星符全部经 icons.yaml（门禁④）
        assert callable(plugin.factory)
        assert plugin.title


def test_entry_points_与内置同键去重() -> None:
    eps = entry_point_plugins()
    pages = collect_plugins()
    assert len(pages) == len({p.key for p in pages})   # 同 key 去重，无双条目
    # entry_points 提供的键都在 collect 结果里（同 key 内置优先）
    assert {ep.key for ep in eps} <= {p.key for p in pages}


def test_pages_yaml_覆盖_显隐与排序() -> None:
    overrides = load_pages_overrides()
    assert overrides and overrides["monitor"].get("visible") is True
    hidden = collect_plugins({**overrides, "monitor": {"visible": False}})
    assert "monitor" not in [p.key for p in hidden]
    reordered = collect_plugins({**overrides, "monitor": {"order": 0}})
    assert reordered[0].key == "monitor"
    # 空覆盖=全部可见按 sort
    assert [p.key for p in collect_plugins({})] == [
        "home", "spider", "parser", "converter", "pipeline", "monitor", "history", "settings"]


def test_插件契约_星符语义名未注册即拒绝() -> None:
    with pytest.raises(ValueError, match="星符语义名未注册"):
        PagePlugin(key="x", title="X", icon="nope.nope", sort=99, factory=lambda: None)
    with pytest.raises(ValueError, match="key 非法"):
        PagePlugin(key="Bad Key", title="X", icon="nav.home", sort=99, factory=lambda: None)


def test_壳层行数门禁_300行以内() -> None:
    app_lines = (REPO_ROOT / "tui" / "tui" / "app.py").read_text(encoding="utf-8").splitlines()
    assert len(app_lines) <= 300, f"app.py {len(app_lines)} 行 > 300（V1-B.3 门禁）"


# ============================================================
# 任务进度卡（§3.3 / V1-T.2.5）
# ============================================================

def test_进度条_填充前推与过冲回落() -> None:
    assert bar_fill(0, 10) == "░" * 10 + " 0%"
    assert bar_fill(50, 10) == "█" * 5 + "░" * 5 + " 50%"
    assert bar_fill(100, 10) == "█" * 10 + " 100%"
    assert bar_fill(120, 10) == "█" * 10 + " 100%"       # 越界钳制
    assert bar_fill(50, 0) == "50%"                       # 未布局回落


def test_进度条宽度_终端纪律() -> None:
    assert bar_width(200) == 40          # min(终端宽-20, 40) 上限
    assert bar_width(60) == 40           # 60-20=40
    assert bar_width(50) == 30
    assert bar_width(20) == 10           # 下限


def test_take_batch_合批取样() -> None:
    assert take_batch("abcdef", 3) == ("abc", "def")
    assert take_batch("ab", 3) == ("ab", "")
    assert take_batch("", 3) == ("", "")
    assert take_batch("abc", 0) == ("", "abc")


# ============================================================
# 步骤时间线（§3.4）
# ============================================================

def test_步骤行渲染_四态星符语义() -> None:
    def step(status: str) -> dict:
        return {"step_index": 0, "step_name": "转换 DOCX", "status": status}

    pending = render_step(step("pending"))
    running = render_step(step("running"))
    success = render_step(step("success"))
    failed = render_step(step("failed"))
    assert design.icon("task.pending") in pending
    assert design.icon("task.step_cursor") in running and design.icon("task.running") in running
    assert design.icon("task.success") in success and design.icon("status.ok") in success
    assert design.icon("task.failed") in failed
    # 帧动画：running 帧轮换 ◈→◉
    assert design.icon("task.running_f2") in render_step(step("running"), running_frame=1)


# ============================================================
# chips / 历史（§3.5）
# ============================================================

def test_chips_选项结构_全部默认选中() -> None:
    bar = ChipBar([(None, "全部"), ("running", "运行")])
    assert bar.selected is None


def test_耗时与时刻解析() -> None:
    assert duration_text("2026-09-25T10:00:00+08:00", "2026-09-25T10:01:05+08:00") == "01:05"
    assert duration_text(None, None) == "-"
    assert local_time("2026-09-25T10:00:00+08:00") != "-"   # 本地时区渲染
    assert local_time("垃圾") == "-"


def test_日志级别判定_字段优先文本兜底() -> None:
    assert detect_level("ERROR", "[INFO] x") == "ERROR"
    assert detect_level(None, "[WARN] 内存爬升") == "WARN"
    assert detect_level(None, "[ERROR] 崩了") == "ERROR"
    assert detect_level(None, "普通行") == "INFO"


def test_任务切换排序_运行中优先于失败() -> None:
    items = [
        {"task_uuid": "s", "status": "success", "created_at": "2026-09-25T10:00:00"},
        {"task_uuid": "f", "status": "failed", "created_at": "2026-09-25T11:00:00"},
        {"task_uuid": "r", "status": "running", "created_at": "2026-09-25T09:00:00"},
    ]
    assert [t["task_uuid"] for t in sort_tasks(items)] == ["r", "f", "s"]


# ============================================================
# 台词库（quotes.yaml 唯一事实源）
# ============================================================

def test_台词库_yaml加载与兼容映射() -> None:
    quotes = load_quotes()
    assert quotes["boot"] and quotes["task_fail"]
    assert all(len(line) <= 24 for lines in quotes.values() for line in lines)


def test_台词抽样_深夜改投与缺组回落() -> None:
    pool = {"boot": ["氢料就位。", "恒星入列。"], "midnight": ["银河劝你休息。"],
            "idle_long": ["守炉中。"]}
    # 深夜 + 命中概率 → midnight 池
    got = [get_quote("boot", now_hour=2, pool=pool) for _ in range(200)]
    assert "银河劝你休息。" in got                       # 改投发生过
    assert set(got) <= {"氢料就位。", "恒星入列。", "银河劝你休息。"}
    # 白天绝不投 midnight
    day = {get_quote("boot", now_hour=12, pool=pool) for _ in range(50)}
    assert "银河劝你休息。" not in day
    # 缺组回落 idle_long
    assert get_quote("task_fail", now_hour=12, pool=pool) == "守炉中。"


def test_设置页台词预览() -> None:
    preview = quote_preview("boot", limit=2)
    assert preview and preview.count("｜") <= 1


# ============================================================
# AI 抽屉模型胶囊清单（§3.6）
# ============================================================

def test_模型胶囊_两档清单与服务端同源() -> None:
    from tui.panels.ai_drawer import MODELS

    assert [key for key, _cap in MODELS] == ["qwen2b", "ornith9b"]
    from astroforge.api.routes_ai import KNOWN_MODELS

    assert {key for key, _cap in MODELS} == set(KNOWN_MODELS)


# ============================================================
# 壳层冒烟（run_test 无终端：挂载/CSS 编译/插件页换装/抽屉；探活失败不阻断）
# ============================================================

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_时间线_空起步重建与失败态联动() -> None:
    from textual.app import App, ComposeResult

    from tui.components.timeline import StepTimeline

    class Host(App):
        """注入设计变量的最小宿主（等价 AstroForgeApp.get_css_variables）。"""

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
            yield StepTimeline(None, "uuid-1", [], title="t", allow_retry=True)

    app = Host()
    async with app.run_test(size=(80, 24)) as pilot:
        timeline = app.query_one(StepTimeline)
        assert not list(timeline.query(".step-row"))          # 空起步
        await timeline.set_steps([
            {"step_index": 0, "step_name": "a", "status": "success"},
            {"step_index": 1, "step_name": "b", "status": "failed"},
        ])
        await pilot.pause()
        assert len(list(timeline.query(".step-row"))) == 2    # 0→N 重建
        assert list(timeline.query(".step-retry"))            # 失败步骤有重试钮
        await timeline.set_steps([
            {"step_index": 0, "step_name": "a", "status": "success"},
            {"step_index": 1, "step_name": "b", "status": "running"},
        ])
        await pilot.pause()
        assert not list(timeline.query(".step-retry"))        # 离开失败态撤钮
        await timeline.set_steps([
            {"step_index": 0, "step_name": "a", "status": "success"},
            {"step_index": 1, "step_name": "b", "status": "failed"},
        ])
        await pilot.pause()
        assert list(timeline.query(".step-retry"))            # 重新失败恢复重试钮


@pytest.mark.anyio
async def test_壳层冒烟_8页换装与抽屉唤起() -> None:
    import time as _time

    from tui.app import AstroForgeApp
    from tui.panels.ai_drawer import AiDrawerScreen
    from tui.panels.log_panel import LogPanelScreen
    from tui.plugins.home.page import HomePage
    from tui.shell.boot import BootScreen

    def _page_mounted(app, key: str) -> bool:
        children = app.query_one("#content").children
        return bool(children) and children[0].id == f"page-{key}"

    async def wait_page(app, key: str, timeout_s: float) -> None:
        """换装是异步 worker：轮询至目标页出现（合并跑套件时机器更慢）。"""
        deadline = _time.monotonic() + timeout_s
        while _time.monotonic() < deadline:
            if _page_mounted(app, key):
                return
            await pilot.pause(0.05)
        raise AssertionError(f"页面 {key} 未在 {timeout_s}s 内挂载")

    app = AstroForgeApp()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert isinstance(app.screen, BootScreen)
        app.pop_screen()                       # 关闭启动屏（探活 worker 随后台循环自然结束）
        await pilot.pause()
        assert isinstance(app.query_one("#page-home"), HomePage)
        # 数字键 1-8 逐页换装（换装走 exclusive worker；每次切换前等过 30ms
        # 去抖窗，避免按键被丢弃；换装完成以轮询判定）
        for index, plugin in enumerate(app.pages):
            await pilot.pause(0.1)
            app.switch_page(index)
            await wait_page(app, plugin.key, timeout_s=10.0)
        # AI 抽屉与日志面板挂载（各自 CSS 编译即校验）
        app.action_ai_panel()
        await pilot.pause()
        assert isinstance(app.screen, AiDrawerScreen)
        app.pop_screen()
        app.action_toggle_log()
        await pilot.pause()
        assert isinstance(app.screen, LogPanelScreen)
