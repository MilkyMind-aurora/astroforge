"""SQLAlchemy 2.0 async 引擎与会话工厂（方案 2.4 机制 13）。

连接参数来自 config/settings.yaml；密码仅从环境变量读取（连接串
经 SQLAlchemy 引擎参数化传递，全程无 SQL 字符串拼接）。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from astroforge.core.config_loader import DatabaseSettings, Settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def build_database_url(db: DatabaseSettings) -> str:
    password = db.password()
    return (
        f"postgresql+asyncpg://{db.user}:{password}@{db.host}:{db.port}/{db.db_name}"
    )


def init_engine(settings: Settings) -> AsyncEngine:
    global _engine, _sessionmaker
    _engine = create_async_engine(
        build_database_url(settings.database),
        pool_size=settings.database.pool_size,
        max_overflow=settings.database.max_overflow,
        pool_pre_ping=settings.database.pool_pre_ping,
        pool_recycle=settings.database.pool_recycle,
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化（init_engine 未调用）")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("数据库引擎未初始化（init_engine 未调用）")
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def ping() -> bool:
    """连通性探测：SELECT 1 经 text() 参数化执行（无拼接）。"""
    from sqlalchemy import text

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
