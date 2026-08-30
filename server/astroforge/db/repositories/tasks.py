"""任务仓储层：全部查询经 SQLAlchemy Core/ORM 参数绑定（方案 8.4 硬性条款）。

服务核心优先保证可用性：数据库不可达时调度器退化为内存态（见 task_scheduler），
本层不吞异常，让调用方决定降级策略。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from astroforge.db.models import Artifact, Task, TaskStep


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TasksRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, task_type: str, mode: str, title: str | None, config: dict[str, Any]
    ) -> Task:
        task = Task(task_type=task_type, mode=mode, title=title, config=config, status="pending")
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get(self, task_uuid: uuid.UUID) -> Task | None:
        stmt = select(Task).where(Task.task_uuid == task_uuid)  # 绑定参数，非拼接
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list(
        self,
        status: str | None = None,
        task_type: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Task]:
        # 筛选字段为白名单枚举（调用方校验），条件经绑定参数传入
        stmt = select(Task).order_by(Task.created_at.desc())
        if status:
            stmt = stmt.where(Task.status == status)
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        stmt = stmt.offset(max(0, page - 1) * page_size).limit(min(page_size, 100))
        return list((await self.session.execute(stmt)).scalars())

    async def set_status(self, task_uuid: uuid.UUID, status: str, **extra: Any) -> None:
        values: dict[str, Any] = {"status": status}
        if status == "running":
            values["started_at"] = _now()
        if status in {"success", "failed", "canceled"}:
            values["finished_at"] = _now()
        values.update(extra)
        await self.session.execute(
            update(Task).where(Task.task_uuid == task_uuid).values(**values)
        )
        await self.session.commit()

    async def set_progress(self, task_uuid: uuid.UUID, progress: int) -> None:
        await self.session.execute(
            update(Task).where(Task.task_uuid == task_uuid).values(progress=progress)
        )
        await self.session.commit()

    async def add_step(
        self, task_uuid: uuid.UUID, step_index: int, step_name: str, input_ref: dict | None = None
    ) -> None:
        await self.session.execute(
            insert(TaskStep).values(
                task_uuid=task_uuid,
                step_index=step_index,
                step_name=step_name,
                status="pending",
                input_ref=input_ref,
            )
        )
        await self.session.commit()

    async def add_artifact(
        self,
        task_uuid: uuid.UUID,
        file_type: str,
        file_name: str,
        file_path: str,
        size_bytes: int | None = None,
    ) -> None:
        await self.session.execute(
            insert(Artifact).values(
                task_uuid=task_uuid,
                file_type=file_type,
                file_name=file_name,
                file_path=file_path,
                size_bytes=size_bytes,
            )
        )
        await self.session.commit()
