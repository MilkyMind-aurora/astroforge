"""转换层（入）：anydoc 办公文档转 MD CLI——Rust 二进制包装（方案 3.4.1）。

二进制预检（补丁 3）：缺失时返回 4004 + 修复指引，绝不裸崩 FileNotFoundError。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from cli_utils import error, fail, info, load_json, ok, save_json

SUPPORTED_SUFFIXES = {".doc", ".docx", ".docm", ".ppt", ".pptx", ".xls", ".xlsx", ".xlsm",
                      ".odt", ".ods", ".odp", ".rtf", ".epub", ".csv"}


def locate_binary(cfg: dict) -> Path | None:
    """定位 anydoc 二进制：config 指定 > bin/anydoc(.exe)。"""
    explicit = cfg.get("binary_path")
    if explicit and Path(explicit).exists():
        return Path(explicit)
    bin_dir = Path(__file__).resolve().parent / "bin"
    for name in ("anydoc.exe", "anydoc"):
        candidate = bin_dir / name
        if candidate.exists():
            return candidate
    return None


def run_anydoc(cfg: dict) -> dict:
    binary = locate_binary(cfg)
    if binary is None:
        return fail(4004, "anydoc 二进制缺失，请运行 scripts/install_anydoc.bat|.sh 修复",
                    {"searched": str(Path(__file__).resolve().parent / "bin")})
    input_path = Path(cfg.get("input_path", ""))
    if not input_path.exists():
        return fail(4001, f"输入不存在: {input_path}")
    if input_path.is_file() and input_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return fail(1002, f"不支持的格式: {input_path.suffix}")

    output_dir = Path(cfg.get("output_dir", input_path.parent / "md_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    targets = ([input_path] if input_path.is_file()
               else [p for p in sorted(input_path.rglob("*")) if p.suffix.lower() in SUPPORTED_SUFFIXES])
    if not targets:
        return fail(4001, "未找到可转换的办公文档")

    converted, failed = [], []
    for target in targets:
        completed = subprocess.run(
            [str(binary), str(target), "--output", str(output_dir)],
            capture_output=True, text=True, timeout=300,
        )
        if completed.returncode == 0:
            converted.append(str(target))
            info(f"转换成功: {target.name}")
        else:
            failed.append({"file": str(target), "stderr": completed.stderr[-300:]})
            error(f"转换失败: {target.name}")
    data = {"converted": converted, "failed": failed, "output_dir": str(output_dir)}
    return ok(data) if converted else fail(3003, "全部转换失败", data)


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge anydoc 转换模块")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = load_json(args.config)
    try:
        result = run_anydoc(cfg)
    except Exception as exc:
        error(f"执行异常: {exc}")
        result = fail(3003, f"模块执行异常: {exc}")
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
