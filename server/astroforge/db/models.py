"""ORM 模型：方案 3.9 的 10 张表（PostgreSQL 16+，DDL 基线）。

约定：JSONB 仅存 ≤64KB 半结构化小对象；时间一律 TIMESTAMPTZ + UTC；
全部数据访问经 ORM/Core 参数绑定，禁止拼接 SQL（方案 8.4 硬性条款）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uuid: Mapped[uuid.UUID] = mapped_column(unique=True, default=_uuid)
    task_type: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16))  # standalone / pipeline
    title: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    priority: Mapped[int] = mapped_column(SmallInteger, default=5)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    error_code: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(32), default="local")  # 远期多用户预留
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(BigInteger)


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.task_uuid", ondelete="CASCADE"))
    step_index: Mapped[int] = mapped_column(SmallInteger)
    step_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    input_ref: Mapped[dict | None] = mapped_column(JSONB)
    output_ref: Mapped[dict | None] = mapped_column(JSONB)
    log_path: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("uq_task_steps", "task_uuid", "step_index", unique=True),)


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(default=1)
    yaml_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_uuid: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.task_uuid", ondelete="CASCADE"))
    file_type: Mapped[str] = mapped_column(String(32))
    file_name: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(CHAR(64))
    preview_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocxTemplate(Base):
    __tablename__ = "docx_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_key: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    scene: Mapped[str | None] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(Text)
    preview_path: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str | None] = mapped_column(String(256))
    model_key: Mapped[str] = mapped_column(String(32), default="qwen2b")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16))  # user / assistant / system
    content: Mapped[str] = mapped_column(Text)
    instruction_json: Mapped[dict | None] = mapped_column(JSONB)
    token_count: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("idx_ai_messages_conv", "conversation_id", "created_at"),)


class MonitorMetric(Base):
    __tablename__ = "monitor_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    metric_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cpu_percent: Mapped[float | None] = mapped_column()
    mem_used_gb: Mapped[float | None] = mapped_column()
    mem_percent: Mapped[float | None] = mapped_column()
    disk_read_mbps: Mapped[float | None] = mapped_column()
    disk_write_mbps: Mapped[float | None] = mapped_column()
    active_tasks: Mapped[int | None] = mapped_column(SmallInteger)
    running_pids: Mapped[dict | None] = mapped_column(JSONB)

    __table_args__ = (Index("idx_metrics_time_brin", "metric_time"),)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(8))  # warn / error
    source: Mapped[str] = mapped_column(String(32))  # monitor / task / env / db
    message: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("idx_alerts_open", "created_at"),)


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
