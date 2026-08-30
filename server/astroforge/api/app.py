"""Sidereal Core 应用工厂：装配 lifespan、认证中间件、路由与 WS 通道。

启动流程（方案 3.8）：配置 → 数据目录/token → DB 引擎（尽力）→ 播种流水线
→ 监控采集器 + 调度器 worker → 就绪；停机反向回收。
"""
from __future__ import annotations

import asyncio
import contextlib
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from astroforge.ai.engine_client import EngineClient
from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, fail
from astroforge.core.config_loader import Settings, get_settings
from astroforge.core.monitor_collector import MonitorCollector
from astroforge.core.pipeline_engine import PipelineEngine
from astroforge.core.task_scheduler import Scheduler
from astroforge.utils.logger import get_logger, setup_logging
from astroforge.ws.hub import WSHub

log = get_logger("astroforge.app")

VERSION = "0.1.0"

OPEN_PATHS = {"/api/v1/system/health", "/docs", "/openapi.json", "/redoc"}


def ensure_token_file(settings: Settings) -> str:
    """首次启动生成 32 字节随机 token；之后复用（重置走 /service/token/reset）。"""
    token_path = settings.token_file()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    if token_path.exists():
        token = token_path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_hex(32)
    token_path.write_text(token, encoding="utf-8")
    log.info("已生成本机服务 token: %s", token_path)
    return token


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    log_file = settings.logs_dir() / "service.log"
    setup_logging(settings.service.log_level, log_file)
    settings.data_dir().mkdir(parents=True, exist_ok=True)

    hub = WSHub()
    pipeline_engine = PipelineEngine()
    pipeline_engine.seed_builtin()
    scheduler = Scheduler(settings, hub, pipeline_engine)
    collector = MonitorCollector(settings, hub)
    context = deps.AppContext(
        settings=settings, hub=hub, scheduler=scheduler,
        pipeline_engine=pipeline_engine, collector=collector,
        ai_client=EngineClient(settings.ai_engine),
    )
    context.token = ensure_token_file(settings)
    context.started_at_mono = time.monotonic()
    app.state.context = context

    # 数据库引擎尽力初始化（失败不阻断，调度器转内存态）
    try:
        from astroforge.db import engine as db_engine

        db_engine.init_engine(settings)
        if settings.service.auto_upgrade_db:
            await _run_migrations()
    except Exception as exc:
        log.warning("数据库初始化失败（服务继续，任务退化为内存态）: %s", exc)

    hub.start_heartbeat()
    collector.start()
    scheduler.start()
    log.info(
        "AstroForge Sidereal Core v%s 就绪 @ %s:%d",
        VERSION, settings.service.host, settings.service.port,
    )
    yield
    await scheduler.stop()
    await collector.stop()
    await hub.stop_heartbeat()
    with contextlib.suppress(Exception):
        from astroforge.db import engine as db_engine

        await db_engine.dispose_engine()
    log.info("Sidereal Core 已优雅停机")


async def _run_migrations() -> None:
    """以库方式执行 alembic upgrade head（auto_upgrade_db 开关）。"""
    from alembic import command
    from alembic.config import Config

    from astroforge.core.config_loader import REPO_ROOT

    ini = REPO_ROOT / "server" / "alembic.ini"
    if not ini.exists():
        log.warning("alembic.ini 不存在，跳过自动迁移")
        return
    alembic_cfg = Config(str(ini))
    migrations = REPO_ROOT / "server" / "astroforge" / "db" / "migrations"
    alembic_cfg.set_main_option("script_location", str(migrations))
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="AstroForge Sidereal Core",
        version=VERSION,
        description="衍星台本地服务核心：REST + WebSocket，双 UI 唯一后端",
        lifespan=lifespan,
    )
    app.state.settings = settings or get_settings()

    # ---- 路由注册 ----
    from astroforge.api import (
        routes_ai,
        routes_files,
        routes_monitor,
        routes_pipelines,
        routes_system,
        routes_tasks,
        routes_templates,
    )

    for router in (
        routes_system.router, routes_tasks.router, routes_pipelines.router,
        routes_templates.router, routes_files.router, routes_monitor.router,
        routes_ai.router,
    ):
        app.include_router(router, prefix="/api/v1")

    # ---- 认证中间件：/api/v1 除 health 外一律校验 token（方案 3.8）----
    @app.middleware("http")
    async def token_middleware(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/v1") and path not in OPEN_PATHS:
            token = request.headers.get("X-AstroForge-Token")
            ctx: deps.AppContext = app.state.context
            if not token or token != ctx.token:
                return JSONResponse(fail(ErrorCode.UNAUTHORIZED, "未认证或 Token 无效"), status_code=401)
        return await call_next(request)

    # ---- WS 通道（?token= 认证，方案 3.8）----
    @app.websocket("/ws/monitor")
    async def ws_monitor(websocket: WebSocket, token: str | None = None):
        if not deps.ws_token_ok(websocket, token):
            await websocket.close(code=4401)
            return
        ctx: deps.AppContext = app.state.context
        await ctx.hub.connect("monitor", websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await ctx.hub.disconnect("monitor", websocket)

    @app.websocket("/ws/logs/{task_uuid}")
    async def ws_logs(websocket: WebSocket, task_uuid: str, token: str | None = None):
        if not deps.ws_token_ok(websocket, token):
            await websocket.close(code=4401)
            return
        ctx: deps.AppContext = app.state.context
        channel = f"logs/{task_uuid}"
        await ctx.hub.connect(channel, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await ctx.hub.disconnect(channel, websocket)

    @app.websocket("/ws/ai")
    async def ws_ai(websocket: WebSocket, token: str | None = None):
        if not deps.ws_token_ok(websocket, token):
            await websocket.close(code=4401)
            return
        ctx: deps.AppContext = app.state.context
        await ctx.hub.connect("ai", websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await ctx.hub.disconnect("ai", websocket)

    # ---- 异常 → 统一信封 ----
    @app.exception_handler(ApiError)
    async def api_error_handler(_request: Request, exc: ApiError):
        return JSONResponse(fail(exc.code, exc.message, exc.data))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(fail(ErrorCode.MISSING_PARAM, f"参数校验失败: {exc.errors()[:3]}"))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        log.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(fail(ErrorCode.INTERNAL, f"服务内部错误: {exc}"))

    return app
