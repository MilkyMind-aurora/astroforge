"""AI 路由：指令对话（三层降级）、会话历史（方案 3.7 / 3.8）。

会话持久化（ai_conversations/ai_messages）属 Phase 6.1.7；当前内存态。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from astroforge.ai import watcher
from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok

router = APIRouter(prefix="/ai", tags=["ai"])

# 内存会话存根：conversation_id -> messages
_conversations: dict[int, list[dict[str, Any]]] = {}
_next_id = 1


class ChatBody(BaseModel):
    message: str
    conversation_id: int | None = None


@router.post("/chat", dependencies=[deps.TokenDep])
async def chat(body: ChatBody, ctx: deps.CtxDep) -> dict:
    if not body.message.strip():
        raise ApiError(ErrorCode.MISSING_PARAM, "消息不能为空")

    conversation_id = body.conversation_id
    if conversation_id is None:
        global _next_id
        conversation_id = _next_id
        _next_id += 1
        _conversations[conversation_id] = []
    history = _conversations.setdefault(conversation_id, [])
    history.append({"role": "user", "content": body.message})

    prompt = body.message
    from astroforge.ai.engine_client import EngineUnavailable

    try:
        model_output = await ctx.ai_client.infer(prompt)
    except EngineUnavailable as exc:
        raise ApiError(ErrorCode.AI_ENGINE_UNREACHABLE,
                       f"AI 引擎不可达: {exc}（modules/ai_engine 未启动或模型未加载）") from exc

    from astroforge.ai.instruction_parser import parse_instruction

    result = parse_instruction(model_output, ctx.settings.ai)
    task_uuid = None
    if result.instruction is not None:
        instruction = result.instruction
        mode = "pipeline" if instruction.get("action") == "pipeline" else "standalone"
        record = ctx.scheduler.create_task(
            instruction["task_type"], mode=mode,
            title=instruction.get("title"), config=instruction.get("params", {}),
        )
        task_uuid = record.task_uuid
        history.append({"role": "assistant", "content": model_output,
                        "instruction": instruction, "task_uuid": task_uuid})
    else:
        history.append({"role": "assistant", "content": model_output})

    return ok({
        "conversation_id": conversation_id,
        "reply": result.raw_reply,
        "instruction": result.instruction,
        "fallback": result.fallback,
        "notice": result.dropped_notes[0] if result.dropped_notes else None,
        "task_uuid": task_uuid,
    })


@router.get("/conversations", dependencies=[deps.TokenDep])
async def conversations() -> dict:
    items = [{"conversation_id": cid, "turns": len(msgs)} for cid, msgs in _conversations.items()]
    return ok({"items": items, "note": "会话持久化属 Phase 6.1.7"})


@router.get("/conversations/{conversation_id}/messages", dependencies=[deps.TokenDep])
async def messages(conversation_id: int) -> dict:
    if conversation_id not in _conversations:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"会话不存在: {conversation_id}")
    return ok({"conversation_id": conversation_id, "messages": _conversations[conversation_id]})


@router.get("/engine/status", dependencies=[deps.TokenDep])
async def engine_status(ctx: deps.CtxDep) -> dict:
    return ok(await watcher.probe_status(ctx.settings))
