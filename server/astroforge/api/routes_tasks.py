"""任务路由：创建/查询/取消/重试/步骤/日志（方案 3.8 tasks API）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok
from astroforge.core.task_scheduler import MODULE_MAP

router = APIRouter(prefix="/tasks", tags=["tasks"])

VALID_STATUS = {"pending", "running", "success", "failed", "canceled"}


class CreateTaskBody(BaseModel):
    task_type: str = Field(
        description="spider_single|spider_site|spider_pdf|spider_table|mineru|wpd|anydoc|md2docx"
    )
    config: dict[str, Any] = Field(default_factory=dict)
    title: str | None = None
    mode: str = Field(default="standalone", description="standalone | pipeline")


@router.post("", dependencies=[deps.TokenDep])
async def create_task(body: CreateTaskBody, ctx: deps.CtxDep) -> dict:
    if body.mode == "standalone" and body.task_type not in MODULE_MAP:
        raise ApiError(ErrorCode.MISSING_PARAM,
                       f"未知任务类型: {body.task_type}（可选: {', '.join(sorted(MODULE_MAP))}）")
    if body.mode == "pipeline" and not body.config.get("pipeline"):
        raise ApiError(ErrorCode.MISSING_PARAM, "pipeline 模式需在 config.pipeline 指定模板名")
    try:
        record = ctx.scheduler.create_task(body.task_type, body.mode, body.title, body.config)
    except ValueError as exc:
        raise ApiError(ErrorCode.MISSING_PARAM, str(exc)) from exc
    return ok(record.to_dict())


@router.get("", dependencies=[deps.TokenDep])
async def list_tasks(
    ctx: deps.CtxDep,
    status: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    if status and status not in VALID_STATUS:
        raise ApiError(ErrorCode.MISSING_PARAM, f"非法状态筛选: {status}")
    records = ctx.scheduler.list(status, task_type, page, page_size)
    return ok({
        "page": page, "page_size": page_size, "total": len(records),
        "items": [r.to_dict(include_steps=False) for r in records],
    })


@router.get("/{task_uuid}", dependencies=[deps.TokenDep])
async def task_detail(task_uuid: str, ctx: deps.CtxDep) -> dict:
    record = ctx.scheduler.get(task_uuid)
    if record is None:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"任务不存在: {task_uuid}")
    return ok(record.to_dict())


@router.post("/{task_uuid}/cancel", dependencies=[deps.TokenDep])
async def cancel_task(task_uuid: str, ctx: deps.CtxDep) -> dict:
    if not ctx.scheduler.cancel(task_uuid):
        raise ApiError(ErrorCode.MISSING_PARAM, "任务不存在或状态不可取消")
    return ok({"task_uuid": task_uuid, "detail": "已请求取消"})


@router.post("/{task_uuid}/retry", dependencies=[deps.TokenDep])
async def retry_task(task_uuid: str, ctx: deps.CtxDep) -> dict:
    record = ctx.scheduler.retry(task_uuid)
    if record is None:
        raise ApiError(ErrorCode.MISSING_PARAM, "任务不存在或状态不可重试（仅 failed/canceled）")
    return ok(record.to_dict())


@router.get("/{task_uuid}/steps", dependencies=[deps.TokenDep])
async def task_steps(task_uuid: str, ctx: deps.CtxDep) -> dict:
    record = ctx.scheduler.get(task_uuid)
    if record is None:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"任务不存在: {task_uuid}")
    return ok({"task_uuid": task_uuid, "steps": record.to_dict()["steps"]})


@router.get("/{task_uuid}/logs", dependencies=[deps.TokenDep])
async def task_logs(task_uuid: str, ctx: deps.CtxDep, offset: int = Query(default=0, ge=0)) -> dict:
    if ctx.scheduler.get(task_uuid) is None:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"任务不存在: {task_uuid}")
    lines = ctx.scheduler.logs(task_uuid, offset)
    return ok({"task_uuid": task_uuid, "offset": offset, "lines": lines})
