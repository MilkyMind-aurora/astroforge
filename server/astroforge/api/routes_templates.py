"""DOCX 模板路由：元数据列表与预览（方案 3.4.2 模板机制）。"""
from __future__ import annotations

from fastapi import APIRouter

from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok
from astroforge.core.env_manager import BUILTIN_TEMPLATES

router = APIRouter(prefix="/templates", tags=["templates"])

BUILTIN_META = {
    "academic": {"name": "学术论文模板", "scene": "课程论文、小论文、竞赛报告"},
    "tech_doc": {"name": "技术文档模板", "scene": "技术方案、接口文档、知识库导出"},
    "math_model": {"name": "数模竞赛模板", "scene": "数学建模竞赛论文（国赛格式规范）"},
    "simple_general": {"name": "简约通用模板", "scene": "日常办公、通用文档"},
    "formal_report": {"name": "正式报告模板", "scene": "工作汇报、正式报告"},
}


@router.get("", dependencies=[deps.TokenDep])
async def list_templates(ctx: deps.CtxDep) -> dict:
    template_dir = ctx.settings.template_dir()
    items = []
    for key in BUILTIN_TEMPLATES:
        file_path = template_dir / f"{key}.docx"
        meta = BUILTIN_META.get(key, {"name": key, "scene": ""})
        items.append({
            "template_key": key, "name": meta["name"], "scene": meta["scene"],
            "is_builtin": True, "exists": file_path.exists(), "file_path": str(file_path),
        })
    return ok({"items": items, "default": ctx.settings.md2docx.default_template})


@router.get("/{template_key}/preview", dependencies=[deps.TokenDep])
async def preview_template(template_key: str, ctx: deps.CtxDep) -> dict:
    if template_key not in BUILTIN_TEMPLATES:
        raise ApiError(ErrorCode.INVALID_TEMPLATE, f"未知模板: {template_key}")
    meta = BUILTIN_META[template_key]
    file_path = ctx.settings.template_dir() / f"{template_key}.docx"
    return ok({
        "template_key": template_key, "name": meta["name"], "scene": meta["scene"],
        "exists": file_path.exists(), "file_path": str(file_path),
        "config": {
            "enable_toc": ctx.settings.md2docx.enable_toc,
            "enable_page_number": ctx.settings.md2docx.enable_page_number,
        },
    })
