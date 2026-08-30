"""流水线路由：模板列表/保存/执行（NovaFlow 引擎，方案 3.5）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class SavePipelineBody(BaseModel):
    yaml_content: str


class RunPipelineBody(BaseModel):
    params: dict[str, Any] = {}
    title: str | None = None


@router.get("", dependencies=[deps.TokenDep])
async def list_pipelines(ctx: deps.CtxDep) -> dict:
    return ok({"items": [p.to_dict() for p in ctx.pipeline_engine.all()]})


@router.post("", dependencies=[deps.TokenDep])
async def save_pipeline(body: SavePipelineBody, ctx: deps.CtxDep) -> dict:
    parsed = ctx.pipeline_engine.save_custom(body.yaml_content)
    return ok(parsed.to_dict())


@router.post("/{name}/run", dependencies=[deps.TokenDep])
async def run_pipeline(name: str, body: RunPipelineBody, ctx: deps.CtxDep) -> dict:
    if ctx.pipeline_engine.get(name) is None:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"流水线模板不存在: {name}")
    record = ctx.scheduler.create_task(
        "pipeline", mode="pipeline", title=body.title or f"流水线: {name}",
        config={"pipeline": name, **body.params},
    )
    return ok(record.to_dict())
