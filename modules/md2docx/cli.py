"""转换层（出）：MD → DOCX CLI（env_md2docx，方案 3.4.2）。

config: {"task_type": "md2docx", "input_path": "...", "output_dir": "...",
         "template": "academic|tech_doc|math_model|simple_general|formal_report", "merge": bool}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from cli_utils import error, fail, info, load_json, ok, save_json

try:
    import converter  # 同目录
except ImportError as exc:  # python-docx 缺失
    converter = None
    _IMPORT_ERROR = exc


def _collect_md_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(p for p in input_path.rglob("*.md"))


def run_md2docx(cfg: dict) -> dict:
    if converter is None:
        return fail(3001, f"python-docx 未安装（env_md2docx）: {_IMPORT_ERROR}")
    input_path = Path(cfg.get("input_path", ""))
    if not input_path.exists():
        return fail(4001, f"输入不存在: {input_path}")
    md_files = _collect_md_files(input_path)
    if not md_files:
        return fail(4001, "未找到 Markdown 文件")

    output_dir = Path(cfg.get("output_dir", input_path.parent / "docx_out"))
    output_dir.mkdir(parents=True, exist_ok=True)
    template = cfg.get("template") or "tech_doc"

    if cfg.get("merge") and len(md_files) > 1:
        target = output_dir / f"{input_path.stem or 'merged'}.docx"
        converter.convert_merged(md_files, target, template)
        info(f"合并转换完成: {target}")
        return ok({"files": [str(target)], "template": template}, "md2docx 完成")

    generated = []
    for md in md_files:
        target = output_dir / f"{md.stem}.docx"
        converter.convert_file(md, target, template)
        generated.append(str(target))
        info(f"转换完成: {md.name} → {target.name}")
    return ok({"files": generated, "template": template}, "md2docx 完成")


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge MD 转 DOCX 模块")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    cfg = load_json(args.config)
    try:
        result = run_md2docx(cfg)
    except Exception as exc:
        error(f"执行异常: {exc}")
        result = fail(3003, f"模块执行异常: {exc}")
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
