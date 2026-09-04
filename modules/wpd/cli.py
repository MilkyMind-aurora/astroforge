# -*- coding: utf-8 -*-
"""理解层：WPD 图表数值提取 CLI（env_wpd，Phase 3，方案 3.3.2）。

config: {"task_type": "wpd", "input_dir": "<图表图片目录或单图 input_path>",
         "axis": {"x_min","x_max","y_min","y_max"} 可选,
         "output_dir": "...", "append_to_md": "<目标 md 可选>"}
输出：每图一个同名 .csv（data_x,data_y）；append_to_md 提供时把各 CSV 以
```csv 代码块追加到该 Markdown 末尾（方案 3.3.2 步骤 4）。
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from cli_utils import error, fail, info, load_json, ok, save_json  # noqa: E402

try:
    import chart_extractor  # 同目录核心算法（依赖 cv2/numpy）
except ImportError as exc:  # 依赖缺失降级
    chart_extractor = None
    _IMPORT_ERROR = exc

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def _collect_images(cfg: dict) -> list[Path]:
    single = cfg.get("input_path")
    if single:
        p = Path(single)
        return [p] if p.is_file() else []
    input_dir = Path(cfg.get("input_dir", ""))
    if not input_dir.exists():
        return []
    return sorted(p for p in input_dir.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)


def _write_csv(path: Path, points: list[tuple[float, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(("data_x", "data_y"))
        writer.writerows(points)


def _append_to_markdown(target: Path, csv_pairs: list[tuple[str, Path]]) -> None:
    """把各 CSV 以代码块形式追加到 Markdown 末尾（方案 3.3.2）。"""
    parts = ["\n\n## 图表提取数据\n"]
    for name, csv_path in csv_pairs:
        content = csv_path.read_text(encoding="utf-8").strip()
        parts.append(f"\n**{csv_path.stem}**（来源图表：{name}）\n\n```csv\n{content}\n```\n")
    with target.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(parts))


def run_wpd(cfg: dict) -> dict:
    if chart_extractor is None:
        return fail(3001, f"opencv/numpy 未安装（env_wpd）: {_IMPORT_ERROR}")
    images = _collect_images(cfg)
    if not images:
        return fail(4001, "未找到图表图片（检查 input_dir/input_path）")
    output_dir = Path(cfg.get("output_dir", (images[0].parent) / "wpd_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    axis = cfg.get("axis")

    csv_pairs, skipped = [], []
    for image_path in images:
        try:
            result = chart_extractor.extract_curve(str(image_path), axis)
        except FileNotFoundError as exc:
            return fail(4001, str(exc))
        except ValueError as exc:
            # 无轴/无彩色系列/点过少：跳过并记录（流程图等非量化图属正常跳过）
            skipped.append({"image": str(image_path), "reason": str(exc)})
            info(f"跳过 {image_path.name}: {exc}")
            continue
        csv_path = output_dir / f"{image_path.stem}.csv"
        _write_csv(csv_path, result["points"])
        csv_pairs.append((image_path.name, csv_path))
        info(f"提取完成: {image_path.name} → {csv_path.name}"
             f"（{len(result['points'])} 点）")

    if not csv_pairs:
        return fail(3003, "所有图表均无法提取（详见 skipped）",
                    {"skipped": skipped})
    if cfg.get("append_to_md"):
        md_target = Path(cfg["append_to_md"])
        if md_target.exists():
            _append_to_markdown(md_target, csv_pairs)
            info(f"已追加到 Markdown: {md_target}")
        else:
            error(f"append_to_md 目标不存在: {md_target}")
    data = {"csv_files": [str(p) for _, p in csv_pairs],
            "skipped": skipped, "output_dir": str(output_dir)}
    if axis is None:
        data["note"] = "未提供 axis 坐标范围，输出为 0-1 归一化坐标"
    return ok(data, "wpd 完成")


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge WPD 图表提数模块")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = load_json(args.config)
    try:
        result = run_wpd(cfg)
    except Exception as exc:
        error(f"执行异常: {exc}")
        result = fail(3003, f"模块执行异常: {exc}")
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
