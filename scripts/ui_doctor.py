# -*- coding: utf-8 -*-
"""前端聚合验收（方案 §七「全局验收工具链」/ V1-B.5）：一次跑完设计契约门禁。

检查项（默认集）：
  pytest          python -m pytest server/tests -q（与 CI Python 门同范围；
                  根 tests/ 属模块功能测试，依赖 cv2/numpy 等模块环境，另行跑）
  ruff            python -m ruff check server scripts（与 CI 同范围）
  gen-idempotent  gen_design 连跑两次：产物字节不变 + git 工作树无新增变化
  placeholder     tui/ 内 "PlaceholderPage" 出现次数 = 0（占位页清零，§3.7 ②）
  bare-color      tui/ 非生成目录裸 hex（#RRGGBB）= 0（裸色只许在生成物，§3.7 ①）
  bare-print      modules/*/cli.py 裸 print( = 0（stdout 契约走 star_console/cli_utils，§4.2 ①）
  app-bare-color  app/lib 除 tokens.g.dart 外 "Color(0x" = 0（§5.8 ②）

--full 追加（需 Flutter 工具链）：
  flutter-analyze flutter analyze（cwd=app）
  flutter-test    flutter test（cwd=app）

用法：
  python scripts/ui_doctor.py                          # 默认检查集
  python scripts/ui_doctor.py --quick                  # 契约快检（编排门禁用，见下）
  python scripts/ui_doctor.py --full                   # 追加 flutter analyze+test
  python scripts/ui_doctor.py --skip=placeholder,bare-color
  python scripts/ui_doctor.py --list                   # 列出检查项

--quick（契约快检，供编排/本地快速门禁）：跳过重量级检查（pytest、
flutter-analyze、flutter-test）与随里程碑推进的清账项（placeholder、
bare-color——TUI 壳层 token 化重写前的已知债，豁免口径与 CI 设计契约
门禁一致），只跑 ruff / gen-idempotent / bare-print / app-bare-color。
默认集与 --full 仍全量执行（含上述清账项），MF1 TUI 重写后清账项归零。

退出码即结论：0=全绿 1=存在 FAIL 2=参数错误。SKIP 不影响退出码（--skip/--quick 显式免责）。
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]

GEN_DIR = REPO_ROOT / "tui" / "tui" / "theme" / "generated"  # 裸色豁免目录（tokens 生成物）
HEX_RE = re.compile(r"#[0-9A-Fa-f]{6}\b")
MAX_HITS_SHOWN = 8

# 检查项注册表：名称 → (说明, 执行函数)。函数返回 (ok|None, note)；
# None = 无法执行（如 git 不可用），按 SKIP 计。
CheckFn = Callable[[], tuple[bool | None, str]]
CHECKS: list[tuple[str, str, CheckFn]] = []


def register(name: str, desc: str) -> Callable[[CheckFn], CheckFn]:
    def deco(fn: CheckFn) -> CheckFn:
        CHECKS.append((name, desc, fn))
        return fn

    return deco


def _run(cmd: list[str], cwd: Path | None = None, timeout_s: int = 900) -> subprocess.CompletedProcess:
    """跑子进程（utf-8 捕获；一律列表式调用，不经 shell）。"""
    return subprocess.run(
        cmd, cwd=cwd or REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout_s,
    )


def _tail(text: str, lines: int = 3) -> str:
    return " | ".join(text.strip().splitlines()[-lines:])[-400:] if text.strip() else ""


def _scan_files(root: Path, patterns: tuple[str, ...], exclude_dirs: tuple[Path, ...]) -> list[Path]:
    """按模式收集文件，剔除豁免目录（如 tokens 生成物目录）。"""
    out: list[Path] = []
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path.is_file() and not any(d in path.parents for d in exclude_dirs):
                out.append(path)
    return out


# ============================================================
# 检查项实现
# ============================================================

@register("pytest", "python -m pytest server/tests -q（CI 同范围）")
def check_pytest() -> tuple[bool | None, str]:
    proc = _run([sys.executable, "-m", "pytest", "server/tests", "-q"])
    note = _tail(proc.stdout or proc.stderr)
    return proc.returncode == 0, note


@register("ruff", "python -m ruff check server scripts（CI 同范围）")
def check_ruff() -> tuple[bool | None, str]:
    proc = _run([sys.executable, "-m", "ruff", "check", "server", "scripts"])
    note = _tail(proc.stdout or proc.stderr, 1)
    return proc.returncode == 0, note


def _artifact_digests() -> dict[str, str]:
    import gen_design  # 延迟导入：scripts 目录在 main() 里已加入 sys.path

    digests: dict[str, str] = {}
    for rel in (*gen_design.ARTIFACTS, *gen_design.TUI_PACKAGE_INITS):
        path = REPO_ROOT / rel
        digests[rel] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "<缺>"
    return digests


def _git_status() -> str | None:
    if shutil.which("git") is None:
        return None
    proc = _run(["git", "status", "--porcelain"])
    return proc.stdout if proc.returncode == 0 else None


@register("gen-idempotent", "gen_design 连跑两次：产物字节不变且 git 工作树无新增变化")
def check_gen_idempotent() -> tuple[bool | None, str]:
    import gen_design

    git_before = _git_status()
    digests_before = _artifact_digests()
    for i in (1, 2):
        proc = _run([sys.executable, str(REPO_ROOT / "scripts" / "gen_design.py")])
        if proc.returncode != 0:
            return False, f"第 {i} 次生成失败: {_tail(proc.stdout + proc.stderr, 2)}"
    digests_after = _artifact_digests()
    if digests_before != digests_after:
        changed = [k for k in digests_after if digests_before.get(k) != digests_after[k]]
        return False, f"两次生成产物不一致: {changed}"
    if git_before is not None:
        git_after = _git_status()
        if git_before != git_after:
            only_after = set(git_after.splitlines()) - set(git_before.splitlines())
            return False, f"生成后 git 工作树出现新变化: {sorted(only_after)[:MAX_HITS_SHOWN]}"
    n = len(gen_design.ARTIFACTS)
    via_git = "git 快照比对" if git_before is not None else "git 不可用，仅字节比对"
    return True, f"{n} 项产物两次生成字节一致（{via_git}）"


@register("placeholder", "tui/ 内 PlaceholderPage = 0（占位页清零，§3.7 ②）")
def check_placeholder() -> tuple[bool | None, str]:
    hits: list[str] = []
    for path in _scan_files(REPO_ROOT / "tui", ("*.py",), ()):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "PlaceholderPage" in line:
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    if hits:
        return False, f"{len(hits)} 处命中: {hits[:MAX_HITS_SHOWN]}"
    return True, "0 命中"


@register("bare-color", "tui/ 非生成目录裸 hex = 0（裸色只许在 tokens 生成物，§3.7 ①）")
def check_bare_color() -> tuple[bool | None, str]:
    hits: list[str] = []
    for path in _scan_files(REPO_ROOT / "tui", ("*.py", "*.tcss"), (GEN_DIR,)):
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if HEX_RE.search(line):
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    if hits:
        return False, f"{len(hits)} 处命中: {hits[:MAX_HITS_SHOWN]}"
    return True, "0 命中"


@register("bare-print", "modules/*/cli.py 裸 print( = 0（stdout 契约，§4.2 ①）")
def check_bare_print() -> tuple[bool | None, str]:
    hits: list[str] = []
    for cli in sorted((REPO_ROOT / "modules").glob("*/cli.py")):
        text = cli.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "print(" in line:
                hits.append(f"{cli.relative_to(REPO_ROOT)}:{lineno}")
    if hits:
        return False, f"{len(hits)} 处命中: {hits[:MAX_HITS_SHOWN]}"
    return True, "0 命中"


@register("app-bare-color", "app/lib 除 tokens.g.dart 外 Color(0x = 0（§5.8 ②）")
def check_app_bare_color() -> tuple[bool | None, str]:
    hits: list[str] = []
    for path in _scan_files(REPO_ROOT / "app" / "lib", ("*.dart",), ()):
        if path.name == "tokens.g.dart":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "Color(0x" in line:
                hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    if hits:
        return False, f"{len(hits)} 处命中: {hits[:MAX_HITS_SHOWN]}"
    return True, "0 命中"


def _flutter_cmd(args: list[str]) -> list[str] | None:
    """解析 flutter 可执行为列表式命令（Windows 下 shutil.which 直接给出 flutter.BAT
    全路径，CreateProcess 可执行批处理；参数是内部常量，不经任何用户输入）。"""
    exe = shutil.which("flutter")
    if exe is None:
        exe = shutil.which("flutter.bat")
    if exe is None:
        return None
    return [exe, *args]


@register("flutter-analyze", "--full：flutter analyze（cwd=app）")
def check_flutter_analyze() -> tuple[bool | None, str]:
    cmd = _flutter_cmd(["analyze", "--no-fatal-infos"])
    if cmd is None:
        return False, "flutter 不在 PATH"
    proc = _run(cmd, cwd=REPO_ROOT / "app", timeout_s=600)
    note = _tail(proc.stdout or proc.stderr, 2)
    return proc.returncode == 0, note


@register("flutter-test", "--full：flutter test（cwd=app）")
def check_flutter_test() -> tuple[bool | None, str]:
    cmd = _flutter_cmd(["test"])
    if cmd is None:
        return False, "flutter 不在 PATH"
    proc = _run(cmd, cwd=REPO_ROOT / "app", timeout_s=900)
    note = _tail(proc.stdout or proc.stderr, 2)
    return proc.returncode == 0, note


FULL_ONLY = {"flutter-analyze", "flutter-test"}
# --quick 豁免集 = 重量级（分钟级）+ 随里程碑推进的清账项（豁免口径同 CI 设计契约门禁）
QUICK_SKIP = {
    "pytest": "--quick 跳过重量级",
    "flutter-analyze": "--quick 跳过重量级",
    "flutter-test": "--quick 跳过重量级",
    "placeholder": "--quick 豁免清账项（MF1 TUI 重写后归零）",
    "bare-color": "--quick 豁免清账项（MF1 TUI 重写后归零）",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AstroForge 前端聚合验收（设计契约 grep 断言 + 生成幂等 + lint/测试）"
    )
    parser.add_argument("--full", action="store_true", help="追加 flutter analyze + flutter test")
    parser.add_argument(
        "--quick", action="store_true",
        help="契约快检：跳过重量级（pytest/flutter）与 MF1 清账项（placeholder/bare-color）",
    )
    parser.add_argument(
        "--skip", default="", help="逗号分隔的检查项名（跳过项显式免责，不计入退出码）"
    )
    parser.add_argument("--list", action="store_true", help="列出全部检查项后退出")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        for name, desc, _fn in CHECKS:
            flag = "（--full）" if name in FULL_ONLY else ("（--quick 跳过）" if name in QUICK_SKIP else "")
            print(f"  {name:<16} {desc}{flag}")
        return 0

    if args.quick and args.full:
        print("[ui_doctor] 参数冲突：--quick（契约快检）与 --full（全量含 flutter）互斥")
        return 2

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    known = {name for name, _d, _f in CHECKS}
    unknown = sorted(skip - known)
    if unknown:
        print(f"[ui_doctor] 未知检查项: {unknown}（可选: {', '.join(sorted(known))}）")
        return 2

    # scripts/ 目录入 import 路径（gen-idempotent 需要复用 gen_design 的产物清单）
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

    quick_skip = QUICK_SKIP if args.quick else {}
    selected = [
        (name, desc, fn) for name, desc, fn in CHECKS if name not in FULL_ONLY or args.full
    ]
    mode = "契约快检" if args.quick else ("全量（含 flutter）" if args.full else "默认集")
    print(f"ui_doctor · 前端聚合验收（{mode}，{len(selected)} 项；repo={REPO_ROOT}）")
    print("-" * 72)

    results: list[tuple[str, str, str]] = []  # (name, mark, note)
    for name, desc, fn in selected:
        if name in skip:
            results.append((name, "SKIP", "--skip 显式跳过"))
            print(f"[SKIP] {name:<16} --skip 显式跳过")
            continue
        if name in quick_skip:
            results.append((name, "SKIP", quick_skip[name]))
            print(f"[SKIP] {name:<16} {quick_skip[name]}")
            continue
        try:
            ok, note = fn()
        except Exception as exc:  # 单项异常不拖垮整场验收，按 FAIL 记录
            ok, note = False, f"检查器异常: {exc}"
        mark = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
        results.append((name, mark, note))
        print(f"[{mark}] {name:<16} {note}")

    print("-" * 72)
    n_pass = sum(1 for _n, m, _t in results if m == "PASS")
    n_fail = sum(1 for _n, m, _t in results if m == "FAIL")
    n_skip = sum(1 for _n, m, _t in results if m == "SKIP")
    verdict = "全绿" if n_fail == 0 else "存在 FAIL"
    print(f"结论: {verdict}（PASS {n_pass} / FAIL {n_fail} / SKIP {n_skip}）")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
