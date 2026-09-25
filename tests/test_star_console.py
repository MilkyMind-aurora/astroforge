# -*- coding: utf-8 -*-
"""MF3 CLI 星幕渲染器单测（方案 §2.5 / §四 / V1-C.1）。

覆盖：stdout 契约字节（[INFO]/[WARN]/[ERROR] 前缀逐字节）、TTY/非 TTY 双态降级、
tokens 取色（STAR_TOKENS/STAR_ICONS/STAR_MOTION 来自生成段）、错误码→修复指引映射、
cli_utils 收拢转发与收尾卡、shell 脚本横幅入口。
"""
from __future__ import annotations

import io
import re
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "modules" / "_shared"))

import star_console  # noqa: E402,I001
import cli_utils  # noqa: E402,I001

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@pytest.fixture()
def plain_mode():
    """强制纯文本态（字节契约面）；用例结束恢复默认双检测。"""
    star_console.configure(force_plain=True, force_color=False)
    yield
    star_console.reset()


def _capture(fn, *args, **kwargs) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args, **kwargs)
    return buf.getvalue()


# ============================================================
# stdout 字节契约（服务核心逐行捕获所依赖的面）
# ============================================================

def test_log_纯文本前缀逐字节(plain_mode) -> None:
    assert _capture(star_console.log, "INFO", "发现 9 个章节") == "[INFO] 发现 9 个章节\n"
    assert _capture(star_console.log, "ERROR", "入口页抓取失败") == "[ERROR] 入口页抓取失败\n"
    assert _capture(star_console.log, "WARN", "2 页连续 404") == "[WARN] 2 页连续 404\n"


def test_cli_utils_info_error_warn_同字节(plain_mode) -> None:
    assert _capture(cli_utils.info, "单页抓取完成") == "[INFO] 单页抓取完成\n"
    assert _capture(cli_utils.error, "执行异常") == "[ERROR] 执行异常\n"
    assert _capture(cli_utils.warn, "弱警示") == "[WARN] 弱警示\n"


def test_log_无前缀行_脚本标记字节不变(plain_mode) -> None:
    assert _capture(star_console.log, None, "[PASS] 健康检查") == "[PASS] 健康检查\n"


def test_log_富文本态前缀保留且含ANSI() -> None:
    star_console.configure(force_plain=False, force_color=True)
    try:
        raw = _capture(star_console.log, "INFO", "发现 9 个章节")
        assert "\x1b[" in raw, "强制着色态应输出 ANSI"
        assert "[INFO]" in raw, "前缀 span 必须完整保留"
        assert ANSI_RE.sub("", raw) == "[INFO] 发现 9 个章节\n"
    finally:
        star_console.reset()


# ============================================================
# 双态降级（TTY + rich 双检测）
# ============================================================

def test_非TTY默认降级为纯文本() -> None:
    star_console.reset()  # pytest 捕获态 stdout 非 TTY → plain 必须 True
    assert star_console._STATE["plain"] is True
    assert star_console._RICH_OK is True  # 本测试环境 .venv 携带 rich


def test_banner_纯文本格式与空行结构(plain_mode) -> None:
    star = star_console.STAR_ICONS["nav.home"]
    out = _capture(star_console.banner, "spider", "env_spider · spider_site")
    assert out == (
        f"\n  {star} AstroForge · 衍星台 — spider\n"
        f"  Sidereal Core v{star_console.CORE_VERSION} · env_spider · spider_site\n\n"
    )


def test_stage_纯文本含分隔线与阶段行(plain_mode) -> None:
    out = _capture(star_console.stage, "解析侧边栏目录", 2, 5)
    star = star_console.STAR_ICONS["nav.home"]
    assert star in out and out.splitlines()[0].startswith("─") and out.splitlines()[0].endswith("─")
    assert star_console.STAR_ICONS["task.running"] in out
    assert "阶段 2/5 · 解析侧边栏目录" in out


def test_progress_非TTY静默_管道里禁止回车重绘(plain_mode) -> None:
    out = _capture(star_console.progress, 24, 52, "爬取进度")
    assert out == "", "非 TTY 下进度条必须静默（\\r 会污染服务核心逐行捕获）"


def test_progress_TTY无rich走ASCII条(monkeypatch) -> None:
    monkeypatch.setattr(star_console, "_IS_TTY", True)
    monkeypatch.setattr(star_console, "_RICH_OK", False)
    star_console.configure(force_plain=True, force_color=False)
    try:
        out = _capture(star_console.progress, 24, 52, "爬取进度")
        assert "\r" not in out, "ASCII 条逐行输出，不得带回车重绘（管道安全）"
        assert out.endswith("\n")
        assert "█" in out and "░" in out and "24/52 · 46%" in out
        # 节流窗口内不重绘（tokens motion.cli.progress_throttle_ms=100）
        assert _capture(star_console.progress, 25, 52, "爬取进度") == ""
        final = _capture(star_console.progress, 52, 52, "爬取进度")  # 完成态不被节流
        assert "52/52 · 100%" in final and final.endswith("\n")
    finally:
        star_console.reset()


def test_result_card_纯文本(plain_mode) -> None:
    out = _capture(star_console.result_card, "任务完成",
                   items=[("_index.json", "output/site"), ("introduction.md", "")],
                   note="52 项 · 耗时 128s")
    assert out.startswith(f"{star_console.STAR_ICONS['task.success']} 任务完成 · 52 项 · 耗时 128s\n")
    assert "产物 2 项" in out and "_index.json  output/site" in out
    assert star_console.STAR_ICONS["nav.home"] in out


