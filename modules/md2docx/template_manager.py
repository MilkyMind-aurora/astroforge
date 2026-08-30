"""模板管理：5 套内置模板加载（方案 3.4.2 模板机制）。

模板文件位于 templates/<key>.docx；存在则继承其样式，否则退回空白文档。
"""
from __future__ import annotations

from pathlib import Path

from docx import Document

BUILTIN_TEMPLATES = {
    "academic": "学术论文模板",
    "tech_doc": "技术文档模板",
    "math_model": "数模竞赛模板",
    "simple_general": "简约通用模板",
    "formal_report": "正式报告模板",
}

# templates/ 目录相对仓库根（模块独立运行，锚定本文件向上三级）
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"


def load_template(template_key: str) -> Document:
    if template_key not in BUILTIN_TEMPLATES:
        template_key = "tech_doc"
    template_path = TEMPLATE_DIR / f"{template_key}.docx"
    if template_path.exists():
        return Document(str(template_path))
    # 模板缺失时退回空白文档（不阻断转换，env-check 会标红提醒）
    return Document()
