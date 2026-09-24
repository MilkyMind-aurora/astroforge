# -*- coding: utf-8 -*-
"""ui_doctor CLI 面回归测试：编排门禁以 `ui_doctor.py --quick` 等命令行入口调用，
本文件锁参数面（--quick 可解析、与 --full 互斥、未知 skip 拒绝），不执行检查本体。
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
    for name in ("pytest", "ruff", "gen-idempotent", "placeholder", "bare-color",
                 "bare-print", "app-bare-color", "flutter-analyze", "flutter-test"):
        assert name in out, f"--list 缺检查项 {name}"


def test_未知skip_拒绝退出码2(capsys) -> None:
    assert ui_doctor.main(["--skip=nope"]) == 2
    assert "未知检查项" in capsys.readouterr().out
