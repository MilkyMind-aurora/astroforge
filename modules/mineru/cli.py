"""理解层：MinerU 文档解析 CLI（env_mineru）。

约定：python cli.py --config <config.json> --output <result.json>
config: {"task_type": "mineru", "input_path": "<PDF/图片/目录>", "output_dir": "..."}
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from cli_utils import error, fail, info, load_json, ok, save_json

TIMEOUT_SECONDS = 3600


def run_mineru(cfg: dict) -> dict:
    input_path = Path(cfg.get("input_path", ""))
    if not input_path:
        return fail(1001, "缺少 input_path 参数")
    if not input_path.exists():
        return fail(4001, f"输入不存在: {input_path}")
    if shutil.which("mineru") is None:
        return fail(3001, "mineru 未安装（请创建 env_mineru 并安装 mineru[core]）")

    output_dir = Path(cfg.get("output_dir", Path(input_path).parent / "mineru_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    # 方案 3.3.1：ModelScope 本地模型源；MODELSCOPE_CACHE 指向自备目录
    env.setdefault("MINERU_MODEL_SOURCE", "modelscope")

    info(f"MinerU 解析开始: {input_path}")
    completed = subprocess.run(
        ["mineru", "-p", str(input_path), "-o", str(output_dir), "-b", "pipeline"],
        env=env, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
    )
    if completed.returncode != 0:
        error(f"mineru 失败: {completed.stderr[-500:]}")
        return fail(3003, f"mineru 退出码 {completed.returncode}", {"stderr": completed.stderr[-1000:]})

    md_files = [str(p) for p in sorted(output_dir.rglob("*.md"))]
    info(f"解析完成，产出 {len(md_files)} 个 Markdown")
    return ok({"md_files": md_files, "output_dir": str(output_dir)}, "mineru 完成")


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge MinerU 解析模块")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = load_json(args.config)
    try:
        result = run_mineru(cfg)
    except subprocess.TimeoutExpired:
        result = fail(3002, f"mineru 超时（>{TIMEOUT_SECONDS}s）")
    except Exception as exc:
        error(f"执行异常: {exc}")
        result = fail(3003, f"模块执行异常: {exc}")
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
