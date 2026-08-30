"""子进程执行器：conda run 环境隔离调用模块 CLI（方案 2.4 机制 1）。

输入配置写临时 JSON 文件传递；stdout 逐行回调；支持超时与取消。
conda 不在 PATH 时回退当前解释器（开发态），生产环境由脚本保证 conda 存在。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import sys
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from astroforge.core.config_loader import REPO_ROOT, Settings
from astroforge.utils.logger import get_logger

log = get_logger("astroforge.runner")

LineCallback = Callable[[str], Awaitable[None]]
DEFAULT_TIMEOUT_SECONDS = 3600


def _resolve_module_path(script_rel: str) -> Path:
    """模块脚本相对仓库根解析（支持 ASTROFORGE_ROOT 覆盖，安装态可迁移）。"""
    root = Path(os.environ.get("ASTROFORGE_ROOT", str(REPO_ROOT)))
    return root / script_rel


async def run_module(
    env_name: str,
    script_rel: str,
    config: dict[str, Any],
    settings: Settings,
    on_line: LineCallback | None = None,
    cancel_event: asyncio.Event | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any] | None]:
    """执行模块 CLI，返回 (returncode, 结果 JSON)。

    结果 JSON 由模块按约定写入 output 文件；约定缺失时 result 为 None。
    """
    data_dir = settings.data_dir()
    cache_dir = data_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:12]
    config_path = cache_dir / f"task_config_{token}.json"
    output_path = cache_dir / f"task_result_{token}.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    script_path = _resolve_module_path(script_rel)
    if not script_path.exists():
        log.error("模块脚本不存在: %s", script_path)
        return 3001, {"code": 3001, "message": f"模块脚本不存在: {script_rel}"}

    if shutil.which("conda"):
        # conda run 在目标环境 PATH 中解析 python，跨平台一致
        cmd = ["conda", "run", "-n", env_name, "--no-capture-output", "python"]
        cmd += [str(script_path), "--config", str(config_path), "--output", str(output_path)]
    else:
        # 开发态回退：无 conda 时用当前解释器（依赖需在本环境可用）
        log.warning("conda 不在 PATH，回退当前解释器执行（生产环境请通过 scripts 启动）")
        cmd = [sys.executable, str(script_path), "--config", str(config_path), "--output", str(output_path)]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(script_path.parent),
        )
    except OSError as exc:
        return 3001, {"code": 3001, "message": f"子进程启动失败: {exc}"}

    async def _pump_stdout() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").rstrip()
            if line and on_line is not None:
                await on_line(line)

    pump = asyncio.create_task(_pump_stdout())
    cancel_watcher: asyncio.Task | None = None
    if cancel_event is not None:

        async def _watch_cancel() -> None:
            await cancel_event.wait()
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()

        cancel_watcher = asyncio.create_task(_watch_cancel())

    try:
        returncode = await asyncio.wait_for(proc.wait(), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.terminate()
        returncode = await proc.wait()
        return 3002, {"code": 3002, "message": f"子进程超时（>{timeout_seconds}s）"}

    with __import__("contextlib").suppress(asyncio.CancelledError):
        await pump
    if cancel_watcher is not None:
        cancel_watcher.cancel()

    result: dict[str, Any] | None = None
    if output_path.exists():
        try:
            result = json.loads(output_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("结果 JSON 解析失败: %s", exc)
    for path in (config_path, output_path):
        # 临时文件即用即删，cache 目录不堆积
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
    if cancel_event is not None and cancel_event.is_set():
        return 1300, {"code": 1300, "message": "任务已取消"}
    return returncode, result
