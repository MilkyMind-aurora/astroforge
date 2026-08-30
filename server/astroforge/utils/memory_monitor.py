"""系统资源采样封装（psutil 守护导入，缺失时返回 None 优雅降级）。"""
from __future__ import annotations

from typing import Any

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    psutil = None  # type: ignore[assignment]
    PSUTIL_AVAILABLE = False


def sample() -> dict[str, Any] | None:
    """单次采样：CPU/内存/磁盘 IO/活跃进程数。psutil 缺失返回 None。"""
    if not PSUTIL_AVAILABLE:
        return None
    mem = psutil.virtual_memory()
    disk_io = psutil.disk_io_counters()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "mem_used_gb": round(mem.used / 1024**3, 2),
        "mem_percent": mem.percent,
        "disk_read_mbps": round((getattr(disk_io, "read_bytes", 0)) / 1024 / 1024, 2),
        "disk_write_mbps": round((getattr(disk_io, "write_bytes", 0)) / 1024 / 1024, 2),
        "active_processes": len(psutil.pids()),
    }


def process_memory_gb(pid: int) -> float | None:
    """指定进程的 RSS 内存（GB）；进程不存在返回 None。"""
    if not PSUTIL_AVAILABLE:
        return None
    try:
        return round(psutil.Process(pid).memory_info().rss / 1024**3, 2)
    except psutil.Error:
        return None
