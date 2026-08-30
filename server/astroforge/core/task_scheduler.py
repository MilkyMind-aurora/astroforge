"""任务调度器：状态机 + 串行队列 + 子进程编排（方案 2.4 机制 1/4/5）。

可用性优先：数据库可达时任务落库（repositories.tasks），不可达时
自动退化为内存态并告警，服务核心不因存储故障而不可用。
"""
from __future__ import annotations

import asyncio
import uuid as uuid_lib
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from astroforge.core import process_runner
from astroforge.core.config_loader import Settings
from astroforge.core.pipeline_engine import PipelineEngine
from astroforge.utils.logger import get_logger
from astroforge.ws.hub import WSHub

log = get_logger("astroforge.scheduler")

# 任务类型 → (conda 环境, 模块脚本相对路径)
MODULE_MAP: dict[str, tuple[str, str]] = {
    "spider_single": ("env_spider", "modules/spider/cli.py"),
    "spider_site": ("env_spider", "modules/spider/cli.py"),
    "spider_pdf": ("env_spider", "modules/spider/cli.py"),
    "spider_table": ("env_spider", "modules/spider/cli.py"),
    "mineru": ("env_mineru", "modules/mineru/cli.py"),
    "wpd": ("env_wpd", "modules/wpd/cli.py"),
    "anydoc": ("env_anydoc", "modules/anydoc/cli.py"),
    "md2docx": ("env_md2docx", "modules/md2docx/cli.py"),
}
LOG_BUFFER_SIZE = 2000


@dataclass
class TaskRecord:
    task_uuid: str
    task_type: str
    mode: str
    title: str | None
    config: dict[str, Any]
    status: str = "pending"  # pending/running/success/failed/canceled
    progress: int = 0
    error_code: int | None = None
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    finished_at: str | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=LOG_BUFFER_SIZE))
    result: dict[str, Any] | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_dict(self, include_steps: bool = True) -> dict[str, Any]:
        data = {
            "task_uuid": self.task_uuid,
            "task_type": self.task_type,
            "mode": self.mode,
            "title": self.title,
            "status": self.status,
            "progress": self.progress,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }
        if include_steps:
            data["steps"] = [dict(step) for step in self.steps]
        return data


