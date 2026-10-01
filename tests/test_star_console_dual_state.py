# -*- coding: utf-8 -*-
"""star_console 双态输出快照比对（CI 门禁）：非 TTY 管道捕获 vs 强制着色捕获。

在真实子进程边界上锁死降级纪律（方案 §2.5【硬性】）的两个面：
  1. 非 TTY 管道态（CI/服务核心的真实形态）：``__main__`` 横幅入口与 log API
     输出纯文本，不含任何 ANSI 转义，``[INFO] `` 日志行逐字节守约；
  2. 强制着色态（样本/调试）：ASTROFORGE_CLI_FORCE_COLOR=1（import 态置
     force_color → rich force_terminal）+ configure(force_plain=False)（文档化
     测试入口，解除降级判定）输出必含 ANSI；剥掉 ANSI 后与纯文本态逐字节一致
     （着色不改变内容）。
态 A 走真实管道（服务核心同款）；态 B 在子进程内用 StringIO 承接后原样回传
管道——Windows 管道被 rich 判为 legacy console（color_system=windows，着色走
Win32 API，管道里本就不出 ANSI），StringIO 捕获是 cli-samples 样本生成的同款
口径，三平台行为一致。两态均跨平台可复现（显式 utf-8 编码）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHARED = REPO_ROOT / "modules" / "_shared"

# CSI 转义（SGR 着色/光标控制均属之）；纯文本态断言用更宽的 \x1b 全禁
ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

BANNER_ARGS = ("ci-drill", "dual-state snapshot")  # banner(module, detail)，参数保持 ASCII 跨平台安全
LOG_MSG = "dual-state probe"
LOG_PLAIN = f"[INFO] {LOG_MSG}\n"  # stdout 日志行字节契约
SHARED_SRC = str(SHARED).replace("'", "'\\''")  # -c 片段里的路径安全引位

PLAIN_PRELUDE = (
    "import sys; "
    f"sys.path.insert(0, r'{SHARED_SRC}'); "
    "import star_console; "
)


def _run(cmd: list[str], *, force_color: bool) -> str:
    """子进程捕获：stdout 一律接管道（非 TTY）；utf-8 编码消除平台差异。"""
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "ASTROFORGE_CLI_THEME": "dark",
    }
    if force_color:
        env["ASTROFORGE_CLI_FORCE_COLOR"] = "1"
    else:
        env.pop("ASTROFORGE_CLI_FORCE_COLOR", None)
    proc = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120, env=env, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"子进程失败 rc={proc.returncode}\nstderr: {proc.stderr[-500:]}"
    return proc.stdout


def _plain_banner_via_main() -> str:
    """真实 ``__main__`` 入口（shell 脚本横幅同款）：管道态 → 纯文本降级。"""
    script = SHARED / "star_console.py"
    return _run([sys.executable, str(script), "banner", *BANNER_ARGS], force_color=False)


def _plain_log_via_api() -> str:
    """-c 直调 log API（不做任何 configure）：管道态默认双检测 → 纯文本。"""
    return _run([sys.executable, "-c", PLAIN_PRELUDE + f"star_console.log('INFO', '{LOG_MSG}')"],
                force_color=False)


def _forced_capture(call: tuple[str, tuple[str, ...]]) -> str:
    """强制着色态：FORCE_COLOR=1 + configure(force_plain=False)，子进程内 StringIO
    承接输出后原样回传（理由见模块 docstring：Windows 管道 legacy console 不出 ANSI）。"""
    src = "\n".join([
        "import io, contextlib, sys",
        f"sys.path.insert(0, r'{SHARED_SRC}')",
        "import star_console as sc",
        "sc.configure(force_plain=False)",
        f"fn, args = {call!r}",
        "buf = io.StringIO()",
        "with contextlib.redirect_stdout(buf):",
        "    getattr(sc, fn)(*args)",
        "sys.stdout.write(buf.getvalue())",
    ])
    return _run([sys.executable, "-c", src], force_color=True)


# ============================================================
# 态 A：非 TTY 管道（CI 与服务核心的真实形态）
# ============================================================

def test_非TTY管道态_纯文本快照特征() -> None:
    out = _plain_banner_via_main()
    assert "\x1b" not in out, "非 TTY 管道态禁止任何 ANSI 转义"
    assert "AstroForge · 衍星台 — ci-drill" in out, "横幅题名必须保留"
    assert "✦" in out, "星符（nav.home）必须保留"
    log_out = _plain_log_via_api()
    assert "\x1b" not in log_out, "日志行纯文本态禁止 ANSI"
    assert log_out == LOG_PLAIN, "stdout 日志行必须逐字节守约"


# ============================================================
# 态 B：FORCE_COLOR 强制着色
# ============================================================

def test_强制着色态_ANSI快照特征() -> None:
    out = _forced_capture(("banner", BANNER_ARGS))
    assert ANSI_CSI_RE.search(out), "强制着色态必须输出 ANSI 转义"
    log_out = _forced_capture(("log", ("INFO", LOG_MSG)))
    assert ANSI_CSI_RE.search(log_out), "log 富文本态前缀必须着色"


def test_双态快照比对_剥ANSI后逐字节一致() -> None:
    plain = _plain_banner_via_main()
    colored = _forced_capture(("banner", BANNER_ARGS))
    assert colored != plain, "强制着色态与纯文本态原始字节必须不同（确系两态）"
    stripped = ANSI_CSI_RE.sub("", colored)
    assert stripped == plain, "剥掉 ANSI 后两态内容必须逐字节一致（着色不改变内容）"
    assert "AstroForge · 衍星台 — ci-drill" in stripped
    log_plain = _plain_log_via_api()
    log_colored = ANSI_CSI_RE.sub("", _forced_capture(("log", ("INFO", LOG_MSG))))
    assert log_colored == log_plain == LOG_PLAIN, "日志行两态剥 ANSI 后均须逐字节守约"
