"""监控采集器（方案 3.6 / 补丁 4）。

psutil 每秒采样 → WS /ws/monitor 实时推送；聚合粒度落内存环形缓冲
（monitor_metrics 表持久化属 Phase 1.2.2 落库步骤，本文件预留写点）。
"""
from __future__ import annotations

import asyncio
import contextlib
import time
from collections import deque
from typing import Any

from astroforge.core.config_loader import Settings
from astroforge.utils import memory_monitor
from astroforge.utils.logger import get_logger
from astroforge.ws.hub import WSHub

log = get_logger("astroforge.monitor")

# 10s 聚合粒度下，每 1 小时 360 点；24h 上限
_AGGREGATE_PER_HOUR = 360


class MonitorCollector:
    def __init__(self, settings: Settings, hub: WSHub):
        self.settings = settings
        self.hub = hub
        self._task: asyncio.Task | None = None
        # (metric_time_epoch, cpu, mem_gb, mem_percent) 聚合点
        self._aggregates: deque[tuple[float, float, float, float]] = deque(
            maxlen=_AGGREGATE_PER_HOUR * max(1, settings.monitor.history_hours)
        )
        self._acc: list[dict[str, Any]] = []
        self._db_enabled = False          # 尽力落库：DB 不可达退内存态
        self._db_warned = False
        self._last_cleanup = 0.0

    def start(self) -> None:
        if not memory_monitor.PSUTIL_AVAILABLE:
            log.warning("psutil 未安装，监控采集关闭")
            return
        try:
            from astroforge.db import engine as db_engine

            db_engine.get_sessionmaker()
            self._db_enabled = True
        except Exception:
            self._db_enabled = False
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="astroforge-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _loop(self) -> None:
        while True:
            sample = memory_monitor.sample()
            if sample is not None:
                await self.hub.broadcast("monitor", "monitor", sample)
                self._acc.append(sample)
                if len(self._acc) >= self.settings.monitor.aggregate_interval:
                    self._flush_aggregate()
            # 每小时清理 24h 前的时序数据（方案 3.9 保留策略）
            if self._db_enabled and time.time() - self._last_cleanup > 3600:
                self._last_cleanup = time.time()
                self._cleanup_old()
            await asyncio.sleep(max(1, self.settings.monitor.refresh_interval))

    def _flush_aggregate(self) -> None:
        if not self._acc:
            return
        count = len(self._acc)
        point = (
            time.time(),
            round(sum(s["cpu_percent"] for s in self._acc) / count, 2),
            round(sum(s["mem_used_gb"] for s in self._acc) / count, 2),
            round(sum(s["mem_percent"] for s in self._acc) / count, 2),
        )
        self._aggregates.append(point)
        self._acc.clear()
        self._persist_metric(point)

    def _persist_metric(self, point: tuple[float, float, float, float]) -> None:
        """聚合点异步落库 monitor_metrics（尽力，失败退内存态，只告警一次）。"""
        if not self._db_enabled:
            return

        async def _write() -> None:
            try:
                from datetime import datetime, timezone

                from astroforge.db import engine as db_engine
                from astroforge.db.models import MonitorMetric

                async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                    session.add(MonitorMetric(
                        metric_time=datetime.fromtimestamp(point[0], tz=timezone.utc),
                        cpu_percent=point[1], mem_used_gb=point[2], mem_percent=point[3],
                    ))
                    await session.commit()
            except Exception as exc:
                self._db_enabled = False
                if not self._db_warned:
                    self._db_warned = True
                    log.warning("监控落库失败（退内存态）: %s", exc)

        asyncio.get_running_loop().create_task(_write())

    def _cleanup_old(self) -> None:
        async def _clean() -> None:
            try:
                from datetime import datetime, timedelta, timezone

                from sqlalchemy import delete

                from astroforge.db import engine as db_engine
                from astroforge.db.models import MonitorMetric

                cutoff = datetime.now(timezone.utc) - timedelta(
                    hours=self.settings.monitor.history_hours
                )
                async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                    await session.execute(
                        delete(MonitorMetric).where(MonitorMetric.metric_time < cutoff)
                    )
                    await session.commit()
            except Exception:
                pass  # 清理失败不影响采集

        asyncio.get_running_loop().create_task(_clean())

    async def history_async(self, range_hours: int) -> list[dict[str, Any]]:
        """历史回放：优先查 monitor_metrics 表，失败退内存缓冲。"""
        try:
            from datetime import datetime, timedelta, timezone

            from sqlalchemy import select

            from astroforge.db import engine as db_engine
            from astroforge.db.models import MonitorMetric

            cutoff = datetime.now(timezone.utc) - timedelta(hours=range_hours)
            async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                rows = (await session.execute(
                    select(MonitorMetric)
                    .where(MonitorMetric.metric_time >= cutoff)
                    .order_by(MonitorMetric.metric_time)
                )).scalars()
                return [
                    {"time": r.metric_time.timestamp(), "cpu_percent": r.cpu_percent,
                     "mem_used_gb": r.mem_used_gb, "mem_percent": r.mem_percent}
                    for r in rows
                ]
        except Exception:
            return self.history(range_hours)

    def history(self, range_hours: int) -> list[dict[str, Any]]:
        """历史回放：range=1h/6h/24h，聚合点降采样输出。"""
        cutoff = time.time() - range_hours * 3600
        points = [p for p in self._aggregates if p[0] >= cutoff]
        if len(points) > 720:  # 输出最多 720 点，均匀抽稀
            step = len(points) / 720
            points = [points[int(i * step)] for i in range(720)]
        return [
            {
                "time": p[0],
                "cpu_percent": p[1],
                "mem_used_gb": p[2],
                "mem_percent": p[3],
            }
            for p in points
        ]