class Scheduler:
    def __init__(self, settings: Settings, hub: WSHub, engine: PipelineEngine):
        self.settings = settings
        self.hub = hub
        self.engine = engine
        self._tasks: dict[str, TaskRecord] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._db_available = False
        self._sessionmaker = None

    # ---- 生命周期 ----
    def start(self) -> None:
        self._try_init_db()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._worker_loop(), name="astroforge-worker")

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    def _try_init_db(self) -> None:
        """数据库可达则启用持久化；失败不阻断服务（内存态降级）。"""
        try:
            from astroforge.db import engine as db_engine

            self._sessionmaker = db_engine.get_sessionmaker()
            self._db_available = True
            log.info("任务持久化已启用（PostgreSQL）")
        except Exception as exc:  # 引擎未初始化或配置缺失
            self._db_available = False
            log.warning("数据库不可用，任务退化为内存态: %s", exc)

    # ---- 任务创建 / 查询 ----
    def create_task(
        self, task_type: str, mode: str = "standalone", title: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> TaskRecord:
        if mode == "standalone" and task_type not in MODULE_MAP:
            raise ValueError(f"未知任务类型: {task_type}")
        record = TaskRecord(
            task_uuid=uuid_lib.uuid4().hex,
            task_type=task_type,
            mode=mode,
            title=title or task_type,
            config=config or {},
        )
        if mode == "pipeline":
            pipeline = self.engine.get(config.get("pipeline", "")) if config else None
            if pipeline is None:
                raise ValueError("流水线模板不存在")
            record.steps = [
                {"step_index": i, "step_name": s.name, "task_type": s.task_type,
                 "status": "pending"}
                for i, s in enumerate(pipeline.steps)
            ]
        else:
            record.steps = [{"step_index": 0, "step_name": task_type,
                             "task_type": task_type, "status": "pending"}]
        self._tasks[record.task_uuid] = record
        self._queue.put_nowait(record.task_uuid)
        self._persist_status(record)
        self._persist_create(record)
        return record

    def get(self, task_uuid: str) -> TaskRecord | None:
        return self._tasks.get(task_uuid)

    def list(self, status: str | None = None, task_type: str | None = None,
             page: int = 1, page_size: int = 20) -> list[TaskRecord]:
        # 白名单筛选（status/type 由路由层枚举校验），内存分页
        records = [t for t in self._tasks.values()
                   if (status is None or t.status == status)
                   and (task_type is None or t.task_type == task_type)]
        records.sort(key=lambda r: r.created_at, reverse=True)
        start = max(0, page - 1) * page_size
        return records[start:start + min(page_size, 100)]

    def logs(self, task_uuid: str, offset: int = 0) -> list[str]:
        record = self._tasks.get(task_uuid)
        return list(record.logs)[offset:] if record else []

    def cancel(self, task_uuid: str) -> bool:
        record = self._tasks.get(task_uuid)
        if record is None or record.status not in {"pending", "running"}:
            return False
        record.cancel_event.set()
        if record.status == "pending":
            record.status = "canceled"
            self._broadcast(record, "status")
            self._persist_status(record)
        return True

    def retry(self, task_uuid: str) -> TaskRecord | None:
        old = self._tasks.get(task_uuid)
        if old is None or old.status not in {"failed", "canceled"}:
            return None
        return self.create_task(old.task_type, old.mode, old.title, old.config)

    # ---- 执行循环（串行，方案 2.4 机制 4）----
    async def _worker_loop(self) -> None:
        while True:
            task_uuid = await self._queue.get()
            record = self._tasks.get(task_uuid)
            if record is None or record.status in {"canceled"}:
                self._queue.task_done()
                continue
            try:
                await self._run_record(record)
            except Exception as exc:  # 调度器永不因单任务崩溃
                log.exception("任务执行异常")
                record.status, record.error_code = "failed", 2002
                record.error_message = f"调度器内部错误: {exc}"
                self._broadcast(record, "status")
            finally:
                self._queue.task_done()

    async def _run_record(self, record: TaskRecord) -> None:
        record.status = "running"
        record.started_at = datetime.now(timezone.utc).isoformat()
        self._broadcast(record, "status")
        self._persist_status(record)

        steps = record.steps
        total = max(1, len(steps))
        for index, step in enumerate(steps):
            if record.cancel_event.is_set():
                record.status, record.error_message = "canceled", "任务已取消"
                break
            task_type = step["task_type"]
            mapping = MODULE_MAP.get(task_type)
            if mapping is None:
                record.status, record.error_code = "failed", 1001
                record.error_message = f"未知任务类型: {task_type}"
                break
            env_name, script_rel = mapping
            step["status"] = "running"
            step_config = dict(record.config)
            if record.mode == "pipeline":
                pipeline = self.engine.get(record.config.get("pipeline", ""))
                if pipeline is not None:
                    step_config.update(pipeline.steps[index].config)
            await self.hub.broadcast(
                f"logs/{record.task_uuid}", "log",
                {"level": "INFO", "text": f"步骤 {index + 1}/{total}: {step['step_name']} 开始"},
            )

            returncode, result = await process_runner.run_module(
                env_name, script_rel, step_config, self.settings,
                on_line=self._make_line_callback(record),
                cancel_event=record.cancel_event,
            )
            step_ok = returncode == 0 and (result is None or result.get("code") == 0)
            step["status"] = "success" if step_ok else "failed"
            record.progress = int((index + 1) / total * 100)
            self._broadcast(record, "progress")
            if not step_ok:
                record.status = "failed"
                record.error_code = (result or {}).get("code", returncode or 3003)
                record.error_message = (result or {}).get("message", f"步骤失败（rc={returncode}）")
                break
        else:
            record.status = "success"
            record.result = result
        record.finished_at = datetime.now(timezone.utc).isoformat()
        self._broadcast(record, "status")
        self._persist_status(record)

    def _make_line_callback(self, record: TaskRecord) -> Any:
        async def on_line(line: str) -> None:
            record.logs.append(line)
            level = "ERROR" if "[ERROR]" in line else "INFO"
            await self.hub.broadcast(
                f"logs/{record.task_uuid}", "log", {"level": level, "text": line}
            )
        return on_line

    def _broadcast(self, record: TaskRecord, msg_type: str) -> None:
        """状态变更同步到双 UI（fire-and-forget，不阻塞调度）。"""
        asyncio.get_running_loop().create_task(
            self.hub.broadcast(f"logs/{record.task_uuid}", msg_type,
                               {"status": record.status, "progress": record.progress,
                                "error_code": record.error_code})
        )

    def _persist_status(self, record: TaskRecord) -> None:
        if not self._db_available or self._sessionmaker is None:
            return
        # 尽力持久化：失败仅告警，不影响任务执行
        async def _write() -> None:
            try:
                from astroforge.db.repositories.tasks import TasksRepo

                async with self._sessionmaker() as session:  # type: ignore[misc]
                    repo = TasksRepo(session)
                    await repo.set_status(
                        uuid_lib.UUID(record.task_uuid), record.status,
                        error_code=str(record.error_code) if record.error_code else None,
                        error_message=record.error_message, progress=record.progress,
                    )
            except Exception as exc:
                log.warning("任务状态落库失败（转内存态）: %s", exc)
                self._db_available = False
        asyncio.get_running_loop().create_task(_write())

    def _persist_create(self, record: TaskRecord) -> None:
        """任务创建落库：tasks 主行 + steps（方案 1.4.4，尽力降级）。"""
        if not self._db_available or self._sessionmaker is None:
            return

        async def _write() -> None:
            try:
                from astroforge.db.repositories.tasks import TasksRepo

                async with self._sessionmaker() as session:  # type: ignore[misc]
                    repo = TasksRepo(session)
                    task = await repo.create(
                        record.task_type, record.mode, record.title, record.config,
                        task_uuid=uuid_lib.UUID(record.task_uuid),
                    )
                    for step in record.steps:
                        await repo.add_step(
                            task.task_uuid, step["step_index"], step["step_name"]
                        )
            except Exception as exc:
                log.warning("任务创建落库失败（内存 uuid 保留）: %s", exc)
                self._db_available = False
        asyncio.get_running_loop().create_task(_write())

    async def list_from_db(
        self, status: str | None = None, task_type: str | None = None,
        page: int = 1, page_size: int = 20,
    ) -> list[dict[str, Any]]:
        """DB 优先的历史查询（方案 1.4.4）；失败抛出让路由退化内存态。"""
        if not self._db_available or self._sessionmaker is None:
            raise RuntimeError("DB 不可用")
        from astroforge.db.repositories.tasks import TasksRepo

        async with self._sessionmaker() as session:  # type: ignore[misc]
            repo = TasksRepo(session)
            rows = await repo.list(status, task_type, page, page_size)
            return [{
                "task_uuid": str(r.task_uuid), "task_type": r.task_type, "mode": r.mode,
                "title": r.title, "status": r.status, "progress": r.progress,
                "error_code": r.error_code, "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            } for r in rows]
