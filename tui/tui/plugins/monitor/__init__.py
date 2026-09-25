# -*- coding: utf-8 -*-
"""监控看板插件（方案 §2.4 L2）：key=monitor，env_dep=PostgreSQL（监控通道依赖）。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.monitor.page import MonitorPage, MonitorState

plugin = PagePlugin(
    key="monitor", title="监控看板", icon="nav.monitor", sort=6,
    env_dep=("PostgreSQL",),
    factory=lambda client, app_ref: MonitorPage(client, app_ref),
)

__all__ = ["MonitorPage", "MonitorState", "plugin"]