def test_result_items_产物超限折叠() -> None:
    data = {"files": [f"/out/file_{i}.md" for i in range(12)]}
    rows = cli_utils._result_items(data)
    assert len(rows) == star_console.ITEM_LIMIT
    assert rows[-1] == ("…其余 5 项", "")
    assert rows[0][0] == "file_0.md"


def test_error_card_纯文本含修复指引(plain_mode) -> None:
    out = _capture(star_console.error_card, 3004, "整站爬取未获得任何页面")
    assert f"{star_console.STAR_ICONS['status.error']} 失败 · code 3004" in out
    assert "整站爬取未获得任何页面" in out
    assert "修复指引: " in out and "反爬" in out


def test_富文本态结果卡与错误卡() -> None:
    star_console.configure(force_plain=False, force_color=True)
    try:
        raw = _capture(star_console.result_card, "任务完成", items=[("_index.json", "")])
        stripped = ANSI_RE.sub("", raw)
        # 沙盒为 legacy 控制台时 rich 降级直角盒线（┌）；真实 WT 下为圆角（╭）——两种都算盒式
        assert ("│" in stripped and "─" in stripped and "✓ 任务完成" in stripped)
        raw_err = _capture(star_console.error_card, 3003, "模块执行异常")
        assert ANSI_RE.sub("", raw_err).count("修复指引") == 1
    finally:
        star_console.reset()


# ============================================================
# tokens 取色（值一律来自生成段）
# ============================================================

def test_色值与节流参数来自生成段() -> None:
    assert star_console.STAR_TOKENS["dark"]["aurora"] == "#4EE0C0"     # §1.1 夜档极光青
    assert star_console.STAR_TOKENS["light"]["aurora"] == "#0C9B7E"
    assert star_console.STAR_TOKENS["dark"]["nova"] == "#FF5648"
    assert star_console.STAR_MOTION["progress_throttle_ms"] == 100     # §1.4 CLI 节流
    assert star_console.STAR_MOTION["spinner_frame_ms"] == 80


def test_取色随主题档切换() -> None:
    star_console.configure(force_plain=True, theme="dark")
    assert star_console._c("aurora") == "#4EE0C0"
    star_console.configure(theme="light")
    assert star_console._c("aurora") == "#0C9B7E"
    star_console.reset()


def test_configure_未知主题拒绝() -> None:
    with pytest.raises(ValueError, match="未知色彩档"):
        star_console.configure(theme="no-such")


def test_星符一律经语义名() -> None:
    for path in ("nav.home", "task.success", "task.running", "status.error"):
        assert star_console.STAR_ICONS[path], f"缺少语义名 {path}"


# ============================================================
# 错误码 → 修复指引映射表（pro 7.3.2）
# ============================================================

def test_已登记错误码逐一有指引() -> None:
    for code, guide in star_console.ERROR_GUIDES.items():
        assert star_console.fix_guide(code) == guide
        assert len(guide) >= 12, f"code {code} 指引过于简略"


def test_关键错误码映射内容() -> None:
    assert "反爬" in star_console.fix_guide(3004)
    assert "conda" in star_console.fix_guide(3001).lower() or "install_envs" in star_console.fix_guide(3001)
    assert "install_anydoc" in star_console.fix_guide(4004)
    assert "download_models" in star_console.fix_guide(3005)
    assert "无需修复" in star_console.fix_guide(1300)
    assert "无需修复" in star_console.fix_guide(0)


def test_未登记错误码回落分段指引() -> None:
    assert "1xxx" in star_console.fix_guide(1999)
    assert "3xxx" in star_console.fix_guide(3999)
    assert "未登记" in star_console.fix_guide(9999)  # 未知分段兜底


# ============================================================
# cli_utils 收尾卡（announce_result）
# ============================================================

def test_announce_result_成功走结果卡(plain_mode) -> None:
    result = {"code": 0, "message": "ok", "data": {"files": ["/out/a.md", "/out/b.md"], "count": 2}}
    out = _capture(cli_utils.announce_result, result, 3.2)
    assert "任务完成 · 2 项 · 耗时 3s" in out
    assert "a.md  \\out" in out or "a.md  /out" in out


def test_announce_result_失败走错误行加错误卡(plain_mode) -> None:
    result = {"code": 1001, "message": "缺少 url 参数", "data": None}
    out = _capture(cli_utils.announce_result, result)
    assert "[ERROR] 缺少 url 参数（code 1001）\n" in out  # 失败必有错误档标记行
    assert "失败 · code 1001" in out and "修复指引" in out


def test_announce_result_产物清单超限折叠(plain_mode) -> None:
    result = {"code": 0, "message": "ok",
              "data": {"files": [f"/out/p{i}.md" for i in range(30)]}}
    out = _capture(cli_utils.announce_result, result)
    assert "产物 8 项" in out and "…其余 23 项" in out


# ============================================================
# shell 脚本横幅入口（__main__）
# ============================================================

def test_main_banner入口(capsys) -> None:
    assert star_console._main(["banner", "check_env", "环境体检"]) == 0
    out = capsys.readouterr().out
    assert "AstroForge · 衍星台 — check_env" in out and "环境体检" in out


def test_main_缺子命令退出码非零() -> None:
    with pytest.raises(SystemExit):
        star_console._main([])
