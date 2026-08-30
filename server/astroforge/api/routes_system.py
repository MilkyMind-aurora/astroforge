"""系统路由：健康检查（开放）、环境自检、服务管理。"""
from __future__ import annotations

import time

from fastapi import APIRouter

from astroforge.api import deps
from astroforge.api.response import ok
from astroforge.core.env_manager import run_env_check

router = APIRouter(tags=["system"])


@router.get("/system/health")
async def health(ctx: deps.CtxDep) -> dict:
    """探活端点（免认证）：双 UI 连接引导使用。"""
    db_ok = False
    ai_ok = False
    try:
        from astroforge.db import engine as db_engine

        db_ok = await db_engine.ping()
    except Exception:
        pass
    try:
        await ctx.ai_client.health()
        ai_ok = True
    except Exception:
        pass
    return ok({
        "service": "sidereal-core",
        "project": "AstroForge",
        "version": "0.1.0",
        "uptime_s": round(time.monotonic() - ctx.started_at_mono, 1),
        "db": db_ok,
        "ai_engine": ai_ok,
        "shutdown_requested": ctx.shutdown_requested,
    })


@router.get("/system/env-check", dependencies=[deps.TokenDep])
async def env_check(ctx: deps.CtxDep) -> dict:
    return ok(await run_env_check(ctx.settings))


@router.post("/service/shutdown", dependencies=[deps.TokenDep])
async def shutdown(ctx: deps.CtxDep) -> dict:
    """优雅停机：置位后由 __main__ 的看护循环让 uvicorn 退出。"""
    ctx.shutdown_requested = True
    return ok({"detail": "停机已请求，等待当前任务收尾"})


@router.post("/service/reload-config", dependencies=[deps.TokenDep])
async def reload_config() -> dict:
    from astroforge.core.config_loader import reload_settings

    settings = reload_settings()
    return ok({"config_path": settings.config_path, "detail": "配置已热更新（引擎级组件需重启生效）"})


@router.post("/service/token/reset", dependencies=[deps.TokenDep])
async def reset_token(ctx: deps.CtxDep) -> dict:
    """重置本机 token：旧 token 立即失效，客户端需重新读取。"""
    import secrets

    token_path = ctx.settings.token_file()
    ctx.token = secrets.token_hex(32)
    token_path.write_text(ctx.token, encoding="utf-8")
    return ok({"token_file": str(token_path)})
