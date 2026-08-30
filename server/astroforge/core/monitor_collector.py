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

    def start(self) -> None:
        if not memory_monitor.PSUTIL_AVAILABLE:
            log.warning("psutil 未安装，监控采集关闭")
            return
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
        # TODO(Phase 1.2.2): 异步批量写入 monitor_metrics 表（复用 db/engine 会话）

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
