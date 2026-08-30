"""监控路由：历史回放（实时数据走 WS /ws/monitor，方案 3.6）。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok

router = APIRouter(prefix="/monitor", tags=["monitor"])

VALID_RANGES = {"1h": 1, "6h": 6, "24h": 24}


@router.get("/history", dependencies=[deps.TokenDep])
async def history(ctx: deps.CtxDep, range: str = Query(default="1h")) -> dict:
    hours = VALID_RANGES.get(range)
    if hours is None:
        raise ApiError(ErrorCode.MISSING_PARAM, f"range 仅支持 {', '.join(VALID_RANGES)}")
    points = await ctx.collector.history_async(hours)
    return ok({"range": range, "points": points})
