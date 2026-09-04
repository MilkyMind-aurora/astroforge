# -*- coding: utf-8 -*-
"""Phase 7.2 内存峰值基准（观测器）：对外部启动的进程做子进程树 RSS 峰值采样。

用法（两步，另开终端启动被测进程后再运行本脚本）：
  # 终端 A：启动被测模块（例如 MinerU）
  conda run -n env_mineru python modules/mineru/cli.py --config ... --output ...
  # 终端 B：把终端 A 的 PID 交给观测器
  python scripts/bench_memory.py --pid 12345 --label "MinerU 解析(4线程)"

红线：单任务峰值 ≤ 12GB（settings.system.max_memory_gb）。
安全约定：本脚本只读进程指标（psutil），不启动任何子进程。
"""
from __future__ import annotations

import argparse
import sys
import time

import psutil

LIMIT_GB = 12.0
POLL_SECONDS = 0.5


def tree_rss_gb(pid: int) -> float:
    """进程树 RSS 总和（GB），含所有子孙进程；进程中途消失按 0 计（观测竞态容错）。"""
    try:
        root = psutil.Process(pid)
        total = root.memory_info().rss
        for child in root.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                continue
        return total / 1024**3
    except psutil.Error:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge 内存峰值观测器")
    parser.add_argument("--pid", type=int, default=None, help="被测进程 PID（与 --find 二选一）")
    parser.add_argument("--find", default=None,
                        help="按 cmdline 子串自动发现进程（如 'mineru/cli.py'，规避 MSYS PID 差异）")
    parser.add_argument("--label", default="被测进程")
    parser.add_argument("--budget-gb", type=float, default=LIMIT_GB)
    args = parser.parse_args()

    if args.pid is None and args.find:
        # 自动发现：匹配 cmdline 子串的进程集合（Windows PID，规避 MSYS 差异）
        def _matched() -> list[int]:
            found = []
            for proc in psutil.process_iter(["pid", "cmdline"]):
                if args.find in " ".join(proc.info.get("cmdline") or []):
                    found.append(proc.info["pid"])
            return found

        pids = _matched()
        deadline = time.time() + 30
        while not pids and time.time() < deadline:
            time.sleep(1)
            pids = _matched()
        if not pids:
            print(f"[MISS] 30s 内未发现 cmdline 含 '{args.find}' 的进程")
            return 2
        print(f"[观测] 发现进程: {pids}")
        peak, start = 0.0, time.time()
        while pids:
            peak = max(peak, *(tree_rss_gb(p) for p in pids))
            time.sleep(POLL_SECONDS)
            pids = [p for p in pids if psutil.pid_exists(p)] or _matched()
        elapsed = time.time() - start
        verdict = "✅ 达标" if peak <= args.budget_gb else "❌ 超红线"
        print(f"[结果] {args.label}: 峰值 {peak:.2f}GB，"
              f"预算 {args.budget_gb}GB {verdict}，耗时 {elapsed:.0f}s")
        return 0 if peak <= args.budget_gb else 1

    if args.pid is None:
        print("[MISS] 需要 --pid 或 --find")
        return 2

    try:
        psutil.Process(args.pid)
    except psutil.Error:
        print(f"[MISS] 进程 {args.pid} 不存在")
        return 2

    print(f"[观测] {args.label} (pid={args.pid})，红线 {args.budget_gb}GB，每 {POLL_SECONDS}s 采样…")
    peak, start = 0.0, time.time()
    while psutil.pid_exists(args.pid):
        peak = max(peak, tree_rss_gb(args.pid))
        time.sleep(POLL_SECONDS)
    elapsed = time.time() - start
    verdict = "✅ 达标" if peak <= args.budget_gb else "❌ 超红线"
    print(f"[结果] {args.label}: 峰值 {peak:.2f}GB / 预算 {args.budget_gb}GB {verdict}，耗时 {elapsed:.0f}s")
    return 0 if peak <= args.budget_gb else 1


if __name__ == "__main__":
    sys.exit(main())
