"""AI 引擎看护：健康探测与崩溃自动重启（方案 3.7，重启上限 restart_limit）。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astroforge.core.config_loader import REPO_ROOT, Settings
from astroforge.utils.logger import get_logger

log = get_logger("astroforge.aiwatch")


def engine_script_path() -> Path:
    return REPO_ROOT / "modules" / "ai_engine" / "server.py"


def launch_command(settings: Settings) -> list[str] | None:
    """拉起 AI 引擎进程的命令（conda 优先；启动逻辑由生命周期统一调度）。"""
    script = engine_script_path()
    if not script.exists():
        return None
    return [
        "conda", "run", "-n", "env_ai", "--no-capture-output",
        sys.executable if not sys.platform.startswith("win") else "python",
        str(script), "--host", "127.0.0.1",
    ]


async def probe_status(settings: Settings) -> dict[str, Any]:
    """探测引擎状态：供 env-check 与 AI 面板展示；不主动拉起。"""
    from astroforge.ai.engine_client import EngineClient, EngineUnavailable

    client = EngineClient(settings.ai_engine)
    try:
        return {"reachable": True, **await client.health()}
    except EngineUnavailable as exc:
        return {"reachable": False, "detail": str(exc), "restart_limit": settings.ai_engine.restart_limit}
