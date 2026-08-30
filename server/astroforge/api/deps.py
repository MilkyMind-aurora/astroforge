"""FastAPI 依赖：从 app.state 取运行时单例；token 校验（方案 2.4 机制 12）。"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from astroforge.ai.engine_client import EngineClient
from astroforge.core.config_loader import Settings
from astroforge.core.monitor_collector import MonitorCollector
from astroforge.core.pipeline_engine import PipelineEngine
from astroforge.core.task_scheduler import Scheduler
from astroforge.ws.hub import WSHub


class AppContext:
    """应用运行时上下文（lifespan 装配）。"""

    def __init__(
        self,
        settings: Settings,
        hub: WSHub,
        scheduler: Scheduler,
        pipeline_engine: PipelineEngine,
        collector: MonitorCollector,
        ai_client: EngineClient,
    ):
        self.settings = settings
        self.hub = hub
        self.scheduler = scheduler
        self.pipeline_engine = pipeline_engine
        self.collector = collector
        self.ai_client = ai_client
        self.token: str = ""
        self.started_at_mono: float = 0.0
        self.shutdown_requested = False


def get_context(request: Request) -> AppContext:
    return request.app.state.context


CtxDep = Annotated[AppContext, Depends(get_context)]


def verify_token(request: Request, x_astroforge_token: Annotated[str | None, Header()] = None) -> None:
    """REST 认证：X-AstroForge-Token 必须与本机 token 文件一致。"""
    ctx: AppContext = request.app.state.context
    if not x_astroforge_token or x_astroforge_token != ctx.token:
        from astroforge.api.response import ApiError, ErrorCode

        raise ApiError(ErrorCode.UNAUTHORIZED, "未认证或 Token 无效（X-AstroForge-Token）")


TokenDep = Depends(verify_token)


def ws_token_ok(request: Request, token: str | None) -> bool:
    """WS 认证：?token= 查询参数校验。"""
    ctx: AppContext = request.app.state.context
    return bool(token) and token == ctx.token
