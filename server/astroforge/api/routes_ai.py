# -*- coding: utf-8 -*-
"""AI 路由：指令对话（三层降级）、会话历史（方案 3.7 / 3.8）。

会话持久化（ai_conversations/ai_messages，Phase 6.1.7）：DB 优先，
数据库不可达时退化为进程内存态（重启前有效）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from astroforge.ai import watcher
from astroforge.api import deps
from astroforge.api.response import ApiError, ErrorCode, ok

router = APIRouter(prefix="/ai", tags=["ai"])

# 内存会话存根：conversation_id -> messages（DB 不可用时的降级存储）
_conversations: dict[int, list[dict[str, Any]]] = {}
_next_id = 1


class ChatBody(BaseModel):
    message: str
    conversation_id: int | None = None


async def _resolve_conversation(ctx: deps.AppContext,
                                conversation_id: int | None) -> tuple[int, bool]:
    """确定会话 id：DB 优先（id 即 ai_conversations.id），失败回退内存自增。

    返回 (conversation_id, db_backed)。
    """
    global _next_id
    try:
        from astroforge.db import engine as db_engine
        from astroforge.db.repositories.tasks import AiRepo

        async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
            repo = AiRepo(session)
            conversation = None
            if conversation_id is not None:
                conversation = await repo.get_conversation(conversation_id)
            if conversation is None:
                conversation = await repo.create_conversation()
            return conversation.id, True
    except Exception:
        if conversation_id is None:
            memory_id = _next_id
            _next_id += 1
            _conversations[memory_id] = []
            return memory_id, False
        _conversations.setdefault(conversation_id, [])
        return conversation_id, False


async def _append_history(ctx: deps.AppContext, conversation_id: int, db_backed: bool,
                          role: str, content: str, instruction_json: dict | None) -> None:
    if db_backed:
        try:
            from astroforge.db import engine as db_engine
            from astroforge.db.repositories.tasks import AiRepo

            async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                await AiRepo(session).append_message(
                    conversation_id, role, content, instruction_json
                )
        except Exception:
            pass  # 落库失败静默降级
    _conversations.setdefault(conversation_id, []).append({
        "role": role, "content": content,
        **({"instruction": instruction_json} if instruction_json else {}),
    })


@router.post("/chat", dependencies=[deps.TokenDep])
async def chat(body: ChatBody, ctx: deps.CtxDep) -> dict:
    if not body.message.strip():
        raise ApiError(ErrorCode.MISSING_PARAM, "消息不能为空")

    conversation_id, db_backed = await _resolve_conversation(ctx, body.conversation_id)
    await _append_history(ctx, conversation_id, db_backed, "user", body.message, None)

    from astroforge.ai.engine_client import EngineUnavailable

    try:
        model_output = await ctx.ai_client.infer(body.message)
    except EngineUnavailable as exc:
        raise ApiError(ErrorCode.AI_ENGINE_UNREACHABLE,
                       f"AI 引擎不可达: {exc}（modules/ai_engine 未启动或模型未加载）") from exc

    from astroforge.ai.instruction_parser import parse_instruction

    result = parse_instruction(model_output, ctx.settings.ai)
    task_uuid = None
    instruction_json = result.instruction
    if instruction_json is not None:
        mode = "pipeline" if instruction_json.get("action") == "pipeline" else "standalone"
        record = ctx.scheduler.create_task(
            instruction_json["task_type"], mode=mode,
            title=instruction_json.get("title"), config=instruction_json.get("params", {}),
        )
        task_uuid = record.task_uuid
    await _append_history(ctx, conversation_id, db_backed,
                          "assistant", model_output, instruction_json)

    return ok({
        "conversation_id": conversation_id,
        "db_backed": db_backed,
        "reply": result.raw_reply,
        "instruction": result.instruction,
        "fallback": result.fallback,
        "notice": result.dropped_notes[0] if result.dropped_notes else None,
        "task_uuid": task_uuid,
    })


@router.get("/conversations", dependencies=[deps.TokenDep])
async def conversations() -> dict:
    try:
        from astroforge.db import engine as db_engine
        from astroforge.db.repositories.tasks import AiRepo

        async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
            items = [{"conversation_id": cid, "title": title, "turns": turns}
                     for cid, title, turns in await AiRepo(session).list_conversations()]
        return ok({"items": items})
    except Exception:
        items = [{"conversation_id": cid, "turns": len(msgs)}
                 for cid, msgs in _conversations.items()]
        return ok({"items": items, "note": "内存态（数据库不可用）"})


@router.get("/conversations/{conversation_id}/messages", dependencies=[deps.TokenDep])
async def messages(conversation_id: int) -> dict:
    try:
        from astroforge.db import engine as db_engine
        from astroforge.db.repositories.tasks import AiRepo

        async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
            rows = await AiRepo(session).messages(conversation_id)
            items = [{"role": r.role, "content": r.content,
                      "instruction": r.instruction_json} for r in rows]
        if items:
            return ok({"conversation_id": conversation_id, "messages": items})
    except Exception:
        pass
    memory = _conversations.get(conversation_id)
    if memory is None:
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"会话不存在: {conversation_id}")
    return ok({"conversation_id": conversation_id, "messages": memory})


@router.get("/engine/status", dependencies=[deps.TokenDep])
async def engine_status(ctx: deps.CtxDep) -> dict:
    return ok(await watcher.probe_status(ctx.settings))
