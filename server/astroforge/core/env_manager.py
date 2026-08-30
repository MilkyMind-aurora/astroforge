"""环境自检引擎（方案 2.4 补丁 3 自检清单）。

启动与 /system/env-check 共用；异常项由双 UI 标红，不阻断服务启动。
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any

import httpx

from astroforge.core.config_loader import REPO_ROOT, Settings
from astroforge.utils.logger import get_logger

log = get_logger("astroforge.envcheck")

BUILTIN_TEMPLATES = ["academic", "tech_doc", "math_model", "simple_general", "formal_report"]


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


async def run_env_check(settings: Settings) -> dict[str, Any]:
    """逐项体检：环境/依赖/模型/浏览器/二进制/模板/存储。"""
    items: list[dict[str, Any]] = []

    items.append(_check(
        "Python 版本", True, f"{shutil.which('python') or 'python'} ({__import__('sys').version.split()[0]})"
    ))
    conda_path = shutil.which("conda")
    items.append(_check(
        "Conda", conda_path is not None, conda_path or "未找到 conda（模块隔离调用将回退当前解释器）"
    ))

    # PostgreSQL 连通性（引擎未初始化时提示配置缺失而非报错）
    try:
        from astroforge.db import engine as db_engine

        db_ok = await db_engine.ping()
        detail = "连通正常" if db_ok else "连接失败（检查服务与 ASTROFORGE_PG_PASSWORD）"
        items.append(_check("PostgreSQL", db_ok, detail))
    except Exception as exc:
        items.append(_check("PostgreSQL", False, f"未初始化/配置缺失: {exc}"))

    browser = settings.browser.chromium_path
    items.append(_check(
        "Chromium 浏览器", bool(browser) and Path(browser).exists(),
        browser or "未配置（platform_overrides.browser.chromium_path）",
    ))

    mineru_dir = settings.mineru.model_dir
    items.append(_check(
        "MinerU 模型目录", bool(mineru_dir) and Path(mineru_dir).exists(),
        mineru_dir or "未配置（mineru.model_dir）",
    ))

    model_path = settings.ai.model_path.get(settings.ai.default_model, "")
    items.append(_check(
        "AI 模型文件", bool(model_path) and Path(model_path).exists(),
        model_path or f"未配置默认模型 {settings.ai.default_model}",
    ))

    anydoc = REPO_ROOT / "modules" / "anydoc" / "bin" / (
        "anydoc.exe" if sys.platform.startswith("win") else "anydoc"
    )
    items.append(_check(
        "anydoc 二进制", anydoc.exists(),
        str(anydoc) if anydoc.exists() else f"缺失，请运行 scripts/install_anydoc（期望路径 {anydoc}）",
    ))

    template_dir = settings.template_dir()
    missing = [t for t in BUILTIN_TEMPLATES if not (template_dir / f"{t}.docx").exists()]
    items.append(_check(
        "DOCX 模板（5 套内置）", not missing,
        "完整" if not missing else f"缺失: {', '.join(missing)}",
    ))

    data_dir = settings.data_dir()
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    items.append(_check("数据目录可写", data_dir.exists(), str(data_dir)))

    # AI 引擎独立进程可达性（127.0.0.1:8421，基础设施探测，非用户 URL）
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(f"{settings.ai_engine.base_url}/v1/health")
        items.append(_check(
            "AI 引擎进程", resp.status_code == 200,
            f"{settings.ai_engine.base_url} → {resp.status_code}",
        ))
    except Exception:
        items.append(_check(
            "AI 引擎进程", False,
            f"{settings.ai_engine.base_url} 不可达（模块未启动属正常，按需拉起）",
        ))

    ok_count = sum(1 for item in items if item["ok"])
    return {"ok_count": ok_count, "total": len(items), "items": items}
