"""理解层：WPD 图表数值提取 CLI（env_wpd）——骨架，核心算法属 Phase 3。

config: {"task_type": "wpd", "input_dir": "<图表图片目录>", "meta": "<MinerU 元数据路径可选>"}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from cli_utils import fail, load_json, save_json


def run_wpd(cfg: dict) -> dict:
    input_dir = cfg.get("input_dir")
    if not input_dir:
        return fail(1001, "缺少 input_dir 参数")
    return fail(3006, "WPD 图表数值提取属 Phase 3 开发中（坐标轴识别 + 数据点提取）",
                {"input_dir": input_dir})


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge WPD 图表提数模块")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = load_json(args.config)
    result = run_wpd(cfg)
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
