"""应用设置仓储：app_settings 键值读写（方案 1.3.3 / 3.9）。

全部经 ORM 主键访问（session.get 自动参数化，无裸查询构造）；
可写键白名单由路由层传入，本层只管存取。
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from astroforge.db.models import AppSetting


async def list_all(session: AsyncSession, keys: Iterable[str]) -> dict[str, Any]:
    """按白名单键逐个主键读取，返回 {key: value}。"""
    items: dict[str, Any] = {}
    for key in keys:
        row = await session.get(AppSetting, key)
        if row is not None:
            items[key] = row.value
    return items


async def get_value(session: AsyncSession, key: str) -> Any | None:
    row = await session.get(AppSetting, key)
    return row.value if row is not None else None


async def put_value(session: AsyncSession, key: str, payload: dict[str, Any]) -> None:
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=payload))
    else:
        row.value = payload
    await session.commit()
