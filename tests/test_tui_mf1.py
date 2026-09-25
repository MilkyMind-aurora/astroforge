# -*- coding: utf-8 -*-
"""MF1 TUI 单元测试：壳层/首页/监控看板的纯函数逻辑（不依赖服务与终端）。

覆盖：问候语分段、体检格位语义、KPI 渲染与内存阈值分档（>warn 熔金 / >crit nova）、
告警推导、进程环境推断、MonitorState 滚动窗口与磁盘速率差分、星野确定性渲染、
Textual 主题装配（tokens → $语义变量）、导航键去抖常量取自 tokens 生成物。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tui"))

import pytest  # noqa: E402
from tui.app import (  # noqa: E402
    NAV_DEBOUNCE_S,
    NAV_HEALTH,
    PAGES,
    _seg,
    _spinner_frame,
)
from tui.pages.home import check_glyph, greeting_by_hour, render_grid  # noqa: E402
from tui.pages.monitor import (  # noqa: E402
    MonitorState,
    derive_alerts,
    format_kpi_row,
    infer_env,
    mem_severity,
    scan_processes,
)
from tui.theme import astro_theme  # noqa: E402
from tui.theme.generated import tokens as design  # noqa: E402
from tui.ui.starfield import render_starfield  # noqa: E402

# ============================================================
# 首页（§3.2）
# ============================================================

def test_问候语三段() -> None:
    assert greeting_by_hour(7) == "早安，指挥官"
    assert greeting_by_hour(12) == "午安，指挥官"
    assert greeting_by_hour(14) == "午安，指挥官"
    assert greeting_by_hour(20) == "晚上好，指挥官"
    assert greeting_by_hour(3) == "晚上好，指挥官"


def test_体检格位语义_成功缺失异常() -> None:
    ok = check_glyph({"ok": True, "detail": "连通正常"})
    miss = check_glyph({"ok": False, "detail": "未配置（platform_overrides…）"})
    err = check_glyph({"ok": False, "detail": "连接失败（检查服务与 ASTROFORGE_PG_PASSWORD）"})
    assert ok == ("task.success", "aurora")   # ✓ 极光
    assert miss == ("task.pending", "ink-400")  # ○ 占位灰（缺失）
    assert err == ("task.failed", "nova")     # ✕ nova（异常）


def test_九宫格三列等宽() -> None:
    items = [{"name": f"项{i}", "ok": True, "detail": "d"} for i in range(7)]
    lines = render_grid(items)
    assert len(lines) == 3  # 7 项 → 3 行（3+3+1）
    assert all("✓" in line or line.strip() == "" for line in lines)


# ============================================================
# 监控看板（§3.4）
# ============================================================

def _sample(mem_gb: float, cpu: float = 10.0) -> dict:
    return {"cpu_percent": cpu, "mem_used_gb": mem_gb,
            "mem_percent": round(mem_gb / 16 * 100, 1),
            "disk_read_mbps": 0.0, "disk_write_mbps": 0.0, "active_processes": 1}


def test_内存阈值分档_熔金与朱红() -> None:
    assert mem_severity(8.2, 10, 12) == "ink-900"   # 正常
    assert mem_severity(10.5, 10, 12) == "molten"   # >10GB 熔金
    assert mem_severity(12.5, 10, 12) == "nova"     # >12GB 朱红


def test_KPI行_等宽数字与运行任务星符() -> None:
    line = format_kpi_row(_sample(8.2, 33.3), running=2, warn_gb=10, crit_gb=12,
                          read_mbps=1.5, write_mbps=2.5)
    assert "33.3%" in line and "8.2GB" in line and "1.5" in line and "2.5" in line
    assert design.icon("task.running") in line


def test_告警推导_红线与通道断开() -> None:
    crit = derive_alerts(_sample(13.0), 10, 12, ws_connected=True)
    warn = derive_alerts(_sample(11.0), 10, 12, ws_connected=True)
    calm = derive_alerts(_sample(8.0), 10, 12, ws_connected=True)
    off = derive_alerts(_sample(8.0), 10, 12, ws_connected=False)
    assert crit == [("error", "内存 13.0GB 超红线 12GB，建议收任务")]
    assert warn == [("warn", "内存 11.0GB 超预警 10GB")]
    assert calm == []
    assert off[0] == ("warn", "监控通道 /ws/monitor 断开，等待重连（数据已冻结）")


def test_进程环境推断() -> None:
    assert infer_env(["python", "D:/repo/modules/spider/cli.py"]) == "env_spider"
    assert infer_env(["python", "-m", "x"]) == "-"
    assert infer_env(["python", "D:/Apps/astroforge/server/__main__.py"]) == "env_astroforge"
    # 模块路径优先于解释器所在环境
    assert infer_env(
        ["D:/envs/env_mineru/python.exe", "D:/repo/modules/wpd/cli.py"]) == "env_wpd"
    # 解释器路径含 env_<name>/ 显式命中
    assert infer_env(["D:/envs/env_wpd/python.exe", "-m", "x"]) == "env_wpd"


class _FakeProc:
    def __init__(self, pid: int, cmdline: list[str], rss_mb: float) -> None:
        self.info = {"pid": pid, "name": "python", "cmdline": cmdline,
                     "memory_info": type("M", (), {"rss": int(rss_mb * 1024 * 1024)})()}
        self._cpu = 4.2

    def cpu_percent(self, interval: float | None = None) -> float:
        return self._cpu


def test_进程扫描_仓库过滤与排序(monkeypatch: pytest.MonkeyPatch) -> None:
    import psutil

    root = str(REPO_ROOT)
    procs = [
        _FakeProc(1, ["python", f"{root}/modules/spider/cli.py"], 500.0),
        _FakeProc(2, ["notepad.exe"], 100.0),              # 与仓库无关 → 过滤
        _FakeProc(3, ["python", f"{root}/server/__main__.py"], 900.0),
    ]
    monkeypatch.setattr(psutil, "process_iter", lambda *_a, **_k: procs)
    rows = scan_processes(limit=10)
    assert [r["pid"] for r in rows] == [3, 1]              # 内存降序
    assert rows[0]["env"] == "env_astroforge"
    assert rows[1]["env"] == "env_spider"
    assert rows[1]["module_task"] is True                  # 模块 cli.py 行前置 ◈


def test_MonitorState_滚动窗口与磁盘速率差分() -> None:
    state = MonitorState.create(warn_gb=10, crit_gb=12)
    state.ingest(_sample(8.0))
    state["prev_ts"] -= 0.5  # 模拟 0.5s 间隔
    state.ingest({**_sample(9.0), "disk_read_mbps": 10.0, "disk_write_mbps": 4.0})
    assert len(state["cpu_window"]) == 2 and len(state["mem_window"]) == 2
    assert state["read_mbps"] == pytest.approx(20.0)   # (10-0)MB / 0.5s
    assert state["write_mbps"] == pytest.approx(8.0)
    state["prev_ts"] -= 0.5
    state.ingest({**_sample(9.0), "disk_read_mbps": 2.0})  # 计数回绕 → 不出负速率
    assert state["read_mbps"] == 0.0


# ============================================================
# 星野（§3.2 hero 框，静态禁循环动画）
# ============================================================

def test_星野渲染_确定性与空种子() -> None:
    stars = [{"x": 0.1, "y": 0.0, "tier": 2}, {"x": 0.9, "y": 0.2, "tier": 0}]
    a = render_starfield(width=20, rows=2, stars=stars)
    b = render_starfield(width=20, rows=2, stars=stars)
    assert a == b, "同 seed 同尺寸必须同画面（预生成禁随机）"
    assert design.icon("misc.star_rank_1") in a and design.icon("misc.star_dim") in a
    assert render_starfield(width=20, rows=2, stars=[]) == "\n"  # 空种子=空框不炸
    assert render_starfield(width=0, rows=2) == ""


# ============================================================
# 设计契约接线（tokens 唯一来源）
# ============================================================

def test_主题装配_tokens到语义变量() -> None:
    theme = astro_theme.build_theme("deep-space")
    palette = design.css_variables("deep-space")
    assert theme.primary == palette["aurora"]      # aurora=全局唯一主强调
    assert theme.secondary == palette["nebula"]    # nebula 仅 AI 位
    assert theme.error == palette["nova"]
    assert theme.dark is True
    # 盒式语言边框三档（V1.2-1）：active=aurora
    assert theme.variables["border-active"] == design.BORDER_LEVELS["active"] == palette["aurora"]
    assert theme.variables["border-subtle"] == palette["faint"]
    with pytest.raises(ValueError, match="未知主题"):
        design.css_variables("nope")


def test_导航去抖与跑圈取自生成物() -> None:
    assert NAV_DEBOUNCE_S == design.INTERACTION["keyboard"]["nav_debounce_ms"] / 1000 == 0.03
    assert [_spinner_frame(i) for i in range(4)] == [
        design.icon(f"misc.spinner_f{i}") for i in range(1, 5)]
    assert _seg("x", "aurora") == "[$aurora]x[/]"


def test_导航表_8页与体检映射齐备() -> None:
    assert [key for key, _i, _l in PAGES] == [
        "home", "spider", "parser", "converter", "pipeline", "monitor", "history", "settings"]
    assert set(NAV_HEALTH) == {key for key, _i, _l in PAGES}
