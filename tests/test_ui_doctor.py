# -*- coding: utf-8 -*-
"""ui_doctor CLI 面回归测试：编排门禁以 `ui_doctor.py --quick` 等命令行入口调用，
本文件锁参数面（--quick 可解析、与 --full 互斥、未知 skip 拒绝），不执行检查本体。
另锁纯函数/grep 断言面：裸色正则（6/8 位 hex）、截图清单、聚焦盒 aurora 变量。
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import ui_doctor  # noqa: E402,I001


def test_quick_参数可解析() -> None:
    args = ui_doctor.build_parser().parse_args(["--quick"])
    assert args.quick is True and args.full is False


def test_quick_与_full_互斥退出码2(capsys) -> None:
    assert ui_doctor.main(["--quick", "--full"]) == 2
    assert "互斥" in capsys.readouterr().out


def test_list_列出全部检查项(capsys) -> None:
    assert ui_doctor.main(["--list"]) == 0
    out = capsys.readouterr().out
    for name in ("pytest", "ruff", "gen-idempotent", "screenshots-check", "placeholder",
                 "bare-color", "focus-aurora", "bare-print", "app-bare-color",
                 "flutter-analyze", "flutter-test"):
        assert name in out, f"--list 缺检查项 {name}"


def test_未知skip_拒绝退出码2(capsys) -> None:
    assert ui_doctor.main(["--skip=nope"]) == 2
    assert "未知检查项" in capsys.readouterr().out


# ============================================================
# 裸色正则（§3.7 ①：#RRGGBB 与 #AARRGGBB 双形态）
# ============================================================

def test_裸色正则_6位与8位hex双形态() -> None:
    assert ui_doctor.HEX_RE.search("color: #EDF0FB;")          # #RRGGBB
    assert ui_doctor.HEX_RE.search("border: round #4EE0C0;")
    assert ui_doctor.HEX_RE.search("Color(0xFF5648) 用 #FF5648FF 直写也命中")  # #AARRGGBB
    assert ui_doctor.HEX_RE.search("#172C32FF")
    assert not ui_doctor.HEX_RE.search("#FFF")                  # 3 位不属本门禁语义
    assert not ui_doctor.HEX_RE.search("无色值注释行")
    assert not ui_doctor.HEX_RE.search("#GGHHII")               # 非 hex 字符不命中


def test_裸色检查_8位argb也判失败(tmp_path: Path, monkeypatch) -> None:
    tui = tmp_path / "tui"
    tui.mkdir()
    (tui / "page.py").write_text("CSS = 'Input:focus { border: round #4EE0C0FF; }'\n",
                                 encoding="utf-8")
    monkeypatch.setattr(ui_doctor, "REPO_ROOT", tmp_path)
    ok, note = ui_doctor.check_bare_color()
    assert ok is False and "1 处命中" in note


# ============================================================
# screenshots-check：双主题截图清单核对（§5.8 ④）
# ============================================================

def _make_shots(repo: Path, names: tuple[str, ...]) -> None:
    shots = repo / "docs" / "design" / "screenshots"
    shots.mkdir(parents=True)
    for name in names:
        (shots / name).write_bytes(b"png")


def test_screenshots_check_清单齐全判过(tmp_path: Path, monkeypatch) -> None:
    _make_shots(tmp_path, ui_doctor.EXPECTED_SCREENSHOTS)
    monkeypatch.setattr(ui_doctor, "REPO_ROOT", tmp_path)
    ok, note = ui_doctor.check_screenshots()
    assert ok is True
    assert str(len(ui_doctor.EXPECTED_SCREENSHOTS)) in note


def test_screenshots_check_缺失列出并判失败(tmp_path: Path, monkeypatch) -> None:
    flutter_only = tuple(
        f"{theme}_{page}.png"
        for theme in ui_doctor.SCREENSHOT_THEMES
        for page in ui_doctor.SCREENSHOT_PAGES
    )
    _make_shots(tmp_path, flutter_only)          # 只补 Flutter 10 张，TUI 两张缺失
    monkeypatch.setattr(ui_doctor, "REPO_ROOT", tmp_path)
    ok, note = ui_doctor.check_screenshots()
    assert ok is False
    assert "tui_dark.png" in note and "tui_light.png" in note


# ============================================================
# focus-aurora：聚焦盒描边=aurora 生成变量（§3.7 ⑦）
# ============================================================

def test_focus_aurora_真实仓库聚焦描边全走变量() -> None:
    ok, note = ui_doctor.check_focus_aurora()
    assert ok is True, note
    assert "$border-active" in note


def test_focus_aurora_裸色或缺变量引用判失败(tmp_path: Path, monkeypatch) -> None:
    tui = tmp_path / "tui"
    gen = tui / "theme" / "generated"
    gen.mkdir(parents=True)
    (gen / "tokens.tcss").write_text(".border-active { border: round #4EE0C0; }\n",
                                     encoding="utf-8")
    (tui / "page.py").write_text(
        "CSS = 'Input:focus { border: round #FF5648; }'\n",   # 聚焦行裸色
        encoding="utf-8")
    monkeypatch.setattr(ui_doctor, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(ui_doctor, "GEN_DIR", gen)
    ok, note = ui_doctor.check_focus_aurora()
    assert ok is False
    assert "裸色" in note and "$aurora" in note
