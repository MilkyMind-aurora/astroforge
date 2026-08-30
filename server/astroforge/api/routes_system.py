"""系统路由：健康检查（开放）、环境自检、服务管理。"""
from __future__ import annotations

import time

from fastapi import APIRouter

from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok
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


# ---- 设置中心（方案 1.3.3）----

# 可写键白名单：更新键不得来自客户端字符串直通（方案 8.4）
WRITABLE_KEYS: dict[str, tuple] = {
    "default_template": (str,),
    "mascot_enabled": (bool,),
    "memory_warning_gb": (int, float),
    "memory_critical_gb": (int, float),
    "request_interval": (int, float),
}


@router.get("/system/config-summary", dependencies=[deps.TokenDep])
async def config_summary(ctx: deps.CtxDep) -> dict:
    """当前生效配置摘要（脱敏：不含任何密码/凭据字段）。"""
    s = ctx.settings
    return ok({
        "service": {"host": s.service.host, "port": s.service.port},
        "database": {"host": s.database.host, "port": s.database.port,
                     "db_name": s.database.db_name, "db_user": s.database.db_user},
        "md2docx": {"default_template": s.md2docx.default_template},
        "monitor": {"memory_warning_gb": s.monitor.memory_warning_gb,
                    "memory_critical_gb": s.monitor.memory_critical_gb,
                    "refresh_interval": s.monitor.refresh_interval,
                    "history_hours": s.monitor.history_hours},
        "ai": {"enabled": s.ai.enabled, "default_model": s.ai.default_model,
               "idle_timeout": s.ai.idle_timeout},
        "system": {"max_memory_gb": s.system.max_memory_gb,
                   "task_concurrency": s.system.task_concurrency,
                   "mascot_enabled": s.system.mascot_enabled},
    })


@router.get("/app-settings", dependencies=[deps.TokenDep])
async def list_app_settings() -> dict:
    """读用户覆盖设置（app_settings 表；DB 不可用返回空集）。"""
    try:
        from astroforge.db import engine as db_engine
        from astroforge.db.repositories import app_settings as settings_repo

        async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
            items = await settings_repo.list_all(session, WRITABLE_KEYS)
        return ok({"items": items})
    except Exception:
        return ok({"items": {}, "note": "数据库不可用，覆盖设置未生效"})


@router.put("/app-settings/{key}", dependencies=[deps.TokenDep])
async def set_app_setting(key: str, ctx: deps.CtxDep, value: dict) -> dict:
    """写覆盖设置：键走白名单，值经 ORM 参数化写入（方案 8.4）。"""
    if key not in WRITABLE_KEYS:
        allowed = ", ".join(sorted(WRITABLE_KEYS))
        raise ApiError(ErrorCode.MISSING_PARAM, f"不可写键: {key}（白名单: {allowed}）")
    expected = WRITABLE_KEYS[key]
    raw = value.get("value") if isinstance(value, dict) and "value" in value else value
    if not isinstance(raw, expected):
        raise ApiError(ErrorCode.MISSING_PARAM, f"键 {key} 的值类型不符")
    try:
        from astroforge.db import engine as db_engine
        from astroforge.db.repositories import app_settings as settings_repo

        async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
            await settings_repo.put_value(session, key, {"value": raw})
        return ok({"key": key, "value": raw})
    except Exception as exc:
        raise ApiError(ErrorCode.DB_UNAVAILABLE, f"数据库不可用，设置未保存: {exc}") from exc
