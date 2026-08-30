"""AI 引擎看护：健康探测（供 env-check 与 AI 面板展示）。

崩溃自动重启（restart_limit）与拉起逻辑属 Phase 6.1.6，届时在此扩展。
"""
from __future__ import annotations

from typing import Any

from astroforge.core.config_loader import Settings


async def probe_status(settings: Settings) -> dict[str, Any]:
    """探测引擎状态：基础设施端点（固定配置 base_url），不主动拉起。"""
    from astroforge.ai.engine_client import EngineClient, EngineUnavailable

    client = EngineClient(settings.ai_engine)
    try:
        return {"reachable": True, **await client.health()}
    except EngineUnavailable as exc:
        return {"reachable": False, "detail": str(exc), "restart_limit": settings.ai_engine.restart_limit}
