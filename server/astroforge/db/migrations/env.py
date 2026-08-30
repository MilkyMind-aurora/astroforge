"""Alembic 迁移环境：连接串从 Sidereal Core 配置动态构建，模型元数据为准。"""
from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 保证 astroforge 包可导入（alembic.ini 位于 server/）
SERVER_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SERVER_DIR))

from astroforge.core.config_loader import load_settings  # noqa: E402
from astroforge.db import models  # noqa: E402
from astroforge.db.engine import build_database_url  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = models.Base.metadata
_settings = load_settings()


def _database_url() -> str:
    """优先环境变量 ASTROFORGE_DATABASE_URL，否则按 settings.yaml 构建。"""
    import os

    return os.environ.get("ASTROFORGE_DATABASE_URL") or build_database_url(_settings.database)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
