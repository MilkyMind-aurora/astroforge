# -*- coding: utf-8 -*-
"""MF3 模块 CLI 契约测试（方案 §4.2 门禁 ①②：裸 print=0 + JSON 契约回归 + 双态降级）。

以子进程方式非 TTY 运行 5 个模块 CLI（fail-fast 配置，零出网、零子进程依赖），
锁定 stdout 契约（方案 §2.5【硬性】）：
  1. 非 TTY 管道态一律纯文本：无 ANSI 转义、无 ``\\r`` 重绘（服务核心逐行捕获兼容）；
  2. ``[ERROR] `` 前缀行存在（task_scheduler._make_line_callback 按 ``[ERROR]`` 判档）；
  3. 结果 JSON 恰为 {"code", "message", "data"} 三键（cli_utils.save_json 契约）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# (模块名, cli 相对路径, fail-fast 配置)——全部走参数校验失败路径，无网络无重依赖
CASES = {
    "spider": ("modules/spider/cli.py", {"task_type": "spider_single"}),
    "mineru": ("modules/mineru/cli.py", {}),
    "wpd": ("modules/wpd/cli.py", {}),
    "anydoc": ("modules/anydoc/cli.py", {}),
    "md2docx": ("modules/md2docx/cli.py", {}),
}


def _run_cli(script_rel: str, config: dict) -> tuple[subprocess.CompletedProcess, dict]:
    script = (REPO_ROOT / script_rel).resolve()
    with tempfile.TemporaryDirectory() as td:
        config_path = Path(td) / "config.json"
        result_path = Path(td) / "result.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        # 强制 utf-8 管道编码，消除 Windows 本地编码差异（契约断言与编码解耦）
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        proc = subprocess.run(
            [sys.executable, str(script), "--config", str(config_path), "--output", str(result_path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, env=env, cwd=str(script.parent),
        )
        assert result_path.exists(), f"{script_rel} 未写结果 JSON：{proc.stdout}\n{proc.stderr}"
        result = json.loads(result_path.read_text(encoding="utf-8"))
    return proc, result


# ============================================================
# §4.2 门禁 ①：modules/*/cli.py 裸 print( = 0（输出一律经 star_console/cli_utils）
# ============================================================

def test_模块cli_裸print清零() -> None:
    hits = []
    for cli in sorted((REPO_ROOT / "modules").glob("*/cli.py")):
        for lineno, line in enumerate(cli.read_text(encoding="utf-8").splitlines(), 1):
            if "print(" in line:
                hits.append(f"{cli.relative_to(REPO_ROOT)}:{lineno}")
    assert not hits, f"cli.py 出现裸 print（违反 §4.2 ①）: {hits}"


# ============================================================
# §4.2 门禁 ②：非 TTY 端到端——stdout 纯文本 + [ERROR] 判档 + 结果 JSON 三键
# ============================================================

@pytest.mark.parametrize("name", sorted(CASES))
def test_模块CLI_非TTY_stdout契约(name: str) -> None:
    script_rel, config = CASES[name]
    proc, result = _run_cli(script_rel, config)

    assert set(result) == {"code", "message", "data"}, f"{name} 结果 JSON 键漂移: {result}"
    assert result["code"] != 0, f"{name} fail-fast 配置应失败: {result}"
    assert proc.returncode == 1, f"{name} 退出码契约（失败=1）: {proc.returncode}"

    out = proc.stdout
    assert "\x1b" not in out, f"{name} 非 TTY 输出混入 ANSI 转义（降级纪律破坏）"
    assert "\r" not in out, f"{name} 非 TTY 输出混入 \\r 重绘（逐行捕获兼容破坏）"
    assert "[ERROR] " in out, f"{name} 失败任务缺 [ERROR] 判档行: {out!r}"
    assert "AstroForge · 衍星台" in out, f"{name} 缺星幕横幅: {out!r}"
    assert "修复指引" in out, f"{name} 失败缺错误码→修复指引: {out!r}"

    # 服务核心 _make_line_callback 判档语义复演：失败行能被 [ERROR] 命中
    levels = ["ERROR" if "[ERROR]" in line else "INFO" for line in out.splitlines()]
    assert "ERROR" in levels


def test_子进程非TTY自动降级_无需配置() -> None:
    """不设任何环境变量时，管道态也必须自动纯文本（isatty 双检测生效）。"""
    script_rel, config = CASES["spider"]
    banned = ("ASTROFORGE_CLI", "PYTHONIO", "PYTHONUTF")
    env = {k: v for k, v in os.environ.items() if not k.startswith(banned)}
    script = (REPO_ROOT / script_rel).resolve()
    with tempfile.TemporaryDirectory() as td:
        config_path = Path(td) / "config.json"
        config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script), "--config", str(config_path),
             "--output", str(Path(td) / "result.json")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=180, env=env, cwd=str(script.parent),
        )
    assert "\x1b" not in proc.stdout, "未配置环境下非 TTY 仍出现 ANSI（双检测失效）"


# ============================================================
# 服务核心契约回归：process_runner 逐行捕获零改动的兼容面
# ============================================================

def test_服务核心逐行捕获语义兼容() -> None:
    """对真实 CLI stdout 复演 process_runner._pump_stdout + scheduler 判档（逐行/剥尾部空白）。"""
    script_rel, config = CASES["spider"]
    proc, result = _run_cli(script_rel, config)
    lines = [line.rstrip() for line in proc.stdout.splitlines() if line]
    assert lines, "stdout 为空"
    assert all("\r" not in line for line in lines), "逐行语义下 \\r 会污染行内容"
    error_lines = [line for line in lines if "[ERROR]" in line]
    assert error_lines, "scheduler 判档依赖行内 [ERROR]，缺失即 UI 错误档失效"


def test_模块cli_星符全部经语义名() -> None:
    """cli.py 内不得出现裸星符字形（一律 STAR_ICONS 语义名 → star_console 渲染）。

    例外：``·``/``•`` 为普通分隔符标点（icons.yaml 的 star_dim/star_mid 仅 TUI
    星野字形语义，CLI 不消费），不按星符泄漏计。
    """
    glyphs = set("✦☄◈❖✺◉☾✜✵✶✷✸●◌✕▲○✓⊘⬇▦▶◐◓◑◒▾▸")
    for cli in sorted((REPO_ROOT / "modules").glob("*/cli.py")):
        text = cli.read_text(encoding="utf-8")
        leaked = {g for g in glyphs if g in text}
        assert not leaked, f"{cli.name} 出现裸星符: {leaked}"
